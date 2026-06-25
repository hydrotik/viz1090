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
TILE_MAX_ZOOM="16"
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
ACTION="run"
STOP_FIRST=0
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
  --tile-max-zoom <z>         Maximum raster basemap zoom. Default: 16
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
  --status                    Print station health and exit.
  --stop                      Stop viz1090 station/app/weather processes and exit.
  --restart                   Stop existing station processes before starting.
  --help                      Show this help.
EOF
}

process_rows() {
    local output
    output="$(ps -eo pid=,args= 2>/dev/null || true)"
    [[ -z "${output}" ]] && return 0
    printf '%s\n' "${output}" | while read -r pid args; do
        [[ -z "${pid}" || "${pid}" == "$$" || "${pid}" == "${BASHPID:-}" ]] && continue
        case "${args}" in
            *"run_uconsole_station.sh --status"*|*"run_uconsole_station.sh --stop"*)
                ;;
            *"./viz1090"*|*"run_uconsole.sh"*|*"run_uconsole_station.sh"*|*"run_weather_hybrid_cycle.sh"*|*"tools/weather_hybrid_cycle.py"*)
                printf '%s\t%s\n' "${pid}" "${args}"
                ;;
        esac
    done
}

print_file_age() {
    local path="$1"
    if [[ ! -f "${path}" ]]; then
        echo "missing"
        return
    fi
    python3 -c 'import os, sys, time; p=sys.argv[1]; age=max(0, int(time.time()-os.path.getmtime(p))); print(f"{age}s old")' "${path}" 2>/dev/null || echo "present"
}

print_status() {
    echo "viz1090 station status"
    echo
    echo "Processes:"
    if ! process_rows | sed 's/^/  /'; then
        true
    fi
    if [[ -z "$(process_rows)" ]]; then
        echo "  none"
    fi
    echo
    echo "Map tiles:"
    if [[ -d "${TILES_DIR}" ]]; then
        if selected="$(python3 tools/coverage_profiles.py select-map --lat "${LAT}" --lon "${LON}" --tiles-dir "${TILES_DIR}" 2>/dev/null)"; then
            size="$(du -h "${selected}" 2>/dev/null | awk '{print $1}')"
            echo "  selected: ${selected}${size:+ (${size})}"
        else
            echo "  selected: none for ${LAT}, ${LON}"
        fi
        echo "  directory: ${TILES_DIR}"
        df -h "${TILES_DIR}" 2>/dev/null | awk 'NR==2 {print "  disk: "$4" free of "$2" ("$5" used)"}'
    else
        echo "  directory missing: ${TILES_DIR}"
    fi
    echo
    echo "Weather:"
    echo "  cache: weather/radar_tiles.csv ($(print_file_age weather/radar_tiles.csv))"
    if [[ -f weather/radar_tiles.csv ]]; then
        echo "  rows: $(wc -l < weather/radar_tiles.csv | tr -d ' ')"
    fi
    echo
    echo "FLOCK:"
    if [[ -d "${FLOCK_DIR}" ]]; then
        echo "  directory: ${FLOCK_DIR}"
        echo "  tile files: $(find "${FLOCK_DIR}" -name '*.csv' 2>/dev/null | wc -l | tr -d ' ')"
    else
        echo "  directory missing: ${FLOCK_DIR}"
    fi
}

stop_station() {
    local rows pids pid
    rows="$(process_rows || true)"
    if [[ -z "${rows}" ]]; then
        echo "No viz1090 station processes found."
        return 0
    fi
    echo "Stopping viz1090 station processes:"
    printf '%s\n' "${rows}" | sed 's/^/  /'
    pids="$(printf '%s\n' "${rows}" | awk '{print $1}')"
    for pid in ${pids}; do
        kill "${pid}" >/dev/null 2>&1 || true
    done
    sleep 1
    for pid in ${pids}; do
        if kill -0 "${pid}" >/dev/null 2>&1; then
            kill -TERM "${pid}" >/dev/null 2>&1 || true
        fi
    done
}

warn_low_disk() {
    local path="$1"
    local free_kb
    [[ -d "${path}" ]] || return 0
    free_kb="$(df -Pk "${path}" 2>/dev/null | awk 'NR==2 {print $4}')"
    [[ -n "${free_kb}" ]] || return 0
    if (( free_kb < 2097152 )); then
        echo "Warning: less than 2 GB free on filesystem for ${path}; tile/weather updates may fail." >&2
        df -h "${path}" >&2 || true
    fi
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
        --status)
            ACTION="status"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --restart)
            STOP_FIRST=1
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

if [[ "${ACTION}" == "status" ]]; then
    print_status
    exit 0
fi

if [[ "${ACTION}" == "stop" ]]; then
    stop_station
    exit 0
fi

if [[ "${STOP_FIRST}" -eq 1 ]]; then
    stop_station
fi

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
warn_low_disk "."
warn_low_disk "${TILES_DIR}"

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
