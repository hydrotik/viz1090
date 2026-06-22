#!/usr/bin/env bash
set -euo pipefail

LAT="40.723972"
LON="-73.845139"
GPS=1
GPS_TIMEOUT="20"
GPS_DEVICE=""
GPS_POWER=1
GPS_POWER_GPIO="27"
WEATHER_FILE="weather/radar_tiles.csv"
CAPTURE_LOG="weather/uat_messages.jsonl"
SDR="driver=rtlsdr,serial=25062501"
RF_DURATION="90"
MIN_INTERVAL="240"
MAX_INTERVAL="1800"
WEATHER_BBOX="-125,24,-66,50"
NETWORK_ZOOM="5"
NETWORK_MIN_ZOOM="5"
NETWORK_SIZE="512"
NETWORK_CELL_PIXELS="6"
NETWORK_MIN_COVERAGE="0.15"
NETWORK_SMOOTH="1"
NETWORK=1
NO_RF=0
NETWORK_PRESERVE_EMPTY=0
ONCE=0
EXTRA_ARGS=()

usage() {
    cat <<'EOF'
Usage: ./run_weather_hybrid_cycle.sh [options] [-- extra weather_hybrid_cycle.py args]

Updates viz1090 weather using RF UAT/FIS-B first. If RF is quiet, it falls
back to internet radar when available and backs off RF sampling intervals.

Options:
  --lat <value>          Fallback latitude. Default: 40.723972
  --lon <value>          Fallback longitude. Default: -73.845139
  --gps                  Try GPS first, falling back to --lat/--lon. Default.
  --no-gps               Do not try GPS.
  --gps-power            Try enabling GPS power GPIO before reading GPS. Default.
  --no-gps-power         Do not touch GPS power GPIO.
  --gps-power-gpio <n>   GPS enable GPIO. Default: 27
  --gps-device <path>    Add a GPS serial device path to try.
  --gps-timeout <sec>    GPS fix timeout. Default: 20
  --weather-file <path>  Radar tile cache. Default: weather/radar_tiles.csv
  --capture-log <path>   Raw dump978-fa JSON log. Default: weather/uat_messages.jsonl
  --sdr <args>           SoapySDR device args. Default: driver=rtlsdr,serial=25062501
  --rf-duration <sec>    UAT/FIS-B sample window. Default: 90
  --min-interval <sec>   Minimum repeat interval. Default: 240
  --max-interval <sec>   Maximum RF retry interval after misses. Default: 1800
  --weather-bbox <bbox>  Network radar bbox lon_min,lat_min,lon_max,lat_max.
                         Default: -125,24,-66,50
  --local-weather        Fetch network radar around current location instead of bbox.
  --network-zoom <z>     Network radar zoom. Default: 5 for bbox coverage.
  --network-min-zoom <z> Lowest network radar zoom fallback. Default: 5
  --network-size <px>    Network radar source tile size, 256 or 512. Default: 512
  --network-cell-pixels <n> Radar output cell size in source pixels. Default: 6
  --network-min-coverage <n> Minimum precipitation coverage per cell. Default: 0.15
  --network-smooth <0|1> RainViewer smoothing. Default: 1
  --no-rf                Skip UAT/FIS-B and fetch network radar only.
  --no-network           Do not use internet fallback.
  --network-preserve-empty Preserve existing radar cache when network returns no precip.
  --once                 Run one RF/network update cycle and exit.
  --help                 Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --lat)
            LAT="$2"
            shift 2
            ;;
        --lon)
            LON="$2"
            shift 2
            ;;
        --gps)
            GPS=1
            shift
            ;;
        --no-gps)
            GPS=0
            shift
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
        --gps-device)
            GPS_DEVICE="$2"
            shift 2
            ;;
        --gps-timeout)
            GPS_TIMEOUT="$2"
            shift 2
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
        --rf-duration)
            RF_DURATION="$2"
            shift 2
            ;;
        --min-interval)
            MIN_INTERVAL="$2"
            shift 2
            ;;
        --max-interval)
            MAX_INTERVAL="$2"
            shift 2
            ;;
        --weather-bbox)
            WEATHER_BBOX="$2"
            shift 2
            ;;
        --local-weather)
            WEATHER_BBOX=""
            NETWORK_ZOOM="7"
            shift
            ;;
        --network-zoom)
            NETWORK_ZOOM="$2"
            shift 2
            ;;
        --network-min-zoom)
            NETWORK_MIN_ZOOM="$2"
            shift 2
            ;;
        --network-size)
            NETWORK_SIZE="$2"
            shift 2
            ;;
        --network-cell-pixels)
            NETWORK_CELL_PIXELS="$2"
            shift 2
            ;;
        --network-min-coverage)
            NETWORK_MIN_COVERAGE="$2"
            shift 2
            ;;
        --network-smooth)
            NETWORK_SMOOTH="$2"
            shift 2
            ;;
        --no-rf)
            NO_RF=1
            shift
            ;;
        --no-network)
            NETWORK=0
            shift
            ;;
        --network-preserve-empty)
            NETWORK_PRESERVE_EMPTY=1
            shift
            ;;
        --once)
            ONCE=1
            shift
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

if [[ "${GPS}" -eq 1 ]]; then
    if [[ "${GPS_POWER}" -eq 1 ]]; then
        if command -v pinctrl >/dev/null 2>&1; then
            pinctrl "${GPS_POWER_GPIO}" op && pinctrl "${GPS_POWER_GPIO}" dh || true
        fi
    fi

    gps_args=(--timeout "${GPS_TIMEOUT}")
    if [[ -n "${GPS_DEVICE}" ]]; then
        gps_args+=(--device "${GPS_DEVICE}")
    fi

    if gps_fix="$(python3 tools/gps_fix.py "${gps_args[@]}")"; then
        LAT="$(printf '%s' "${gps_fix}" | awk '{print $1}')"
        LON="$(printf '%s' "${gps_fix}" | awk '{print $2}')"
        echo "Using GPS fix for weather: ${LAT}, ${LON}"
    else
        echo "No GPS fix found within ${GPS_TIMEOUT}s; using configured weather location: ${LAT}, ${LON}" >&2
    fi
fi

args=(
    --lat "${LAT}"
    --lon "${LON}"
    --weather-file "${WEATHER_FILE}"
    --capture-log "${CAPTURE_LOG}"
    --sdr "${SDR}"
    --rf-duration "${RF_DURATION}"
    --min-interval "${MIN_INTERVAL}"
    --max-interval "${MAX_INTERVAL}"
    --network-zoom "${NETWORK_ZOOM}"
    --network-min-zoom "${NETWORK_MIN_ZOOM}"
    --network-size "${NETWORK_SIZE}"
    --network-cell-pixels "${NETWORK_CELL_PIXELS}"
    --network-min-coverage "${NETWORK_MIN_COVERAGE}"
    --network-smooth "${NETWORK_SMOOTH}"
)

if [[ -n "${WEATHER_BBOX}" ]]; then
    args+=("--weather-bbox=${WEATHER_BBOX}")
fi
if [[ "${ONCE}" -eq 1 ]]; then
    args+=(--once)
fi
if [[ "${NO_RF}" -eq 1 ]]; then
    args+=(--no-rf)
fi
if [[ "${NETWORK}" -eq 0 ]]; then
    args+=(--no-network)
fi
if [[ "${NETWORK_PRESERVE_EMPTY}" -eq 1 ]]; then
    args+=(--network-preserve-empty)
fi

exec python3 tools/weather_hybrid_cycle.py "${args[@]}" "${EXTRA_ARGS[@]}"
