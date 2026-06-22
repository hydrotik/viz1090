#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from pathlib import Path


RASTER_FORMATS = {"png", "jpg", "jpeg", "webp"}
VECTOR_FORMATS = {"pbf", "mvt", "vector"}


class InspectionError(Exception):
    pass


def normalize_format(value):
    if not value:
        return ""
    value = value.strip().lower()
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    if value == "x-protobuf":
        return "pbf"
    return value


def detect_blob_format(blob):
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if blob.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(blob) >= 12 and blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "webp"
    if blob.startswith(b"\x1f\x8b"):
        return "pbf"
    return ""


def read_metadata(conn):
    metadata = {}
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()
    tables = {row[0] for row in rows}
    if "metadata" not in tables:
        return metadata, tables

    try:
        for name, value in conn.execute("SELECT name, value FROM metadata"):
            metadata[str(name)] = str(value)
    except sqlite3.Error:
        pass
    return metadata, tables


def inspect_mbtiles(path):
    path = Path(path)
    if not path.exists():
        raise InspectionError("file does not exist")
    if not path.is_file():
        raise InspectionError("path is not a file")

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise InspectionError(f"could not open SQLite database: {exc}") from exc

    try:
        metadata, tables = read_metadata(conn)
        if "tiles" not in tables:
            raise InspectionError("missing required 'tiles' table")

        try:
            min_zoom, max_zoom, count = conn.execute(
                "SELECT MIN(zoom_level), MAX(zoom_level), COUNT(*) FROM tiles"
            ).fetchone()
        except sqlite3.Error as exc:
            raise InspectionError(f"could not read tiles table: {exc}") from exc

        if count == 0:
            raise InspectionError("tiles table is empty")

        sample_blob = conn.execute(
            "SELECT tile_data FROM tiles WHERE tile_data IS NOT NULL LIMIT 1"
        ).fetchone()
        sample_format = detect_blob_format(sample_blob[0]) if sample_blob else ""
    finally:
        conn.close()

    declared_format = normalize_format(metadata.get("format", ""))
    effective_format = declared_format or sample_format

    if effective_format in RASTER_FORMATS:
        kind = "raster"
        usable = True
    elif effective_format in VECTOR_FORMATS:
        kind = "vector"
        usable = False
    elif sample_format in RASTER_FORMATS:
        kind = "raster"
        usable = True
        effective_format = sample_format
    elif sample_format in VECTOR_FORMATS:
        kind = "vector"
        usable = False
        effective_format = sample_format
    else:
        kind = "unknown"
        usable = False

    return {
        "path": str(path),
        "name": metadata.get("name", ""),
        "bounds": metadata.get("bounds", ""),
        "declared_format": declared_format,
        "sample_format": sample_format,
        "effective_format": effective_format,
        "kind": kind,
        "usable": usable,
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "count": count,
    }


def print_report(result):
    print(f"path: {result['path']}")
    if result["name"]:
        print(f"name: {result['name']}")
    if result["bounds"]:
        print(f"bounds: {result['bounds']}")
    print(f"tiles: {result['count']} rows, zoom {result['min_zoom']}..{result['max_zoom']}")
    print(f"metadata.format: {result['declared_format'] or 'missing'}")
    print(f"sample tile format: {result['sample_format'] or 'unknown'}")
    if result["usable"]:
        print("result: usable raster MBTiles for viz1090")
    elif result["kind"] == "vector":
        print("result: vector MBTiles; render/export to raster MBTiles before using with viz1090")
    else:
        print("result: unsupported or unknown tile format")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect an MBTiles file and verify whether viz1090 can render it."
    )
    parser.add_argument("path", help="MBTiles file to inspect")
    parser.add_argument("--quiet", action="store_true", help="Only set the exit status")
    args = parser.parse_args(argv)

    try:
        result = inspect_mbtiles(args.path)
    except InspectionError as exc:
        if not args.quiet:
            print(f"{args.path}: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print_report(result)

    return 0 if result["usable"] else 2


if __name__ == "__main__":
    sys.exit(main())
