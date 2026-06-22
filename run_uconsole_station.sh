#!/usr/bin/env bash
set -euo pipefail

LAT="40.723972"
LON="-73.845139"
TILES=""
TILES_DIR="mapdata/tiles"
USE_TILES=1
TILES_EXPLICIT=0
MAP_TILE_PROFILE="auto"
MAP_PROFILE="us-hd"
WEATHER_BBOX="-75,39.8,-71.8,42.2"
WEATHER_PROFILE="regional"
NETWORK_ZOOM="6"
NETWORK_MIN_ZOOM="5"
NETWORK_CELL_PIXELS="3"
NETWORK_MIN_COVERAGE="0.08"
WEATHER_INTERVAL="300"
WEATHER_MIN_PIXELS="3"
FLOCK=1
FLOCK_DIR="mapdata/flock"
FLOCK_MAX_POINTS="5000"
TILE_MAX_ZOOM="13"
TILE_MIN_BYTES="2048"
TILE_OPACITY="204"
WEATHER=1
RF_WEATHER=0
GPS=1
DEBUG_WEATHER=0
FIT_WEATHER=0
REGEN_MAP=0
SCREENSHOT_FILE=""
SCREENSHOT_DELAY_MS="3000"
SCREENSHOT_EXIT=0
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
  --tiles <path>              Raster MBTiles file. Overrides profile selection.
  --tiles-dir <path>          Raster MBTiles directory. Default: mapdata/tiles
  --no-tiles                  Use generated vector map only.
  --map-tile-profile <name>   auto, conus-overview, northeast, nyc, etc. Default: auto
  --map-profile <name>        Passed to run_uconsole.sh. Default: us-hd
  --lat <value>               Fallback latitude. Default: 40.723972
  --lon <value>               Fallback longitude. Default: -73.845139
  --gps / --no-gps            Let run_uconsole.sh try GPS. Default: --gps
  --weather-profile <name>    auto/regional, national, local, or custom. Default: regional
  --weather-bbox <bbox>       lon_min,lat_min,lon_max,lat_max. Overrides profile.
  --network-zoom <z>          RainViewer fetch zoom. Default: profile-specific
  --network-min-zoom <z>      Lowest fallback zoom if higher zoom is unsupported. Default: profile-specific
  --network-cell-pixels <n>   Radar output cell size. Default: 3
  --network-min-coverage <n>  Minimum precip coverage per cell. Default: 0.08
  --weather-min-pixels <n>    Minimum rendered radar cell size. Default: 3
  --flock / --no-flock        Draw local FLOCK/surveillance overlay when available. Default: --flock
  --flock-dir <path>          Local FLOCK overlay directory. Default: mapdata/flock
  --flock-max-points <n>      Maximum FLOCK points drawn per frame. Default: 5000
  --tile-max-zoom <z>         Maximum raster basemap zoom. Default: 13
  --tile-min-bytes <n>        Skip tiny MBTiles placeholders below n bytes. Default: 2048
  --tile-opacity <0-255>      Raster basemap opacity. Default: 204
  --rf-weather                Try RF UAT/FIS-B before network fallback.
  --no-weather                Start app without the weather updater.
  --debug-weather             Print radar load/render diagnostics.
  --fit-weather               Center and zoom to the first loaded radar cache.
  --screenshot-file <path>    Save one renderer screenshot as BMP.
  --screenshot-delay-ms <ms>  Delay before screenshot capture. Default: 3000
  --screenshot-exit           Exit after saving screenshot.
  --regen-map                 Regenerate generated map data.
  --help                      Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tiles)
            TILES="$2"
            USE_TILES=1
            TILES_EXPLICIT=1
            shift 2
            ;;
        --tiles-dir)
            TILES_DIR="$2"
            shift 2
            ;;
        --no-tiles)
            USE_TILES=0
            shift
            ;;
        --map-tile-profile)
            MAP_TILE_PROFILE="$2"
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
            WEATHER_PROFILE="custom"
            shift 2
            ;;
        --weather-profile)
            WEATHER_PROFILE="$2"
            shift 2
            ;;
        --network-zoom)
            NETWORK_ZOOM="$2"
            WEATHER_PROFILE="custom"
            shift 2
            ;;
        --network-min-zoom)
            NETWORK_MIN_ZOOM="$2"
            WEATHER_PROFILE="custom"
            shift 2
            ;;
        --network-cell-pixels)
            NETWORK_CELL_PIXELS="$2"
            WEATHER_PROFILE="custom"
            shift 2
            ;;
        --network-min-coverage)
            NETWORK_MIN_COVERAGE="$2"
            WEATHER_PROFILE="custom"
            shift 2
            ;;
        --weather-min-pixels)
            WEATHER_MIN_PIXELS="$2"
            shift 2
            ;;
        --flock)
            FLOCK=1
            shift
            ;;
        --no-flock)
            FLOCK=0
            shift
            ;;
        --flock-dir)
            FLOCK_DIR="$2"
            shift 2
            ;;
        --flock-max-points)
            FLOCK_MAX_POINTS="$2"
            shift 2
            ;;
        --tile-max-zoom)
            TILE_MAX_ZOOM="$2"
            shift 2
            ;;
        --tile-min-bytes)
            TILE_MIN_BYTES="$2"
            shift 2
            ;;
        --tile-opacity)
            TILE_OPACITY="$2"
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
        --screenshot-file)
            SCREENSHOT_FILE="$2"
            shift 2
            ;;
        --screenshot-delay-ms)
            SCREENSHOT_DELAY_MS="$2"
            shift 2
            ;;
        --screenshot-exit)
            SCREENSHOT_EXIT=1
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

if [[ "${USE_TILES}" -eq 1 && "${TILES_EXPLICIT}" -eq 0 ]]; then
    if [[ "${MAP_TILE_PROFILE}" == "auto" ]]; then
        if selected="$(python3 tools/coverage_profiles.py select-map --lat "${LAT}" --lon "${LON}" --tiles-dir "${TILES_DIR}")"; then
            TILES="${selected}"
            echo "Selected raster map ${TILES}"
        else
            TILES=""
            echo "No installed raster map profile matched; continuing with generated vector map only." >&2
        fi
    else
        TILES="$(python3 tools/coverage_profiles.py map-path "${MAP_TILE_PROFILE}" --tiles-dir "${TILES_DIR}")"
    fi
fi

if [[ "${WEATHER_PROFILE}" != "custom" ]]; then
    while IFS='=' read -r key value; do
        case "${key}" in
            WEATHER_BBOX) WEATHER_BBOX="${value}" ;;
            NETWORK_ZOOM) NETWORK_ZOOM="${value}" ;;
            NETWORK_MIN_ZOOM) NETWORK_MIN_ZOOM="${value}" ;;
            NETWORK_CELL_PIXELS) NETWORK_CELL_PIXELS="${value}" ;;
            NETWORK_MIN_COVERAGE) NETWORK_MIN_COVERAGE="${value}" ;;
            WEATHER_INTERVAL) WEATHER_INTERVAL="${value}" ;;
        esac
    done < <(python3 tools/coverage_profiles.py weather --profile "${WEATHER_PROFILE}" --lat "${LAT}" --lon "${LON}" --shell)
fi

weather_args=(
    --lat "${LAT}"
    --lon "${LON}"
    --weather-bbox="${WEATHER_BBOX}"
    --network-zoom "${NETWORK_ZOOM}"
    --network-min-zoom "${NETWORK_MIN_ZOOM}"
    --network-cell-pixels "${NETWORK_CELL_PIXELS}"
    --network-min-coverage "${NETWORK_MIN_COVERAGE}"
    --min-interval "${WEATHER_INTERVAL}"
    --max-interval "${WEATHER_INTERVAL}"
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
    --map-profile "${MAP_PROFILE}"
    --lat "${LAT}"
    --lon "${LON}"
    --weather-min-pixels "${WEATHER_MIN_PIXELS}"
    --tile-max-zoom "${TILE_MAX_ZOOM}"
    --tile-min-bytes "${TILE_MIN_BYTES}"
    --tile-opacity "${TILE_OPACITY}"
)

if [[ "${USE_TILES}" -eq 1 && -n "${TILES}" ]]; then
    app_args=(
        --osm-mode
        --tiles "${TILES}"
        "${app_args[@]}"
    )
fi

if [[ "${GPS}" -eq 0 ]]; then
    app_args+=(--no-gps)
fi
if [[ "${DEBUG_WEATHER}" -eq 1 ]]; then
    app_args+=(--debug-weather)
fi
if [[ "${FIT_WEATHER}" -eq 1 ]]; then
    app_args+=(--fit-weather)
fi
if [[ "${FLOCK}" -eq 1 && -d "${FLOCK_DIR}" ]]; then
    app_args+=(--flock-dir "${FLOCK_DIR}" --flock-max-points "${FLOCK_MAX_POINTS}")
fi
if [[ "${REGEN_MAP}" -eq 1 ]]; then
    app_args+=(--regen-map)
fi
if [[ -n "${SCREENSHOT_FILE}" ]]; then
    mkdir -p "$(dirname "${SCREENSHOT_FILE}")"
    app_args+=(--screenshot-file "${SCREENSHOT_FILE}" --screenshot-delay-ms "${SCREENSHOT_DELAY_MS}")
fi
if [[ "${SCREENSHOT_EXIT}" -eq 1 ]]; then
    app_args+=(--screenshot-exit)
fi

./run_uconsole.sh "${app_args[@]}" "${APP_EXTRA[@]}"
