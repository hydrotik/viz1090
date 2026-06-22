#!/usr/bin/env bash
set -euo pipefail

TIMEOUT="60"
GPS_POWER=1
GPS_POWER_GPIO="27"
GPS_DEVICE=""
EXTRA_ARGS=()

usage() {
    cat <<'EOF'
Usage: ./run_gps_probe.sh [options] [-- extra gps_fix.py args]

Enables the uConsole GPS power GPIO when available, then prints gpsd, serial
device, raw NMEA, and fix status.

Options:
  --timeout <sec>       Probe duration. Default: 60
  --gps-device <path>   Add a GPS serial device path to try.
  --gps-power           Try enabling GPS power GPIO. Default.
  --no-gps-power        Do not touch GPS power GPIO.
  --gps-power-gpio <n>  GPS enable GPIO. Default: 27
  --help                Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --gps-device)
            GPS_DEVICE="$2"
            shift 2
            ;;
        --gps-power)
            GPS_POWER=1
            shift
            ;;
        --no-gps-power)
            GPS_POWER=0
            shift
            ;;
        --gps-power-gpio)
            GPS_POWER_GPIO="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        --)
            shift
            EXTRA_ARGS+=("$@")
            break
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ "${GPS_POWER}" -eq 1 ]]; then
    if command -v pinctrl >/dev/null 2>&1; then
        if pinctrl "${GPS_POWER_GPIO}" op && pinctrl "${GPS_POWER_GPIO}" dh; then
            echo "Enabled GPS power on GPIO ${GPS_POWER_GPIO}"
        else
            echo "Could not enable GPS power GPIO ${GPS_POWER_GPIO}; continuing with GPS probe." >&2
        fi
    else
        echo "pinctrl not found; continuing without GPIO power control." >&2
    fi
fi

args=(--diagnose --timeout "${TIMEOUT}")
if [[ -n "${GPS_DEVICE}" ]]; then
    args+=(--device "${GPS_DEVICE}")
fi

exec python3 tools/gps_fix.py "${args[@]}" "${EXTRA_ARGS[@]}"
