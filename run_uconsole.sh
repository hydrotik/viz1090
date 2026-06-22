#!/usr/bin/env bash
set -euo pipefail

LAT="40.723972"
LON="-73.845139"
GPS=1
GPS_TIMEOUT="8"
GPS_DEVICE=""
GPS_POWER=1
GPS_POWER_GPIO="27"
MAP_PROFILE="us-hd"
BBOX="-180,17,-52,72"
MAP_DIR="mapdata/generated/us-hd"
WEATHER_FILE="weather/radar_tiles.csv"
ORGANIC_FEED=""
ORGANIC_FEED_INTERVAL_MS="1000"
THEME="atc"
UISCALE="1"
PLANE_SCALE="1.5"
LABEL_SCALE="1.9"
STATUS_SCALE="1.8"
TILE_SOURCE=""
TILE_MODE="auto"
TILE_THEME="auto"
TILE_MIN_ZOOM="0"
TILE_MAX_ZOOM="17"
TILE_ZOOM_OFFSET="0"
TILE_USABLE=1
TOLERANCE="0.001"
MINPOP="100000"
ROADS=1
WATER=1
SIMULATE_WEATHER=0
REGEN_MAP=0
SKIP_MAP=0
DEBUG_INPUT=0
EXTRA_ARGS=()

usage() {
    cat <<'EOF'
Usage: ./run_uconsole.sh [options] [-- extra viz1090 args]

Builds if needed, generates offline map data if missing, then starts
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
  --map-profile <name> us-hd, us, conus-hd, conus, drive, northeast, or custom.
                      Default: us-hd
  --car-mode          Larger at-a-glance UI, daylight map theme, and drive map profile.
  --bbox <bounds>     Map bbox lon_min,lat_min,lon_max,lat_max. Default: US profile.
  --mapdir <path>     Generated map directory. Default: mapdata/generated/us-hd
  --weather-file <path> Radar tile cache file. Default: weather/radar_tiles.csv
  --organic-feed <path> Write aircraft GeoJSON for an Organic Maps sidecar overlay.
  --organic-feed-interval-ms <ms> Feed interval. Default: 1000
  --theme <name>      classic, atc, map, or light. Default: atc
  --osm-mode          Use a local OSM-style raster basemap when available.
                      Default tile source: mapdata/tiles/us.mbtiles
  --tiles <path>      Offline raster tiles: MBTiles file or z/x/y tile directory.
  --tiles-mode <mode> auto, mbtiles, xyz, or tms. Default: auto
  --tile-theme <mode> auto, light, or dark. Default: auto
  --tile-min-zoom <z> Minimum raster tile zoom. Default: 0
  --tile-max-zoom <z> Maximum raster tile zoom. Default: 17
  --tile-zoom-offset <n> Adjust selected raster tile zoom. Default: 0
  --uiscale <value>   UI scale. Default: 1
  --plane-scale <n>   Aircraft icon scale. Default: 1.5
  --label-scale <n>   Aircraft label scale. Default: 1.9
  --status-scale <n>  Bottom status text scale. Default: 1.8
  --simulate-weather  Draw a simulated radar storm cell.
  --debug-input       Print SDL input events to stdout.
  --tolerance <value> Map simplification tolerance. Default: profile-specific.
  --minpop <value>    Minimum city population label. Default: 100000
  --no-roads          Do not include roads in regenerated map data.
  --no-water          Do not include lakes/rivers in regenerated map data.
  --regen-map         Regenerate map data even when files already exist.
  --skip-map          Do not generate map data.
  --help              Show this help.
EOF
}

apply_map_profile() {
    case "${MAP_PROFILE}" in
        us-hd)
            BBOX="-180,17,-52,72"
            MAP_DIR="mapdata/generated/us-hd"
            TOLERANCE="0.0005"
            MINPOP="50000"
            ROADS=1
            WATER=1
            ;;
        us)
            BBOX="-180,17,-52,72"
            MAP_DIR="mapdata/generated/us"
            TOLERANCE="0.001"
            MINPOP="100000"
            ROADS=1
            WATER=1
            ;;
        conus-hd)
            BBOX="-125,24,-66,50"
            MAP_DIR="mapdata/generated/conus-hd"
            TOLERANCE="0.00035"
            MINPOP="25000"
            ROADS=1
            WATER=1
            ;;
        conus)
            BBOX="-125,24,-66,50"
            MAP_DIR="mapdata/generated/conus"
            TOLERANCE="0.00075"
            MINPOP="50000"
            ROADS=1
            WATER=1
            ;;
        drive)
            BBOX="-125,24,-66,50"
            MAP_DIR="mapdata/generated/drive"
            TOLERANCE="0.00035"
            MINPOP="25000"
            ROADS=1
            WATER=1
            ;;
        northeast)
            BBOX="-82,36,-65,48.5"
            MAP_DIR="mapdata/generated/northeast"
            TOLERANCE="0.00025"
            MINPOP="25000"
            ROADS=1
            WATER=1
            ;;
        custom)
            ;;
        *)
            echo "Unknown map profile: ${MAP_PROFILE}" >&2
            echo "Valid profiles: us-hd, us, conus-hd, conus, drive, northeast, custom" >&2
            exit 1
            ;;
    esac
}

apply_car_mode() {
    MAP_PROFILE="drive"
    apply_map_profile
    THEME="map"
    PLANE_SCALE="1.8"
    LABEL_SCALE="2.2"
    STATUS_SCALE="2.2"
    GPS_TIMEOUT="20"
}

apply_osm_mode() {
    THEME="map"
    if [[ -z "${TILE_SOURCE}" ]]; then
        TILE_SOURCE="mapdata/tiles/us.mbtiles"
    fi
    TILE_MODE="auto"
    TILE_MIN_ZOOM="0"
    TILE_MAX_ZOOM="16"
    TILE_ZOOM_OFFSET="0"
}

apply_map_profile

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
        --map-profile)
            MAP_PROFILE="$2"
            apply_map_profile
            shift 2
            ;;
        --car-mode)
            apply_car_mode
            shift
            ;;
        --bbox)
            MAP_PROFILE="custom"
            BBOX="$2"
            shift 2
            ;;
        --mapdir)
            MAP_PROFILE="custom"
            MAP_DIR="$2"
            shift 2
            ;;
        --weather-file)
            WEATHER_FILE="$2"
            shift 2
            ;;
        --organic-feed)
            ORGANIC_FEED="$2"
            shift 2
            ;;
        --organic-feed-interval-ms)
            ORGANIC_FEED_INTERVAL_MS="$2"
            shift 2
            ;;
        --theme)
            THEME="$2"
            shift 2
            ;;
        --osm-mode)
            apply_osm_mode
            shift
            ;;
        --tiles)
            TILE_SOURCE="$2"
            shift 2
            ;;
        --tiles-mode)
            TILE_MODE="$2"
            shift 2
            ;;
        --tile-theme)
            TILE_THEME="$2"
            shift 2
            ;;
        --tile-min-zoom)
            TILE_MIN_ZOOM="$2"
            shift 2
            ;;
        --tile-max-zoom)
            TILE_MAX_ZOOM="$2"
            shift 2
            ;;
        --tile-zoom-offset)
            TILE_ZOOM_OFFSET="$2"
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
        --debug-input)
            DEBUG_INPUT=1
            shift
            ;;
        --tolerance)
            MAP_PROFILE="custom"
            TOLERANCE="$2"
            shift 2
            ;;
        --minpop)
            MAP_PROFILE="custom"
            MINPOP="$2"
            shift 2
            ;;
        --no-roads)
            MAP_PROFILE="custom"
            ROADS=0
            shift
            ;;
        --no-water)
            MAP_PROFILE="custom"
            WATER=0
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

    if [[ "${WATER}" -eq 1 ]]; then
        map_args+=(--water)
    else
        map_args+=(--no-water)
    fi

    ./getmap.sh "${map_args[@]}"
fi

if [[ -n "${TILE_SOURCE}" && ! -e "${TILE_SOURCE}" ]]; then
    echo "Raster tile source ${TILE_SOURCE} was requested but does not exist yet; continuing with vector map only." >&2
fi

if [[ -n "${TILE_SOURCE}" && -f "${TILE_SOURCE}" ]]; then
    case "${TILE_SOURCE}" in
        *.mbtiles|*.MBTILES)
            if ! python3 tools/inspect_mbtiles.py --quiet "${TILE_SOURCE}"; then
                TILE_USABLE=0
                echo "Raster tile source ${TILE_SOURCE} is not directly renderable by viz1090:" >&2
                python3 tools/inspect_mbtiles.py "${TILE_SOURCE}" >&2 || true
                echo "Continuing with generated vector map only. Use raster PNG/JPEG/WebP MBTiles, not vector PBF/MVT MBTiles." >&2
            fi
            ;;
    esac
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

if [[ -n "${TILE_SOURCE}" && -e "${TILE_SOURCE}" && "${TILE_USABLE}" -eq 1 ]]; then
    viz_args+=(
        --tiles "${TILE_SOURCE}"
        --tiles-mode "${TILE_MODE}"
        --tile-theme "${TILE_THEME}"
        --tile-min-zoom "${TILE_MIN_ZOOM}"
        --tile-max-zoom "${TILE_MAX_ZOOM}"
        --tile-zoom-offset "${TILE_ZOOM_OFFSET}"
    )
fi

if [[ -n "${ORGANIC_FEED}" ]]; then
    mkdir -p "$(dirname "${ORGANIC_FEED}")"
    viz_args+=(
        --organic-feed "${ORGANIC_FEED}"
        --organic-feed-interval-ms "${ORGANIC_FEED_INTERVAL_MS}"
    )
fi

if [[ "${SIMULATE_WEATHER}" -eq 1 ]]; then
    viz_args+=(--simulate-weather)
elif [[ -n "${WEATHER_FILE}" ]]; then
    viz_args+=(--weather-file "${WEATHER_FILE}")
fi

if [[ "${DEBUG_INPUT}" -eq 1 ]]; then
    viz_args+=(--debug-input)
fi

exec ./viz1090 "${viz_args[@]}" "${EXTRA_ARGS[@]}"
