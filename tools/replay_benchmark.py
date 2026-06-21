#!/usr/bin/env python3
import argparse
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


def read_hex_messages(path):
    messages = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        messages.append(bytes.fromhex(line))
    return messages


def beast_escape(payload):
    return payload.replace(b"\x1a", b"\x1a\x1a")


def beast_frame(message, timestamp=0, signal=0x7f):
    if len(message) != 14:
        raise ValueError("Only long DF17/DF18 Beast fixtures are supported by this replay helper")

    timestamp_bytes = timestamp.to_bytes(6, byteorder="big", signed=False)
    return b"\x1a3" + beast_escape(timestamp_bytes + bytes([signal]) + message)


def serve_frames(host, port, frames, duration, rate_hz, errors):
    deadline = time.monotonic() + duration
    interval = 1.0 / rate_hz if rate_hz > 0 else 0.0

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((host, port))
            server.listen(1)
            server.settimeout(duration)

            try:
                conn, _addr = server.accept()
            except socket.timeout:
                errors.append("viz1090 did not connect to replay server")
                return

            with conn:
                idx = 0
                while time.monotonic() < deadline:
                    conn.sendall(frames[idx % len(frames)])
                    idx += 1
                    if interval:
                        time.sleep(interval)
    except OSError as exc:
        errors.append(str(exc))


def run_benchmark(args):
    messages = read_hex_messages(args.fixtures)
    if not messages:
        raise RuntimeError("No fixture messages found")

    frames = [beast_frame(message, timestamp=i) for i, message in enumerate(messages)]

    if args.check_fixture:
        print("loaded %d Beast fixture frame(s)" % len(frames))
        return 0

    if not Path(args.viz).exists():
        print("%s does not exist; build viz1090 first" % args.viz, file=sys.stderr)
        return 1

    server_errors = []
    server = threading.Thread(
        target=serve_frames,
        args=(args.host, args.port, frames, args.duration, args.rate, server_errors),
        daemon=True,
    )
    server.start()

    env = os.environ.copy()
    if args.dummy_video:
        env.setdefault("SDL_VIDEODRIVER", "dummy")

    command = [
        args.viz,
        "--server", args.host,
        "--port", str(args.port),
        "--screensize", str(args.width), str(args.height),
        "--mapdir", args.mapdir,
        "--theme", args.theme,
        "--lat", str(args.lat),
        "--lon", str(args.lon),
        "--fps",
    ]

    extra_args = args.extra_args
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    command.extend(extra_args)

    start = time.monotonic()
    proc = subprocess.Popen(command, env=env)

    try:
        proc.wait(timeout=args.duration)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    elapsed = time.monotonic() - start
    server.join(timeout=1)

    if server_errors:
        print("replay server failed: %s" % "; ".join(server_errors), file=sys.stderr)
        return 1

    if proc.returncode not in (0, -15):
        print("viz1090 exited with status %s after %.2fs" % (proc.returncode, elapsed), file=sys.stderr)
        return 1

    print("replay benchmark smoke completed in %.2fs" % elapsed)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Replay Beast fixtures into viz1090 for smoke/perf testing")
    parser.add_argument("--fixtures", default="tests/fixtures/beast_messages.hex")
    parser.add_argument("--viz", default="./viz1090")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=30005)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--rate", type=float, default=20.0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--lat", type=float, default=47.6)
    parser.add_argument("--lon", type=float, default=-122.3)
    parser.add_argument("--mapdir", default=".")
    parser.add_argument("--theme", default="atc", choices=["classic", "atc", "map", "light"])
    parser.add_argument("--dummy-video", action="store_true", default=True)
    parser.add_argument("--check-fixture", action="store_true")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    return parser


if __name__ == "__main__":
    sys.exit(run_benchmark(build_parser().parse_args()))
