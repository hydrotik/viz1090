#!/usr/bin/env python3
import argparse
import json
import math
import struct
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path


RAINVIEWER_API = "https://api.rainviewer.com/public/weather-maps.json"
USER_AGENT = "viz1090 weather fallback/0.1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def fetch_url(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def latest_radar_frame(metadata):
    radar = metadata.get("radar") or {}
    frames = []
    frames.extend(radar.get("past") or [])
    frames.extend(radar.get("nowcast") or [])
    if not frames:
        raise ValueError("RainViewer metadata did not include radar frames")
    return max(frames, key=lambda frame: int(frame.get("time", 0)))


def rainviewer_tile_url(metadata, frame, lat, lon, zoom, size, color, smooth, snow):
    host = metadata.get("host")
    path = frame.get("path")
    if not host or not path:
        raise ValueError("RainViewer metadata missing host/path")
    return "%s%s/%d/%d/%.5f/%.5f/%d/%d_%d.png" % (
        host.rstrip("/"),
        path,
        size,
        zoom,
        lat,
        lon,
        color,
        smooth,
        snow,
    )


def rainviewer_xyz_tile_url(metadata, frame, x, y, zoom, size, color, smooth, snow):
    host = metadata.get("host")
    path = frame.get("path")
    if not host or not path:
        raise ValueError("RainViewer metadata missing host/path")
    return "%s%s/%d/%d/%d/%d/%d/%d_%d.png" % (
        host.rstrip("/"),
        path,
        size,
        zoom,
        x,
        y,
        color,
        smooth,
        snow,
    )


def paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def png_chunks(data):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG image")

    offset = len(PNG_SIGNATURE)
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            raise ValueError("truncated PNG chunk")
        yield kind, data[payload_start:payload_end]
        offset = payload_end + 4
        if kind == b"IEND":
            break


def decode_png_rgba(data):
    width = height = bit_depth = color_type = None
    compressed = []
    palette = []
    palette_alpha = []

    for kind, payload in png_chunks(data):
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("unsupported PNG format")
        elif kind == b"PLTE":
            palette = [tuple(payload[i : i + 3]) for i in range(0, len(payload), 3)]
        elif kind == b"tRNS":
            palette_alpha = list(payload)
        elif kind == b"IDAT":
            compressed.append(payload)

    if width is None or height is None:
        raise ValueError("PNG missing IHDR")

    if color_type == 6:
        if bit_depth != 8:
            raise ValueError("unsupported PNG format")
        raw_bpp = 4
        stride = width * raw_bpp
    elif color_type == 2:
        if bit_depth != 8:
            raise ValueError("unsupported PNG format")
        raw_bpp = 3
        stride = width * raw_bpp
    elif color_type == 3:
        if bit_depth not in (1, 2, 4, 8):
            raise ValueError("unsupported PNG format")
        raw_bpp = 1
        stride = (width * bit_depth + 7) // 8
    else:
        raise ValueError("unsupported PNG color type %s" % color_type)

    raw = zlib.decompress(b"".join(compressed))
    rows = []
    pos = 0
    previous = bytearray(stride)

    for _ in range(height):
        filter_type = raw[pos]
        pos += 1
        scanline = bytearray(raw[pos : pos + stride])
        pos += stride

        for i in range(stride):
            left = scanline[i - raw_bpp] if i >= raw_bpp else 0
            up = previous[i]
            up_left = previous[i - raw_bpp] if i >= raw_bpp else 0

            if filter_type == 1:
                scanline[i] = (scanline[i] + left) & 0xFF
            elif filter_type == 2:
                scanline[i] = (scanline[i] + up) & 0xFF
            elif filter_type == 3:
                scanline[i] = (scanline[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[i] = (scanline[i] + paeth(left, up, up_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError("unsupported PNG filter %s" % filter_type)

        rows.append(bytes(scanline))
        previous = scanline

    pixels = []
    if color_type == 6:
        for row in rows:
            pixels.append([tuple(row[i : i + 4]) for i in range(0, len(row), 4)])
    elif color_type == 2:
        for row in rows:
            pixels.append([(row[i], row[i + 1], row[i + 2], 255) for i in range(0, len(row), 3)])
    else:
        for row in rows:
            decoded = []
            if bit_depth == 8:
                values = row[:width]
            else:
                values = []
                mask = (1 << bit_depth) - 1
                for packed in row:
                    for shift in range(8 - bit_depth, -1, -bit_depth):
                        values.append((packed >> shift) & mask)
                        if len(values) == width:
                            break
                    if len(values) == width:
                        break

            for value in values:
                if value >= len(palette):
                    decoded.append((0, 0, 0, 0))
                    continue
                rgb = palette[value]
                alpha = palette_alpha[value] if value < len(palette_alpha) else 255
                decoded.append((rgb[0], rgb[1], rgb[2], alpha))
            pixels.append(decoded)

    return width, height, pixels


def lon_to_world_x(lon, zoom, size):
    return (lon + 180.0) / 360.0 * size * (2**zoom)


def lat_to_world_y(lat, zoom, size):
    sin_lat = math.sin(math.radians(max(-85.05112878, min(85.05112878, lat))))
    return (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * size * (2**zoom)


def world_x_to_lon(x, zoom, size):
    return x / (size * (2**zoom)) * 360.0 - 180.0


def world_y_to_lat(y, zoom, size):
    n = math.pi - 2.0 * math.pi * y / (size * (2**zoom))
    return math.degrees(math.atan(math.sinh(n)))


def pixel_to_lon_lat(px, py, center_lat, center_lon, zoom, size):
    center_x = lon_to_world_x(center_lon, zoom, size)
    center_y = lat_to_world_y(center_lat, zoom, size)
    world_x = center_x - size / 2.0 + px
    world_y = center_y - size / 2.0 + py
    return world_x_to_lon(world_x, zoom, size), world_y_to_lat(world_y, zoom, size)


def tile_xy_for_lon_lat(lon, lat, zoom):
    count = 2**zoom
    x = int(math.floor((lon + 180.0) / 360.0 * count))
    sin_lat = math.sin(math.radians(max(-85.05112878, min(85.05112878, lat))))
    y = int(math.floor((0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * count))
    return max(0, min(count - 1, x)), max(0, min(count - 1, y))


def tile_ranges_for_bbox(bbox, zoom):
    lon_min, lat_min, lon_max, lat_max = bbox
    if lon_min > lon_max:
        lon_min, lon_max = lon_max, lon_min
    if lat_min > lat_max:
        lat_min, lat_max = lat_max, lat_min

    x_min, y_max = tile_xy_for_lon_lat(lon_min, lat_min, zoom)
    x_max, y_min = tile_xy_for_lon_lat(lon_max, lat_max, zoom)

    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min

    return range(x_min, x_max + 1), range(y_min, y_max + 1)


def parse_bbox(value):
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be lon_min,lat_min,lon_max,lat_max")
    try:
        lon_min, lat_min, lon_max, lat_max = [float(part) for part in parts]
    except ValueError:
        raise argparse.ArgumentTypeError("bbox values must be numeric")
    if not (-180.0 <= lon_min <= 180.0 and -180.0 <= lon_max <= 180.0):
        raise argparse.ArgumentTypeError("bbox longitude values must be between -180 and 180")
    if not (-90.0 <= lat_min <= 90.0 and -90.0 <= lat_max <= 90.0):
        raise argparse.ArgumentTypeError("bbox latitude values must be between -90 and 90")
    return lon_min, lat_min, lon_max, lat_max


def clip_tiles_to_bbox(tiles, bbox):
    lon_min, lat_min, lon_max, lat_max = bbox
    if lon_min > lon_max:
        lon_min, lon_max = lon_max, lon_min
    if lat_min > lat_max:
        lat_min, lat_max = lat_max, lat_min

    clipped = []
    for tile in tiles:
        tile_lat_min, tile_lon_min, tile_lat_max, tile_lon_max, intensity = tile
        if tile_lat_max < lat_min or tile_lat_min > lat_max:
            continue
        if tile_lon_max < lon_min or tile_lon_min > lon_max:
            continue
        clipped.append(
            (
                max(tile_lat_min, lat_min),
                max(tile_lon_min, lon_min),
                min(tile_lat_max, lat_max),
                min(tile_lon_max, lon_max),
                intensity,
            )
        )
    return clipped


def classify_intensity(r, g, b, a):
    if a < 16:
        return 0

    if r > 145 and b > 120 and g < 150:
        return 4
    if r > 155 and g < 155:
        return 3
    if r > 145 and g > 120:
        return 2
    if g > 90:
        return 1

    brightness = max(r, g, b)
    if brightness > 225:
        return 4
    if brightness > 175:
        return 3
    if brightness > 115:
        return 2
    return 1


def is_placeholder_tile(width, height, pixels):
    total = max(1, width * height)
    visible = 0
    label_like = 0

    for row in pixels:
        for r, g, b, a in row:
            if a <= 12:
                continue
            visible += 1
            if a > 100 and ((r > 220 and g > 220 and b > 220) or (r < 25 and g < 25 and b < 25)):
                label_like += 1

    if visible == 0:
        return False

    visible_ratio = visible / float(total)
    label_ratio = label_like / float(visible)
    return visible_ratio > 0.03 and label_ratio > 0.35


def tiles_from_image(width, height, pixels, center_lat, center_lon, zoom, size, cell_pixels, min_coverage):
    center_x = lon_to_world_x(center_lon, zoom, size)
    center_y = lat_to_world_y(center_lat, zoom, size)
    origin_x = center_x - size / 2.0
    origin_y = center_y - size / 2.0
    return tiles_from_image_at_origin(width, height, pixels, origin_x, origin_y, zoom, size, cell_pixels, min_coverage)


def tiles_from_image_at_origin(width, height, pixels, origin_x, origin_y, zoom, size, cell_pixels, min_coverage):
    tiles = []

    for y in range(0, height, cell_pixels):
        for x in range(0, width, cell_pixels):
            count = 0
            total = [0, 0, 0, 0]
            samples = 0

            for py in range(y, min(y + cell_pixels, height)):
                for px in range(x, min(x + cell_pixels, width)):
                    samples += 1
                    r, g, b, a = pixels[py][px]
                    if a > 12:
                        count += 1
                        total[0] += r
                        total[1] += g
                        total[2] += b
                        total[3] += a

            if samples == 0 or count / float(samples) < min_coverage:
                continue

            avg = [value / float(count) for value in total]
            intensity = classify_intensity(avg[0], avg[1], avg[2], avg[3])
            if intensity < 1:
                continue

            lon1 = world_x_to_lon(origin_x + x, zoom, size)
            lat1 = world_y_to_lat(origin_y + y, zoom, size)
            lon2 = world_x_to_lon(origin_x + min(x + cell_pixels, width), zoom, size)
            lat2 = world_y_to_lat(origin_y + min(y + cell_pixels, height), zoom, size)
            tiles.append((min(lat1, lat2), min(lon1, lon2), max(lat1, lat2), max(lon1, lon2), intensity))

    return tiles


def write_tiles(path, tiles, metadata, frame, source_url, preserve_empty=False):
    if not tiles and preserve_empty and path.exists():
        print("network weather returned no precipitation; preserving existing %s" % path)
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write("# source=rainviewer generated=%s frame_time=%s\n" % (metadata.get("generated", ""), frame.get("time", "")))
        handle.write("# Weather data by RainViewer https://www.rainviewer.com/\n")
        handle.write("# tile_url=%s\n" % source_url)
        handle.write("# lat_min,lon_min,lat_max,lon_max,intensity\n")
        for tile in tiles:
            handle.write("%.6f,%.6f,%.6f,%.6f,%d\n" % tile)

    temp_path.replace(path)
    print("wrote %d network radar tile(s) to %s" % (len(tiles), path))
    return len(tiles)


def fetch_rainviewer(args):
    metadata = json.loads(fetch_url(args.api_url, args.timeout).decode("utf-8"))
    frame = latest_radar_frame(metadata)

    if args.bbox:
        tiles = []
        urls = []
        x_range, y_range = tile_ranges_for_bbox(args.bbox, args.zoom)
        for x in x_range:
            for y in y_range:
                tile_url = rainviewer_xyz_tile_url(
                    metadata, frame, x, y, args.zoom, args.size, args.color, args.smooth, args.snow
                )
                image_data = fetch_url(tile_url, args.timeout)
                width, height, pixels = decode_png_rgba(image_data)
                if is_placeholder_tile(width, height, pixels):
                    print("skipping placeholder radar tile %s" % tile_url, file=sys.stderr)
                    continue
                tiles.extend(
                    tiles_from_image_at_origin(
                        width,
                        height,
                        pixels,
                        x * args.size,
                        y * args.size,
                        args.zoom,
                        args.size,
                        args.cell_pixels,
                        args.min_coverage,
                    )
                )
                urls.append(tile_url)

        tiles = clip_tiles_to_bbox(tiles, args.bbox)
        source_url = "bbox=%s tiles=%d" % (",".join("%.5f" % value for value in args.bbox), len(urls))
        return write_tiles(Path(args.output), tiles, metadata, frame, source_url, args.preserve_empty)

    tile_url = rainviewer_tile_url(
        metadata, frame, args.lat, args.lon, args.zoom, args.size, args.color, args.smooth, args.snow
    )
    image_data = fetch_url(tile_url, args.timeout)
    width, height, pixels = decode_png_rgba(image_data)
    if is_placeholder_tile(width, height, pixels):
        return write_tiles(Path(args.output), [], metadata, frame, tile_url, args.preserve_empty)
    tiles = tiles_from_image(
        width,
        height,
        pixels,
        args.lat,
        args.lon,
        args.zoom,
        args.size,
        args.cell_pixels,
        args.min_coverage,
    )
    return write_tiles(Path(args.output), tiles, metadata, frame, tile_url, args.preserve_empty)


def build_parser():
    parser = argparse.ArgumentParser(description="Fetch internet radar data into viz1090 radar tile cache")
    parser.add_argument("--lat", type=float, default=40.723972)
    parser.add_argument("--lon", type=float, default=-73.845139)
    parser.add_argument("--bbox", type=parse_bbox, help="lon_min,lat_min,lon_max,lat_max area to fetch with XYZ tiles")
    parser.add_argument("--output", default="weather/radar_tiles.csv")
    parser.add_argument("--api-url", default=RAINVIEWER_API)
    parser.add_argument("--zoom", type=int, default=7)
    parser.add_argument("--size", type=int, choices=(256, 512), default=512)
    parser.add_argument("--color", type=int, default=2)
    parser.add_argument("--smooth", type=int, choices=(0, 1), default=1)
    parser.add_argument("--snow", type=int, choices=(0, 1), default=1)
    parser.add_argument("--cell-pixels", type=int, default=6)
    parser.add_argument("--min-coverage", type=float, default=0.15)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--preserve-empty", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        fetch_rainviewer(args)
        return 0
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as error:
        print("network weather failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
