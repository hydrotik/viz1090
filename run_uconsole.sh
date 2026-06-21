#!/usr/bin/env bash
set -euo pipefail

LAT="40.723972"
LON="-73.845139"
GPS=1
GPS_TIMEOUT="8"
GPS_DEVICE=""
GPS_POWER=1
GPS_POWER_GPIO="27"
BBOX="-75,39.8,-71.8,42.2"
MAP_DIR="mapdata/generated/nyc"
WEATHER_FILE="weather/radar_tiles.csv"
THEME="atc"
UISCALE="1"
PLANE_SCALE="1.5"
LABEL_SCALE="1.9"
STATUS_SCALE="1.8"
TOLERANCE="0.0001"
MINPOP="50000"
ROADS=1
SIMULATE_WEATHER=0
REGEN_MAP=0
SKIP_MAP=0
EXTRA_ARGS=()

usage() {
    cat <<'EOF'
Usage: ./run_uconsole.sh [options] [-- extra viz1090 args]

Builds if needed, generates offline regional map data if missing, then starts
viz1090 with uConsole-friendly defaults.

Options:
  --lat <value>       Viewer latitude. Default: 40.723972
  --lon <value>       Viewer longitude. Default: -73.845139
  --gps               Try GPS first, falling back to --lat/--lon. Default.
  --no-gps            Do not try GPS.
  --gps-power         Try enabling GPS power GPIO before reading GPS. Default.
  --no-gps-power      Do not touch GPS power GPIO.
  --gps-power-gpio <n> GPS enable GPIO. Default: 27
  --gps-device <path> Add a GPS serial device path to try.
  --gps-timeout <sec> GPS fix timeout. Default: 8
  --bbox <bounds>     Map bbox lon_min,lat_min,lon_max,lat_max.
  --mapdir <path>     Generated map directory. Default: mapdata/generated/nyc
  --weather-file <path> Radar tile cache file. Default: weather/radar_tiles.csv
  --theme <name>      classic, atc, or map. Default: atc
  --uiscale <value>   UI scale. Default: 1
  --plane-scale <n>   Aircraft icon scale. Default: 1.5
  --label-scale <n>   Aircraft label scale. Default: 1.9
  --status-scale <n>  Bottom status text scale. Default: 1.8
  --simulate-weather  Draw a simulated radar storm cell.
  --tolerance <value> Map simplification tolerance. Default: 0.0001
  --minpop <value>    Minimum city population label. Default: 50000
  --no-roads          Do not include roads in regenerated map data.
  --regen-map         Regenerate map data even when files already exist.
  --skip-map          Do not generate map data.
  --help              Show this help.
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
        --bbox)
            BBOX="$2"
            shift 2
            ;;
        --mapdir)
            MAP_DIR="$2"
            shift 2
            ;;
        --weather-file)
            WEATHER_FILE="$2"
            shift 2
            ;;
        --theme)
            THEME="$2"
            shift 2
            ;;
        --uiscale)
            UISCALE="$2"
            shift 2
            ;;
        --plane-scale)
            PLANE_SCALE="$2"
            shift 2
            ;;
        --label-scale)
            LABEL_SCALE="$2"
            shift 2
            ;;
        --status-scale)
            STATUS_SCALE="$2"
            shift 2
            ;;
        --simulate-weather)
            SIMULATE_WEATHER=1
            shift
            ;;
        --tolerance)
            TOLERANCE="$2"
            shift 2
            ;;
        --minpop)
            MINPOP="$2"
            shift 2
            ;;
        --no-roads)
            ROADS=0
            shift
            ;;
        --regen-map)
            REGEN_MAP=1
            shift
            ;;
        --skip-map)
            SKIP_MAP=1
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

needs_build=0
if [[ ! -x ./viz1090 ]]; then
    needs_build=1
elif find . -maxdepth 1 \( -name '*.cpp' -o -name '*.c' -o -name '*.h' \) -newer ./viz1090 | grep -q .; then
    needs_build=1
fi

if [[ "${needs_build}" -eq 1 ]]; then
    make viz1090
fi

if [[ "${GPS}" -eq 1 ]]; then
    if [[ "${GPS_POWER}" -eq 1 ]]; then
        if command -v pinctrl >/dev/null 2>&1; then
            if pinctrl "${GPS_POWER_GPIO}" op && pinctrl "${GPS_POWER_GPIO}" dh; then
                echo "Enabled GPS power on GPIO ${GPS_POWER_GPIO}"
            else
                echo "Could not enable GPS power GPIO ${GPS_POWER_GPIO}; continuing with GPS probe." >&2
            fi
        else
            echo "pinctrl not found; continuing with GPS probe without GPIO power control." >&2
        fi
    fi

    gps_args=(--timeout "${GPS_TIMEOUT}")
    if [[ -n "${GPS_DEVICE}" ]]; then
        gps_args+=(--device "${GPS_DEVICE}")
    fi

    if gps_fix="$(python3 tools/gps_fix.py "${gps_args[@]}")"; then
        LAT="$(printf '%s' "${gps_fix}" | awk '{print $1}')"
        LON="$(printf '%s' "${gps_fix}" | awk '{print $2}')"
        echo "Using GPS fix: ${LAT}, ${LON}"
    else
        echo "No GPS fix found within ${GPS_TIMEOUT}s; using configured location: ${LAT}, ${LON}" >&2
    fi
fi

map_ready=1
for file in mapdata.bin mapnames airportnames; do
    if [[ ! -s "${MAP_DIR}/${file}" ]]; then
        map_ready=0
    fi
done

if [[ "${SKIP_MAP}" -eq 0 && ( "${REGEN_MAP}" -eq 1 || "${map_ready}" -eq 0 ) ]]; then
    python3 - <<'PY'
missing = []
for name in ("fiona", "shapely", "tqdm", "numpy"):
    try:
        __import__(name)
    except Exception:
        missing.append(name)
if missing:
    raise SystemExit(
        "Missing Python map dependencies: %s\n"
        "Install with: sudo apt install -y python3-fiona python3-shapely python3-tqdm python3-numpy wget unzip"
        % ", ".join(missing)
    )
PY
    map_args=(
        --output-dir "${MAP_DIR}"
        --bbox "${BBOX}"
        --tolerance "${TOLERANCE}"
        --minpop "${MINPOP}"
    )

    if [[ "${ROADS}" -eq 1 ]]; then
        map_args+=(--roads)
    else
        map_args+=(--no-roads)
    fi

    ./getmap.sh "${map_args[@]}"
fi

viz_args=(
    --fullscreen
    --screensize 1280 720
    --uiscale "${UISCALE}"
    --plane-scale "${PLANE_SCALE}"
    --label-scale "${LABEL_SCALE}"
    --status-scale "${STATUS_SCALE}"
    --mapdir "${MAP_DIR}"
    --theme "${THEME}"
    --lat "${LAT}"
    --lon "${LON}"
)

if [[ "${SIMULATE_WEATHER}" -eq 1 ]]; then
    viz_args+=(--simulate-weather)
elif [[ -s "${WEATHER_FILE}" ]]; then
    viz_args+=(--weather-file "${WEATHER_FILE}")
fi

exec ./viz1090 "${viz_args[@]}" "${EXTRA_ARGS[@]}"
