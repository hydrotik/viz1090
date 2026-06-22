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
    "/dev/serial0",
    "/dev/ttyS0",
    "/dev/ttyAMA0",
    "/dev/serial/by-id/usb-ClockworkPI_uConsole_20230713-if01",
    "/dev/ttyACM0",
    "/dev/ttyUSB0",
)


def describe_device(device):
    path = Path(device)
    if not path.exists():
        return "%s missing" % device
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    return "%s present -> %s" % (device, resolved)


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


def diagnose_gpsd(timeout):
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=min(timeout, 2.0)) as sock:
            sock.sendall(b'?WATCH={"enable":true,"json":true};\n')
            sock.setblocking(False)
            deadline = time.monotonic() + timeout
            buffer = ""
            print("gpsd: connected on 127.0.0.1:2947")

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
                    if message.get("class") == "TPV":
                        print("gpsd TPV: mode=%s lat=%s lon=%s" % (message.get("mode"), message.get("lat"), message.get("lon")))
                        if message.get("mode", 0) >= 2 and message.get("lat") is not None and message.get("lon") is not None:
                            return float(message["lat"]), float(message["lon"])
    except OSError as error:
        print("gpsd: unavailable (%s)" % error)

    return None


def diagnose_serial(devices, timeout, baud, raw_lines):
    per_device_timeout = max(1.0, timeout / max(1, len(devices)))

    for device in devices:
        print("serial: %s" % describe_device(device))
        path = Path(device)
        if not path.exists():
            continue

        deadline = time.monotonic() + per_device_timeout
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
        except OSError as error:
            print("serial: could not open %s (%s)" % (device, error))
            continue

        try:
            configure_serial(fd, baud)
            buffer = b""
            lines_seen = 0

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
                    line = raw_line.decode("ascii", errors="ignore").strip()
                    if not line:
                        continue
                    lines_seen += 1
                    if raw_lines > 0 and lines_seen <= raw_lines:
                        print("serial NMEA %s: %s" % (device, line[:140]))
                    fix = parse_nmea_fix(line)
                    if fix:
                        print("serial fix from %s: %.6f %.6f" % (device, fix[0], fix[1]))
                        return fix

            if lines_seen == 0:
                print("serial: no NMEA lines read from %s" % device)
            else:
                print("serial: read %d NMEA line(s) from %s but no valid fix yet" % (lines_seen, device))
        finally:
            os.close(fd)

    return None


def read_text_if_present(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def diagnose_boot_config():
    config_paths = ("/boot/firmware/config.txt", "/boot/config.txt")
    cmdline_paths = ("/boot/firmware/cmdline.txt", "/boot/cmdline.txt")

    config_text = ""
    config_path = ""
    for path in config_paths:
        config_text = read_text_if_present(path)
        if config_text:
            config_path = path
            break

    if config_text:
        interesting = []
        for line in config_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "enable_uart" in stripped or "dtparam=uart0" in stripped or "dtoverlay=uart" in stripped:
                interesting.append(stripped)
        if interesting:
            print("boot config %s UART lines: %s" % (config_path, "; ".join(interesting)))
        else:
            print("boot config %s: no active UART enable line found" % config_path)
    else:
        print("boot config: config.txt not readable/found")

    cmdline_text = ""
    cmdline_path = ""
    for path in cmdline_paths:
        cmdline_text = read_text_if_present(path)
        if cmdline_text:
            cmdline_path = path
            break

    if cmdline_text:
        serial_console = [item for item in cmdline_text.split() if item.startswith("console=serial")]
        if serial_console:
            print("boot cmdline %s serial console entries: %s" % (cmdline_path, " ".join(serial_console)))
            print("GPS warning: serial console can occupy the GPS UART; HackerGadgets says to remove console=serial0,115200 on CM4.")
        else:
            print("boot cmdline %s: no console=serial* entry found" % cmdline_path)
    else:
        print("boot cmdline: cmdline.txt not readable/found")


def diagnose(args, devices):
    diagnose_boot_config()

    fix = None
    if not args.serial_only:
        fix = diagnose_gpsd(args.timeout)

    if fix is None and not args.gpsd_only:
        fix = diagnose_serial(devices, args.timeout, args.baud, args.raw_lines)

    if fix:
        print("%.6f %.6f" % fix)
        return 0

    print("no GPS fix found")
    return 1


def build_parser():
    parser = argparse.ArgumentParser(description="Read one GPS fix from gpsd or NMEA serial")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--device", action="append", default=[])
    parser.add_argument("--serial-only", action="store_true")
    parser.add_argument("--gpsd-only", action="store_true")
    parser.add_argument("--diagnose", action="store_true", help="print gpsd/device/NMEA status while looking for a fix")
    parser.add_argument("--raw-lines", type=int, default=8, help="NMEA lines to print per serial device in diagnostic mode")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    devices = args.device or list(DEFAULT_DEVICES)

    if args.diagnose:
        return diagnose(args, devices)

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
