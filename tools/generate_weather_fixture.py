#!/usr/bin/env python3
import argparse
import math
from pathlib import Path


def generate_tiles(lat, lon, output):
    cell_deg = 0.025
    rows = []

    for y in range(-12, 13):
        for x in range(-16, 17):
            nx = (x + 0.25 * y) / 10.0
            ny = y / 7.5
            band = math.exp(-(nx * nx + ny * ny))
            embedded = math.exp(-(((x - 2.0) ** 2) / 18.0 + ((y + 1.0) ** 2) / 10.0))
            trailing = 0.45 * math.exp(-(((x + 8.0) ** 2) / 30.0 + ((y - 4.0) ** 2) / 12.0))
            value = band + embedded + trailing

            if value > 1.45:
                intensity = 4
            elif value > 1.05:
                intensity = 3
            elif value > 0.62:
                intensity = 2
            elif value > 0.28:
                intensity = 1
            else:
                continue

            tile_lat = lat + y * cell_deg
            tile_lon = lon + x * cell_deg
            rows.append(
                (
                    tile_lat - cell_deg * 0.5,
                    tile_lon - cell_deg * 0.5,
                    tile_lat + cell_deg * 0.5,
                    tile_lon + cell_deg * 0.5,
                    intensity,
                )
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("# lat_min,lon_min,lat_max,lon_max,intensity\n")
        for row in rows:
            handle.write("%.6f,%.6f,%.6f,%.6f,%d\n" % row)

    return len(rows)


def build_parser():
    parser = argparse.ArgumentParser(description="Generate a simulated radar tile cache")
    parser.add_argument("--lat", type=float, default=40.723972)
    parser.add_argument("--lon", type=float, default=-73.845139)
    parser.add_argument("--output", default="weather/radar_tiles.csv")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    count = generate_tiles(args.lat, args.lon, Path(args.output))
    print("wrote %d radar tile(s) to %s" % (count, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
