#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


MAP_PROFILES = {
    "conus-overview": {
        "label": "Lower 48 overview",
        "bbox": (-125.0, 24.0, -66.0, 50.0),
        "min_zoom": 0,
        "max_zoom": 7,
        "output": "mapdata/tiles/conus-overview-raster.mbtiles",
        "priority": 10,
    },
    "northeast": {
        "label": "Northeast",
        "bbox": (-82.0, 36.0, -65.0, 48.5),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/northeast-raster.mbtiles",
        "priority": 80,
    },
    "southeast": {
        "label": "Southeast",
        "bbox": (-91.0, 24.0, -75.0, 37.5),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/southeast-raster.mbtiles",
        "priority": 70,
    },
    "midwest": {
        "label": "Midwest and Great Lakes",
        "bbox": (-104.0, 36.0, -80.0, 50.0),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/midwest-raster.mbtiles",
        "priority": 70,
    },
    "south-central": {
        "label": "South Central",
        "bbox": (-107.0, 25.0, -88.0, 38.0),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/south-central-raster.mbtiles",
        "priority": 70,
    },
    "mountain-west": {
        "label": "Mountain West",
        "bbox": (-116.0, 31.0, -102.0, 49.0),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/mountain-west-raster.mbtiles",
        "priority": 70,
    },
    "west-coast": {
        "label": "West Coast",
        "bbox": (-125.0, 31.0, -113.0, 49.0),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/west-coast-raster.mbtiles",
        "priority": 70,
    },
    "west-coast-hd": {
        "label": "West Coast high detail",
        "bbox": (-125.0, 31.0, -113.0, 49.0),
        "min_zoom": 0,
        "max_zoom": 14,
        "output": "mapdata/tiles/west-coast-hd-raster.mbtiles",
        "priority": 115,
    },
    "mountain-west-hd": {
        "label": "Mountain West high detail",
        "bbox": (-116.0, 31.0, -102.0, 49.0),
        "min_zoom": 0,
        "max_zoom": 14,
        "output": "mapdata/tiles/mountain-west-hd-raster.mbtiles",
        "priority": 115,
    },
    "arizona-hd": {
        "label": "Arizona high detail",
        "bbox": (-115.2, 31.0, -108.7, 37.2),
        "min_zoom": 0,
        "max_zoom": 14,
        "output": "mapdata/tiles/arizona-hd-raster.mbtiles",
        "priority": 130,
    },
    "tri-state-ultra": {
        "label": "NY/NJ/CT tri-state ultra detail",
        "bbox": (-75.6, 39.3, -71.5, 42.4),
        "min_zoom": 0,
        "max_zoom": 15,
        "output": "mapdata/tiles/tri-state-ultra-raster.mbtiles",
        "priority": 140,
    },
    "alaska": {
        "label": "Alaska",
        "bbox": (-170.0, 51.0, -129.0, 72.0),
        "min_zoom": 0,
        "max_zoom": 8,
        "output": "mapdata/tiles/alaska-raster.mbtiles",
        "priority": 60,
    },
    "hawaii": {
        "label": "Hawaii",
        "bbox": (-161.0, 18.0, -154.0, 23.0),
        "min_zoom": 0,
        "max_zoom": 11,
        "output": "mapdata/tiles/hawaii-raster.mbtiles",
        "priority": 60,
    },
    "puerto-rico": {
        "label": "Puerto Rico",
        "bbox": (-68.2, 17.5, -65.0, 18.8),
        "min_zoom": 0,
        "max_zoom": 12,
        "output": "mapdata/tiles/puerto-rico-raster.mbtiles",
        "priority": 60,
    },
    "nyc": {
        "label": "NYC metro",
        "bbox": (-75.0, 39.8, -71.8, 42.2),
        "min_zoom": 0,
        "max_zoom": 14,
        "output": "mapdata/tiles/nyc-raster.mbtiles",
        "priority": 100,
    },
}


WEATHER_PRESETS = {
    "national": {
        "bbox": (-125.0, 24.0, -66.0, 50.0),
        "zoom": 5,
        "min_zoom": 4,
        "cell_pixels": 8,
        "min_coverage": 0.15,
        "interval": 600,
    },
    "regional": {
        "zoom": 6,
        "min_zoom": 5,
        "cell_pixels": 3,
        "min_coverage": 0.08,
        "interval": 300,
    },
    "local": {
        "zoom": 7,
        "min_zoom": 5,
        "cell_pixels": 3,
        "min_coverage": 0.08,
        "interval": 240,
    },
}


def contains(profile, lat, lon):
    lon_min, lat_min, lon_max, lat_max = profile["bbox"]
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def bbox_area(profile):
    lon_min, lat_min, lon_max, lat_max = profile["bbox"]
    return (lon_max - lon_min) * (lat_max - lat_min)


def profile_names_for_group(group):
    if group == "all-us":
        return [
            "conus-overview",
            "northeast",
            "southeast",
            "midwest",
            "south-central",
            "mountain-west",
            "west-coast",
            "alaska",
            "hawaii",
            "puerto-rico",
        ]
    if group == "starter":
        return ["conus-overview", "northeast", "nyc"]
    if group == "conus-regions":
        return [
            "conus-overview",
            "northeast",
            "southeast",
            "midwest",
            "south-central",
            "mountain-west",
            "west-coast",
        ]
    if group == "western-hd":
        return ["west-coast-hd", "mountain-west-hd", "arizona-hd"]
    if group == "travel-hd":
        return ["west-coast-hd", "mountain-west-hd", "arizona-hd", "tri-state-ultra"]
    return [group]


def select_map_profile(lat, lon, tiles_dir):
    candidates = []
    for name, profile in MAP_PROFILES.items():
        path = Path(profile["output"])
        if tiles_dir:
            path = Path(tiles_dir) / path.name
        if not path.exists():
            continue
        if contains(profile, lat, lon):
            candidates.append((profile["priority"], -bbox_area(profile), name, path))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2], candidates[0][3]

    for fallback in ("conus-overview", "nyc"):
        profile = MAP_PROFILES[fallback]
        path = Path(profile["output"])
        if tiles_dir:
            path = Path(tiles_dir) / path.name
        if path.exists():
            return fallback, path

    return "", None


def regional_weather_bbox(lat, lon):
    candidates = []
    for name, profile in MAP_PROFILES.items():
        if name in ("conus-overview", "nyc"):
            continue
        if contains(profile, lat, lon):
            candidates.append((profile["priority"], -bbox_area(profile), profile["bbox"]))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]

    return WEATHER_PRESETS["national"]["bbox"]


def local_weather_bbox(lat, lon):
    lon_pad = 3.2
    lat_pad = 2.4
    return (
        max(-180.0, lon - lon_pad),
        max(-85.0, lat - lat_pad),
        min(180.0, lon + lon_pad),
        min(85.0, lat + lat_pad),
    )


def print_shell(values):
    for key, value in values.items():
        print("%s=%s" % (key, value))


def format_bbox(bbox):
    return ",".join(("%g" % value) for value in bbox)


def list_profiles(args):
    data = {}
    for name, profile in MAP_PROFILES.items():
        data[name] = dict(profile)
        data[name]["bbox"] = list(profile["bbox"])
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


def select_map(args):
    name, path = select_map_profile(args.lat, args.lon, args.tiles_dir)
    if args.shell:
        print_shell({"TILE_PROFILE": name, "TILE_SOURCE": str(path or "")})
    elif path:
        print(path)
    return 0 if path else 1


def map_path(args):
    profile = MAP_PROFILES[args.profile]
    path = Path(profile["output"])
    if args.tiles_dir:
        path = Path(args.tiles_dir) / path.name
    if args.shell:
        print_shell({"TILE_PROFILE": args.profile, "TILE_SOURCE": str(path)})
    else:
        print(path)
    return 0


def weather(args):
    preset_name = args.profile
    if preset_name == "auto":
        preset_name = "regional"
    preset = dict(WEATHER_PRESETS[preset_name])

    if preset_name == "regional":
        bbox = regional_weather_bbox(args.lat, args.lon)
    elif preset_name == "local":
        bbox = local_weather_bbox(args.lat, args.lon)
    else:
        bbox = preset["bbox"]

    values = {
        "WEATHER_BBOX": format_bbox(bbox),
        "NETWORK_ZOOM": preset["zoom"],
        "NETWORK_MIN_ZOOM": preset["min_zoom"],
        "NETWORK_CELL_PIXELS": preset["cell_pixels"],
        "NETWORK_MIN_COVERAGE": preset["min_coverage"],
        "WEATHER_INTERVAL": preset["interval"],
    }

    if args.shell:
        print_shell(values)
    else:
        print(json.dumps(values, indent=2, sort_keys=True))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="viz1090 coverage profiles for offline maps and weather")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List raster map coverage profiles")
    list_parser.set_defaults(func=list_profiles)

    select_parser = subparsers.add_parser("select-map", help="Select the best existing raster map for a location")
    select_parser.add_argument("--lat", type=float, required=True)
    select_parser.add_argument("--lon", type=float, required=True)
    select_parser.add_argument("--tiles-dir", default="mapdata/tiles")
    select_parser.add_argument("--shell", action="store_true")
    select_parser.set_defaults(func=select_map)

    path_parser = subparsers.add_parser("map-path", help="Print the configured path for a raster map profile")
    path_parser.add_argument("profile", choices=sorted(MAP_PROFILES))
    path_parser.add_argument("--tiles-dir", default="mapdata/tiles")
    path_parser.add_argument("--shell", action="store_true")
    path_parser.set_defaults(func=map_path)

    weather_parser = subparsers.add_parser("weather", help="Emit weather fetch settings")
    weather_parser.add_argument("--profile", choices=("auto", "national", "regional", "local"), default="auto")
    weather_parser.add_argument("--lat", type=float, required=True)
    weather_parser.add_argument("--lon", type=float, required=True)
    weather_parser.add_argument("--shell", action="store_true")
    weather_parser.set_defaults(func=weather)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
