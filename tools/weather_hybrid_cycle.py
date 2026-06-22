#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
from pathlib import Path


def line_count(path):
    try:
        with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def run_command(command):
    print("+ %s" % " ".join(command), flush=True)
    return subprocess.run(command).returncode


def run_uat(args):
    before = line_count(args.capture_log)
    command = [
        args.uat_script,
        "--duration",
        str(args.rf_duration),
        "--weather-file",
        args.weather_file,
        "--capture-log",
        args.capture_log,
        "--sdr",
        args.sdr,
    ]
    status = run_command(command)
    after = line_count(args.capture_log)
    return status, max(0, after - before)


def run_network(args):
    command = [
        sys.executable,
        args.network_script,
        "--lat",
        str(args.lat),
        "--lon",
        str(args.lon),
        "--output",
        args.weather_file,
        "--zoom",
        str(args.network_zoom),
        "--min-zoom",
        str(args.network_min_zoom),
        "--size",
        str(args.network_size),
        "--cell-pixels",
        str(args.network_cell_pixels),
        "--min-coverage",
        str(args.network_min_coverage),
        "--smooth",
        str(args.network_smooth),
    ]
    if args.weather_bbox:
        command.append("--bbox=%s" % args.weather_bbox)
    if args.network_preserve_empty:
        command.append("--preserve-empty")
    return run_command(command)


def cycle(args):
    interval = args.min_interval
    miss_count = 0

    while True:
        rf_status = 0
        new_messages = 0

        if not args.no_rf:
            rf_status, new_messages = run_uat(args)

        if new_messages > 0:
            miss_count = 0
            interval = args.min_interval
            print("RF UAT capture decoded %d new message(s); next capture in %ds" % (new_messages, interval))
        else:
            miss_count += 1
            if args.network:
                network_status = run_network(args)
                if network_status == 0:
                    print("network radar fallback completed")
                else:
                    print("network radar fallback unavailable")

            interval = min(args.max_interval, max(args.min_interval, interval * 2))
            print("RF UAT quiet after %d miss(es); next capture in %ds" % (miss_count, interval))

        if args.once:
            return rf_status

        time.sleep(interval)


def build_parser():
    parser = argparse.ArgumentParser(description="Hybrid RF/network radar updater for viz1090")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--weather-file", default="weather/radar_tiles.csv")
    parser.add_argument("--capture-log", default="weather/uat_messages.jsonl")
    parser.add_argument("--sdr", default="driver=rtlsdr")
    parser.add_argument("--rf-duration", type=float, default=90.0)
    parser.add_argument("--min-interval", type=int, default=240)
    parser.add_argument("--max-interval", type=int, default=1800)
    parser.add_argument("--network", action="store_true", default=True)
    parser.add_argument("--no-network", action="store_false", dest="network")
    parser.add_argument("--network-zoom", type=int, default=5)
    parser.add_argument("--network-min-zoom", type=int, default=5)
    parser.add_argument("--network-size", type=int, choices=(256, 512), default=512)
    parser.add_argument("--network-cell-pixels", type=int, default=6)
    parser.add_argument("--network-min-coverage", type=float, default=0.15)
    parser.add_argument("--network-smooth", type=int, choices=(0, 1), default=1)
    parser.add_argument("--weather-bbox", default="")
    parser.add_argument("--network-preserve-empty", action="store_true")
    parser.add_argument("--no-rf", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--uat-script", default="./run_uat_weather_cycle.sh")
    parser.add_argument("--network-script", default="tools/network_weather.py")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return cycle(args)


if __name__ == "__main__":
    raise SystemExit(main())
