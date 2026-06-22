#!/usr/bin/env python3
import argparse
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_raster_mbtiles import parse_bbox, tile_ranges_for_bbox, tile_xy_for_lon_lat


DEFAULT_RINGMAST4R_RAW_BASE = "https://raw.githubusercontent.com/Ringmast4r/FLOCK/main/data/tiles"
DEFAULT_DEFLOCKHOPPER_URL = (
    "https://raw.githubusercontent.com/FoggedLens/deflockhopper_maps/master/public/cameras-us.json.gz"
)
DEFAULT_USER_AGENT = "viz1090 FLOCK overlay builder/0.1"


def classify_feature(properties):
    text = " ".join("%s=%s" % (key, value) for key, value in properties.items()).lower()
    if "flock" in text:
        return 2
    if "alpr" in text or "license" in text or "licence" in text:
        return 1
    return 0


def feature_points(payload):
    for feature in payload.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            continue
        properties = feature.get("properties") or {}
        yield lat, lon, classify_feature(properties)


def deflockhopper_points(payload):
    if not isinstance(payload, list):
        return
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
        except (TypeError, ValueError):
            continue
        yield lat, lon, classify_feature(item)


def point_in_bbox(point, bbox):
    lat, lon, _kind = point
    lon_min, lat_min, lon_max, lat_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def group_points_by_tile(points, bbox, zoom):
    grouped = {}
    for point in points:
        if not point_in_bbox(point, bbox):
            continue
        lat, lon, _kind = point
        x, y = tile_xy_for_lon_lat(lon, lat, zoom)
        grouped.setdefault((x, y), []).append(point)
    return grouped


def tile_url(base_url, zoom, x, y):
    return "%s/%d/%d/%d.json" % (base_url.rstrip("/"), zoom, x, y)


def fetch_bytes(url, timeout, user_agent):
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_json(url, timeout, user_agent):
    return json.loads(fetch_bytes(url, timeout, user_agent).decode("utf-8"))


def load_deflockhopper_payload(args):
    if args.input_file:
        data = Path(args.input_file).read_bytes()
    else:
        data = fetch_bytes(args.deflockhopper_url, args.timeout, args.user_agent)

    if args.input_file and not str(args.input_file).endswith(".gz"):
        return json.loads(data.decode("utf-8"))

    return json.loads(gzip.decompress(data).decode("utf-8"))


def write_csv_tile(path, points):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        handle.write("# lat,lon,kind  kind: 0=surveillance, 1=ALPR, 2=Flock Safety\n")
        for lat, lon, kind in points:
            handle.write("%.7f,%.7f,%d\n" % (lat, lon, kind))
    temp.replace(path)


def write_grouped_tiles(grouped, output_root, dry_run):
    written = 0
    points_total = 0
    for (x, y), points in sorted(grouped.items()):
        points_total += len(points)
        output = output_root / str(x) / ("%d.csv" % y)
        if dry_run:
            print("would write %d point(s) to %s" % (len(points), output))
        else:
            write_csv_tile(output, points)
        written += 1
    return written, points_total


def build_ringmast4r_overlay(args):
    x_range, y_range = tile_ranges_for_bbox(args.bbox, args.zoom)
    output_root = Path(args.output_dir) / str(args.zoom)
    fetched = 0
    missing = 0
    written = 0
    points_total = 0

    for x in x_range:
        for y in y_range:
            url = tile_url(args.raw_base, args.zoom, x, y)
            try:
                payload = fetch_json(url, args.timeout, args.user_agent)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    missing += 1
                    continue
                raise
            points = list(feature_points(payload))
            fetched += 1
            points_total += len(points)

            if not points:
                continue

            output = output_root / str(x) / ("%d.csv" % y)
            if args.dry_run:
                print("would write %d point(s) to %s" % (len(points), output))
            else:
                write_csv_tile(output, points)
            written += 1

            if args.sleep > 0:
                time.sleep(args.sleep)

    print(
        "FLOCK overlay tiles: fetched=%d missing=%d written=%d points=%d output=%s"
        % (fetched, missing, written, points_total, output_root)
    )
    return 0


def build_deflockhopper_overlay(args):
    output_root = Path(args.output_dir) / str(args.zoom)
    payload = load_deflockhopper_payload(args)
    grouped = group_points_by_tile(deflockhopper_points(payload), args.bbox, args.zoom)
    written, points_total = write_grouped_tiles(grouped, output_root, args.dry_run)
    print(
        "FLOCK overlay tiles: source=deflockhopper written=%d points=%d output=%s"
        % (written, points_total, output_root)
    )
    return 0


def build_overlay(args):
    if args.source == "ringmast4r":
        return build_ringmast4r_overlay(args)
    return build_deflockhopper_overlay(args)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Build compact viz1090 FLOCK/surveillance overlay tiles."
    )
    parser.add_argument("--source", choices=("deflockhopper", "ringmast4r"), default="deflockhopper")
    parser.add_argument("--bbox", default="-125,24,-66,50", type=parse_bbox)
    parser.add_argument("--output-dir", default="mapdata/flock")
    parser.add_argument("--zoom", type=int, default=6)
    parser.add_argument("--raw-base", default=DEFAULT_RINGMAST4R_RAW_BASE)
    parser.add_argument("--deflockhopper-url", default=DEFAULT_DEFLOCKHOPPER_URL)
    parser.add_argument("--input-file", help="Optional local deflockhopper JSON or JSON.GZ file")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional delay between successful tile downloads")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None):
    return build_overlay(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
