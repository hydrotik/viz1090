#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


TILE_KEYS = (
    ("lat_min", "lon_min", "lat_max", "lon_max"),
    ("latMin", "lonMin", "latMax", "lonMax"),
    ("south", "west", "north", "east"),
)


def run_command(command, check=False):
    print("+ %s" % " ".join(command), flush=True)
    return subprocess.run(command, check=check)


def service_command(action, service, use_sudo):
    command = ["systemctl", action, service]
    if use_sudo:
        command.insert(0, "sudo")
    return run_command(command)


def wait_for_port(host, port, timeout):
    deadline = time.monotonic() + timeout
    last_error = None

    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=1.0)
            sock.settimeout(1.0)
            return sock
        except OSError as error:
            last_error = error
            time.sleep(0.25)

    raise RuntimeError("could not connect to %s:%d: %s" % (host, port, last_error))


def parse_json_stream(sock, duration, capture_log):
    deadline = time.monotonic() + duration
    buffer = ""
    messages = 0

    if capture_log:
        capture_log.parent.mkdir(parents=True, exist_ok=True)
        log_handle = capture_log.open("a", encoding="utf-8")
    else:
        log_handle = None

    try:
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue

            if not chunk:
                break

            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                messages += 1
                if log_handle:
                    log_handle.write(line + "\n")
                    log_handle.flush()

                yield line
    finally:
        if log_handle:
            log_handle.close()

    print("captured %d UAT JSON message(s)" % messages)


def normalize_intensity(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip().lower()
        levels = {
            "light": 1,
            "moderate": 2,
            "heavy": 3,
            "extreme": 4,
            "vip1": 1,
            "vip2": 2,
            "vip3": 3,
            "vip4": 4,
        }
        if value in levels:
            return levels[value]

    try:
        intensity = int(float(value))
    except (TypeError, ValueError):
        return None

    if intensity < 1:
        return None

    return max(1, min(4, intensity))


def tile_from_dict(item):
    if not isinstance(item, dict):
        return None

    selected_keys = None
    for keys in TILE_KEYS:
        if all(key in item for key in keys):
            selected_keys = keys
            break

    if selected_keys is None:
        return None

    intensity = normalize_intensity(
        item.get("intensity", item.get("level", item.get("vip", item.get("precip"))))
    )
    if intensity is None:
        return None

    try:
        lat_min = float(item[selected_keys[0]])
        lon_min = float(item[selected_keys[1]])
        lat_max = float(item[selected_keys[2]])
        lon_max = float(item[selected_keys[3]])
    except (TypeError, ValueError):
        return None

    if lat_min > lat_max:
        lat_min, lat_max = lat_max, lat_min
    if lon_min > lon_max:
        lon_min, lon_max = lon_max, lon_min

    return lat_min, lon_min, lat_max, lon_max, intensity


def extract_tiles(value):
    tiles = []

    direct_tile = tile_from_dict(value)
    if direct_tile:
        return [direct_tile]

    if isinstance(value, dict):
        for child in value.values():
            tiles.extend(extract_tiles(child))
    elif isinstance(value, list):
        for child in value:
            tiles.extend(extract_tiles(child))

    return tiles


def write_tiles(path, tiles, write_empty=False):
    if not tiles and not write_empty:
        print("no recognized radar tile records; leaving existing %s unchanged" % path)
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write("# lat_min,lon_min,lat_max,lon_max,intensity\n")
        for tile in tiles:
            handle.write("%.6f,%.6f,%.6f,%.6f,%d\n" % tile)

    temp_path.replace(path)
    print("wrote %d radar tile(s) to %s" % (len(tiles), path))
    return len(tiles)


def collect_weather(args):
    dump978_bin = shutil.which(args.dump978_bin)
    if not dump978_bin:
        raise RuntimeError(
            "%s not found. Install/build dump978-fa first; see README.md." % args.dump978_bin
        )

    command = [
        dump978_bin,
        "--sdr",
        args.sdr,
        "--json-port",
        str(args.json_port),
    ]
    if args.raw_port:
        command.extend(["--raw-port", str(args.raw_port)])
    for extra_arg in args.dump978_arg:
        command.append(extra_arg)

    process = subprocess.Popen(command)
    try:
        with wait_for_port(args.host, args.json_port, args.startup_timeout) as sock:
            tiles = []
            for line in parse_json_stream(sock, args.duration, Path(args.capture_log) if args.capture_log else None):
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tiles.extend(extract_tiles(message))

        write_tiles(Path(args.weather_file), tiles, args.write_empty)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def build_parser():
    parser = argparse.ArgumentParser(description="Capture UAT/FIS-B weather and update viz1090 radar cache")
    parser.add_argument("--duration", type=float, default=75.0, help="seconds to listen on 978 MHz")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--json-port", type=int, default=30978)
    parser.add_argument("--raw-port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=10.0)
    parser.add_argument("--dump978-bin", default="dump978-fa")
    parser.add_argument("--dump978-arg", action="append", default=[])
    parser.add_argument("--sdr", default="driver=rtlsdr")
    parser.add_argument("--weather-file", default="weather/radar_tiles.csv")
    parser.add_argument("--capture-log", default="weather/uat_messages.jsonl")
    parser.add_argument("--write-empty", action="store_true", help="overwrite weather file even when no radar tiles are decoded")
    parser.add_argument("--service", default="dump1090-mutability")
    parser.add_argument("--service-control", action="store_true", help="stop/start ADS-B service around UAT capture")
    parser.add_argument("--no-sudo", action="store_true", help="do not prefix service commands with sudo")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    use_sudo = not args.no_sudo

    try:
        if args.service_control:
            service_command("stop", args.service, use_sudo)

        return collect_weather(args)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print("uat weather capture failed: %s" % error, file=sys.stderr)
        return 1
    finally:
        if args.service_control:
            service_command("start", args.service, use_sudo)


if __name__ == "__main__":
    raise SystemExit(main())
