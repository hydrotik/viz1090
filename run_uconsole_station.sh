#!/usr/bin/env bash
set -euo pipefail

LAT="40.723972"
LON="-73.845139"
TILES="mapdata/tiles/nyc-raster.mbtiles"
MAP_PROFILE="us-hd"
WEATHER_BBOX="-75,39.8,-71.8,42.2"
NETWORK_ZOOM="8"
NETWORK_CELL_PIXELS="3"
NETWORK_MIN_COVERAGE="0.08"
WEATHER_MIN_PIXELS="3"
WEATHER=1
RF_WEATHER=0
GPS=1
DEBUG_WEATHER=0
FIT_WEATHER=0
REGEN_MAP=0
APP_EXTRA=()

usage() {
    cat <<'EOF'
Usage: ./run_uconsole_station.sh [options] [-- extra run_uconsole.sh args]

One-command uConsole workflow:
  1. build viz1090 when needed
  2. fetch one network radar snapshot
  3. keep the weather updater running in the background
  4. start viz1090 with offline raster tiles, ADS-B, and weather overlay
  5. stop the background weather updater when viz1090 exits

Options:
  --tiles <path>              Raster MBTiles file. Default: mapdata/tiles/nyc-raster.mbtiles
  --map-profile <name>        Passed to run_uconsole.sh. Default: us-hd
  --lat <value>               Fallback latitude. Default: 40.723972
  --lon <value>               Fallback longitude. Default: -73.845139
  --gps / --no-gps            Let run_uconsole.sh try GPS. Default: --gps
  --weather-bbox <bbox>       lon_min,lat_min,lon_max,lat_max. Default: NYC metro
  --network-zoom <z>          RainViewer fetch zoom. Default: 8
  --network-cell-pixels <n>   Radar output cell size. Default: 3
  --network-min-coverage <n>  Minimum precip coverage per cell. Default: 0.08
  --weather-min-pixels <n>    Minimum rendered radar cell size. Default: 3
  --rf-weather                Try RF UAT/FIS-B before network fallback.
  --no-weather                Start app without the weather updater.
  --debug-weather             Print radar load/render diagnostics.
  --fit-weather               Center and zoom to the first loaded radar cache.
  --regen-map                 Regenerate generated map data.
  --help                      Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tiles)
            TILES="$2"
            shift 2
            ;;
        --map-profile)
            MAP_PROFILE="$2"
            shift 2
            ;;
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
        --weather-bbox)
            WEATHER_BBOX="$2"
            shift 2
            ;;
        --network-zoom)
            NETWORK_ZOOM="$2"
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
        --weather-min-pixels)
            WEATHER_MIN_PIXELS="$2"
            shift 2
            ;;
        --rf-weather)
            RF_WEATHER=1
            shift
            ;;
        --no-weather)
            WEATHER=0
            shift
            ;;
        --debug-weather)
            DEBUG_WEATHER=1
            shift
            ;;
        --fit-weather)
            FIT_WEATHER=1
            shift
            ;;
        --regen-map)
            REGEN_MAP=1
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        --)
            shift
            APP_EXTRA+=("$@")
            break
            ;;
        *)
            APP_EXTRA+=("$1")
            shift
            ;;
    esac
done

weather_pid=""
cleanup() {
    if [[ -n "${weather_pid}" ]] && kill -0 "${weather_pid}" >/dev/null 2>&1; then
        kill "${weather_pid}" >/dev/null 2>&1 || true
        wait "${weather_pid}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

make viz1090
mkdir -p weather

weather_args=(
    --lat "${LAT}"
    --lon "${LON}"
    --weather-bbox="${WEATHER_BBOX}"
    --network-zoom "${NETWORK_ZOOM}"
    --network-cell-pixels "${NETWORK_CELL_PIXELS}"
    --network-min-coverage "${NETWORK_MIN_COVERAGE}"
    --min-interval 300
    --max-interval 300
)

if [[ "${RF_WEATHER}" -eq 0 ]]; then
    weather_args+=(--no-rf)
fi

if [[ "${WEATHER}" -eq 1 ]]; then
    echo "Refreshing weather cache..."
    ./run_weather_hybrid_cycle.sh --no-gps --once "${weather_args[@]}" || true
    ./run_weather_hybrid_cycle.sh --no-gps "${weather_args[@]}" &
    weather_pid="$!"
    echo "Weather updater started as PID ${weather_pid}"
fi

app_args=(
    --osm-mode
    --tiles "${TILES}"
    --map-profile "${MAP_PROFILE}"
    --lat "${LAT}"
    --lon "${LON}"
    --weather-min-pixels "${WEATHER_MIN_PIXELS}"
)

if [[ "${GPS}" -eq 0 ]]; then
    app_args+=(--no-gps)
fi
if [[ "${DEBUG_WEATHER}" -eq 1 ]]; then
    app_args+=(--debug-weather)
fi
if [[ "${FIT_WEATHER}" -eq 1 ]]; then
    app_args+=(--fit-weather)
fi
if [[ "${REGEN_MAP}" -eq 1 ]]; then
    app_args+=(--regen-map)
fi

./run_uconsole.sh "${app_args[@]}" "${APP_EXTRA[@]}"
