#!/usr/bin/env python3
import argparse
import json
import os
import select
import socket
import sys
import termios
import time
from pathlib import Path


DEFAULT_DEVICES = (
    "/dev/serial/by-id/usb-ClockworkPI_uConsole_20230713-if01",
    "/dev/ttyACM0",
    "/dev/ttyUSB0",
    "/dev/ttyAMA0",
)


def nmea_coord(raw_value, hemisphere):
    if not raw_value or not hemisphere:
        raise ValueError("empty coordinate")

    dot = raw_value.find(".")
    if dot < 0:
        dot = len(raw_value)

    degree_len = dot - 2
    if degree_len <= 0:
        raise ValueError("invalid coordinate")

    degrees = float(raw_value[:degree_len])
    minutes = float(raw_value[degree_len:])
    value = degrees + minutes / 60.0

    if hemisphere in ("S", "W"):
        value *= -1.0

    return value


def parse_nmea_fix(line):
    line = line.strip()
    if not line.startswith("$"):
        return None

    fields = line.split("*", 1)[0].split(",")
    sentence = fields[0][3:]

    if sentence == "GGA" and len(fields) >= 7:
        quality = fields[6]
        if quality and quality != "0":
            return nmea_coord(fields[2], fields[3]), nmea_coord(fields[4], fields[5])

    if sentence == "RMC" and len(fields) >= 7:
        status = fields[2]
        if status == "A":
            return nmea_coord(fields[3], fields[4]), nmea_coord(fields[5], fields[6])

    return None


def read_gpsd(timeout):
    deadline = time.monotonic() + timeout

    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=min(timeout, 2.0)) as sock:
            sock.sendall(b'?WATCH={"enable":true,"json":true};\n')
            sock.setblocking(False)
            buffer = ""

            while time.monotonic() < deadline:
                readable, _, _ = select.select([sock], [], [], 0.25)
                if not readable:
                    continue

                chunk = sock.recv(4096)
                if not chunk:
                    break

                buffer += chunk.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if message.get("class") == "TPV" and message.get("mode", 0) >= 2:
                        lat = message.get("lat")
                        lon = message.get("lon")
                        if lat is not None and lon is not None:
                            return float(lat), float(lon)
    except OSError:
        return None

    return None


def configure_serial(fd, baud):
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = attrs[2] | termios.CLOCAL | termios.CREAD
    attrs[3] = 0

    speed = getattr(termios, "B%d" % baud, termios.B9600)
    attrs[4] = speed
    attrs[5] = speed
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def read_serial_device(device, timeout, baud):
    path = Path(device)
    if not path.exists():
        return None

    deadline = time.monotonic() + timeout

    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError:
        return None

    try:
        configure_serial(fd, baud)
        buffer = b""

        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], 0.25)
            if not readable:
                continue

            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                continue

            if not chunk:
                continue

            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                line = raw_line.decode("ascii", errors="ignore")
                fix = parse_nmea_fix(line)
                if fix:
                    return fix
    finally:
        os.close(fd)

    return None


def read_serial(devices, timeout, baud):
    per_device_timeout = max(1.0, timeout / max(1, len(devices)))
    for device in devices:
        fix = read_serial_device(device, per_device_timeout, baud)
        if fix:
            return fix
    return None


def build_parser():
    parser = argparse.ArgumentParser(description="Read one GPS fix from gpsd or NMEA serial")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--device", action="append", default=[])
    parser.add_argument("--serial-only", action="store_true")
    parser.add_argument("--gpsd-only", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    devices = args.device or list(DEFAULT_DEVICES)

    fix = None
    if not args.serial_only:
        fix = read_gpsd(args.timeout)

    if fix is None and not args.gpsd_only:
        fix = read_serial(devices, args.timeout, args.baud)

    if fix is None:
        return 1

    print("%.6f %.6f" % fix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
