#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.coverage_profiles import MAP_PROFILES, profile_names_for_group


def expand_profiles(values):
    names = []
    for value in values:
        for name in profile_names_for_group(value):
            if name not in MAP_PROFILES:
                raise SystemExit("unknown tile profile '%s'" % name)
            if name not in names:
                names.append(name)
    return names


def command_for_profile(args, name):
    profile = MAP_PROFILES[name]
    max_zoom = min(profile["max_zoom"], args.max_zoom) if args.max_zoom is not None else profile["max_zoom"]
    command = [
        sys.executable,
        "tools/build_raster_mbtiles.py",
        "--tile-url",
        args.tile_url,
        "--bbox=%s" % ",".join("%g" % value for value in profile["bbox"]),
        "--min-zoom",
        str(profile["min_zoom"]),
        "--max-zoom",
        str(max_zoom),
        "--output",
        profile["output"],
        "--name",
        "viz1090 %s raster" % profile["label"],
        "--jobs",
        str(args.jobs),
        "--max-tiles",
        str(args.max_tiles),
        "--format",
        args.format,
    ]
    if args.force:
        command.append("--force")
    if args.dry_run:
        command.append("--dry-run")
    return command


def run(args):
    names = expand_profiles(args.profiles)
    for name in names:
        command = command_for_profile(args, name)
        print("+ %s" % " ".join(command), flush=True)
        if not args.print_only:
            status = subprocess.run(command).returncode
            if status != 0:
                return status
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Build viz1090 raster MBTiles packs from a local tile renderer")
    parser.add_argument(
        "--tile-url",
        required=True,
        help="Local/provider-approved raster URL with {z}, {x}, {y}",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["starter"],
        help="Profiles or groups: starter, conus-regions, all-us, nyc, northeast, west-coast, ...",
    )
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--max-tiles", type=int, default=250000)
    parser.add_argument("--max-zoom", type=int, help="Cap each profile's configured max zoom")
    parser.add_argument("--format", default="png", choices=("png", "jpg", "jpeg", "webp"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    return parser


def main(argv=None):
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
