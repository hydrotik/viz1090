#!/usr/bin/env bash
set -euo pipefail

DURATION="75"
INTERVAL="240"
LOOP=0
SERVICE_CONTROL=1
WEATHER_FILE="weather/radar_tiles.csv"
CAPTURE_LOG="weather/uat_messages.jsonl"
SDR="driver=rtlsdr"
EXTRA_ARGS=()

usage() {
    cat <<'EOF'
Usage: ./run_uat_weather_cycle.sh [options] [-- extra uat_weather_cycle.py args]

Temporarily retunes a single RTL-SDR from 1090 MHz ADS-B to 978 MHz UAT/FIS-B,
captures decoded dump978-fa JSON, updates the viz1090 weather cache when radar
tiles are recognized, then returns the receiver to ADS-B service.

Options:
  --duration <sec>       UAT capture duration. Default: 75
  --interval <sec>       Delay between captures in --loop mode. Default: 240
  --loop                 Repeat forever.
  --no-service-control   Do not stop/start dump1090-mutability.
  --weather-file <path>  Radar tile cache. Default: weather/radar_tiles.csv
  --capture-log <path>   Raw dump978-fa JSON log. Default: weather/uat_messages.jsonl
  --sdr <args>           SoapySDR device args. Default: driver=rtlsdr
  --help                 Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --loop)
            LOOP=1
            shift
            ;;
        --no-service-control)
            SERVICE_CONTROL=0
            shift
            ;;
        --weather-file)
            WEATHER_FILE="$2"
            shift 2
            ;;
        --capture-log)
            CAPTURE_LOG="$2"
            shift 2
            ;;
        --sdr)
            SDR="$2"
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

run_once() {
    args=(
        --duration "${DURATION}"
        --weather-file "${WEATHER_FILE}"
        --capture-log "${CAPTURE_LOG}"
        --sdr "${SDR}"
    )

    if [[ "${SERVICE_CONTROL}" -eq 1 ]]; then
        args+=(--service-control)
    fi

    python3 tools/uat_weather_cycle.py "${args[@]}" "${EXTRA_ARGS[@]}"
}

if [[ "${LOOP}" -eq 1 ]]; then
    while true; do
        run_once || true
        sleep "${INTERVAL}"
    done
else
    run_once
fi
