#!/usr/bin/env python3
import argparse
import concurrent.futures
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from math import atan, floor, log, pi, radians, sinh, tan, cos


DEFAULT_USER_AGENT = "viz1090 raster mbtiles builder/0.1"
RASTER_FORMATS = {"png", "jpg", "jpeg", "webp"}


def parse_bbox(value):
    try:
        lon_min, lat_min, lon_max, lat_max = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox must be lon_min,lat_min,lon_max,lat_max") from exc

    if lon_min >= lon_max:
        raise argparse.ArgumentTypeError("bbox lon_min must be less than lon_max")
    if lat_min >= lat_max:
        raise argparse.ArgumentTypeError("bbox lat_min must be less than lat_max")
    if lon_min < -180 or lon_max > 180 or lat_min < -85.05112878 or lat_max > 85.05112878:
        raise argparse.ArgumentTypeError("bbox must be within Web Mercator limits")
    return lon_min, lat_min, lon_max, lat_max


def normalize_format(value):
    value = value.lower().lstrip(".")
    if value == "jpeg":
        return "jpg"
    if value not in RASTER_FORMATS:
        raise argparse.ArgumentTypeError("format must be png, jpg, jpeg, or webp")
    return value


def tile_xy_for_lon_lat(lon, lat, zoom):
    lat = max(-85.05112878, min(85.05112878, lat))
    count = 2**zoom
    x = floor((lon + 180.0) / 360.0 * count)
    lat_rad = radians(lat)
    y = floor((1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / pi) / 2.0 * count)
    return max(0, min(count - 1, int(x))), max(0, min(count - 1, int(y)))


def lon_from_tile_x(x, zoom):
    return x / float(2**zoom) * 360.0 - 180.0


def lat_from_tile_y(y, zoom):
    n = pi - 2.0 * pi * y / float(2**zoom)
    return atan(sinh(n)) * 180.0 / pi


def tile_ranges_for_bbox(bbox, zoom):
    lon_min, lat_min, lon_max, lat_max = bbox
    x_min, y_max = tile_xy_for_lon_lat(lon_min, lat_min, zoom)
    x_max, y_min = tile_xy_for_lon_lat(lon_max, lat_max, zoom)
    return range(x_min, x_max + 1), range(y_min, y_max + 1)


def iter_tiles(bbox, min_zoom, max_zoom):
    for z in range(min_zoom, max_zoom + 1):
        x_range, y_range = tile_ranges_for_bbox(bbox, z)
        for x in x_range:
            for y in y_range:
                yield z, x, y


def tile_count(bbox, min_zoom, max_zoom):
    count = 0
    for z in range(min_zoom, max_zoom + 1):
        x_range, y_range = tile_ranges_for_bbox(bbox, z)
        count += len(x_range) * len(y_range)
    return count


def open_mbtiles(path, metadata):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    conn.execute(
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)"
    )
    conn.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")
    conn.executemany("INSERT INTO metadata (name, value) VALUES (?, ?)", sorted(metadata.items()))
    conn.commit()
    return conn


def make_tile_url(template, z, x, y):
    return template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))


def fetch_tile(template, tile, timeout, user_agent, retries):
    z, x, y = tile
    url = make_tile_url(template, z, x, y)
    headers = {"User-Agent": user_agent}
    last_error = None

    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status == 204 or response.status == 404:
                    return tile, None
                return tile, response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (204, 404):
                return tile, None
            last_error = exc
        except urllib.error.URLError as exc:
            last_error = exc

        if attempt < retries:
            time.sleep(0.25 * (attempt + 1))

    raise RuntimeError("%s failed: %s" % (url, last_error))


def insert_tile(conn, tile, data, input_scheme):
    if not data:
        return
    z, x, y = tile
    tile_row = y if input_scheme == "tms" else (2**z - 1 - y)
    conn.execute(
        "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
        (z, x, tile_row, data),
    )


def build_mbtiles(args):
    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit("%s already exists; pass --force to overwrite" % output)

    total = tile_count(args.bbox, args.min_zoom, args.max_zoom)
    if args.dry_run:
        print("would fetch %d tiles for zoom %d..%d into %s" % (total, args.min_zoom, args.max_zoom, output))
        return 0
    if total > args.max_tiles:
        raise SystemExit(
            "refusing to fetch %d tiles; increase --max-tiles after confirming disk/time budget" % total
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    if partial.exists():
        partial.unlink()

    lon_min, lat_min, lon_max, lat_max = args.bbox
    metadata = {
        "name": args.name,
        "type": "baselayer",
        "version": "1",
        "description": args.description,
        "format": args.format,
        "bounds": "%.6f,%.6f,%.6f,%.6f" % (lon_min, lat_min, lon_max, lat_max),
        "minzoom": str(args.min_zoom),
        "maxzoom": str(args.max_zoom),
        "scheme": "tms",
    }

    conn = open_mbtiles(partial, metadata)
    fetched = 0
    written = 0
    try:
        tiles = list(iter_tiles(args.bbox, args.min_zoom, args.max_zoom))
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = [
                executor.submit(fetch_tile, args.tile_url, tile, args.timeout, args.user_agent, args.retries)
                for tile in tiles
            ]
            for future in concurrent.futures.as_completed(futures):
                tile, data = future.result()
                fetched += 1
                if data:
                    insert_tile(conn, tile, data, args.input_scheme)
                    written += 1
                if fetched % args.commit_every == 0:
                    conn.commit()
                    print("fetched %d/%d, wrote %d tiles" % (fetched, total, written), file=sys.stderr)
        conn.commit()
    finally:
        conn.close()

    os.replace(partial, output)
    print("wrote %d raster tile(s) to %s" % (written, output))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build raster MBTiles from a local or provider-approved XYZ/TMS tile URL."
    )
    parser.add_argument("--tile-url", required=True, help="Tile URL template with {z}, {x}, and {y}")
    parser.add_argument("--bbox", required=True, type=parse_bbox, help="lon_min,lat_min,lon_max,lat_max")
    parser.add_argument("--min-zoom", required=True, type=int)
    parser.add_argument("--max-zoom", required=True, type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--name", default="viz1090 offline basemap")
    parser.add_argument("--description", default="Raster MBTiles generated for viz1090")
    parser.add_argument("--format", default="png", type=normalize_format)
    parser.add_argument("--input-scheme", choices=("xyz", "tms"), default="xyz")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--commit-every", type=int, default=250)
    parser.add_argument("--max-tiles", type=int, default=250000)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.min_zoom < 0 or args.max_zoom < args.min_zoom or args.max_zoom > 22:
        raise SystemExit("zoom range must be 0 <= min_zoom <= max_zoom <= 22")
    if args.jobs < 1:
        raise SystemExit("--jobs must be at least 1")
    if "{z}" not in args.tile_url or "{x}" not in args.tile_url or "{y}" not in args.tile_url:
        raise SystemExit("--tile-url must include {z}, {x}, and {y}")

    return build_mbtiles(args)


if __name__ == "__main__":
    sys.exit(main())
