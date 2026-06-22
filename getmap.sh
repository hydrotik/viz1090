#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="mapdata"
OUTPUT_DIR="."
OFFLINE=0
FORCE_DOWNLOAD=0
MINPOP=100000
TOLERANCE=0.001
BBOX=""
ROADS="auto"
WATER="auto"

usage() {
    cat <<'EOF'
Usage: ./getmap.sh [options]

Downloads and converts offline vector map assets for viz1090.

Options:
  --offline              Use only files already present in mapdata/cache.
  --force-download       Re-download sources even if cached files exist.
  --data-dir <path>      Source cache/work directory. Default: mapdata.
  --output-dir <path>    Generated map output directory. Default: current dir.
  --bbox <bounds>        Clip to lon_min,lat_min,lon_max,lat_max.
  --roads                Include Natural Earth roads.
  --no-roads             Do not include roads.
  --water                Include lakes and river centerlines.
  --no-water             Do not include lakes and river centerlines.
  --minpop <number>      Minimum city population label. Default: 100000.
  --tolerance <number>   Geometry simplification tolerance. Default: 0.001.
  --help                 Show this help.

Example for offline US assets:
  ./getmap.sh --output-dir mapdata/generated/us --bbox -180,17,-52,72 --roads --water --tolerance 0.001 --minpop 100000

Run viz1090 with:
  ./viz1090 --mapdir mapdata/generated/us --theme atc --lat 40.723972 --lon -73.845139
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --offline)
            OFFLINE=1
            shift
            ;;
        --force-download)
            FORCE_DOWNLOAD=1
            shift
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --bbox)
            BBOX="$2"
            shift 2
            ;;
        --roads)
            ROADS="yes"
            shift
            ;;
        --no-roads)
            ROADS="no"
            shift
            ;;
        --water)
            WATER="yes"
            shift
            ;;
        --no-water)
            WATER="no"
            shift
            ;;
        --minpop)
            MINPOP="$2"
            shift 2
            ;;
        --tolerance)
            TOLERANCE="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

CACHE_DIR="${DATA_DIR}/cache"
WORK_DIR="${DATA_DIR}/work"

mkdir -p "${CACHE_DIR}" "${WORK_DIR}" "${OUTPUT_DIR}"
rm -rf "${WORK_DIR:?}/"*

cache_file_valid() {
    local filename="$1"
    local path="$2"

    if [[ ! -s "${path}" ]]; then
        return 1
    fi

    if [[ "${filename}" == *.zip ]]; then
        unzip -tq "${path}" >/dev/null 2>&1
        return
    fi

    return 0
}

download_source() {
    local filename="$1"
    local url="$2"
    local output="${CACHE_DIR}/${filename}"
    local partial="${output}.partial"

    if [[ -f "${output}" && "${FORCE_DOWNLOAD}" -eq 0 ]] && cache_file_valid "${filename}" "${output}"; then
        echo "Using cached ${filename}"
        return
    fi

    if [[ "${OFFLINE}" -eq 1 ]]; then
        echo "Missing cached source ${output}; cannot continue in --offline mode." >&2
        exit 1
    fi

    echo "Downloading ${filename}"
    rm -f "${partial}"
    if wget --tries=3 --timeout=20 --no-verbose -O "${partial}" "${url}"; then
        mv "${partial}" "${output}"
        return
    fi

    rm -f "${partial}"
    if [[ -f "${output}" ]] && cache_file_valid "${filename}" "${output}"; then
        echo "Download failed for ${filename}; using existing cached copy." >&2
        return
    fi

    echo "Download failed for ${filename}, and no cached copy exists." >&2
    echo "Reconnect the uConsole to the network and retry, or copy mapdata/cache from a machine that already has these files." >&2
    exit 1
}

download_optional_source() {
    local filename="$1"
    local url="$2"
    local output="${CACHE_DIR}/${filename}"
    local partial="${output}.partial"

    if [[ -f "${output}" && "${FORCE_DOWNLOAD}" -eq 0 ]] && cache_file_valid "${filename}" "${output}"; then
        echo "Using cached ${filename}"
        return 0
    fi

    if [[ "${OFFLINE}" -eq 1 ]]; then
        echo "Optional cached source ${output} is missing; continuing without it." >&2
        return 1
    fi

    echo "Downloading optional ${filename}"
    rm -f "${partial}"
    if wget --tries=3 --timeout=20 --no-verbose -O "${partial}" "${url}"; then
        mv "${partial}" "${output}"
        return 0
    fi

    rm -f "${partial}"
    if [[ -f "${output}" ]] && cache_file_valid "${filename}" "${output}"; then
        echo "Optional source ${filename} could not be refreshed; using existing cached copy." >&2
        return 0
    fi

    echo "Optional source ${filename} could not be downloaded; continuing without it." >&2
    return 1
}

extract_source() {
    local filename="$1"
    unzip -q -o "${CACHE_DIR}/${filename}" -d "${WORK_DIR}"
}

download_source "ne_10m_admin_1_states_provinces.zip" "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
download_source "ne_10m_coastline.zip" "https://naciscdn.org/naturalearth/10m/physical/ne_10m_coastline.zip"
download_source "ne_10m_populated_places.zip" "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip"
download_source "ne_10m_airports.zip" "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_airports.zip"
RUNWAY_CSV_AVAILABLE=0
if download_optional_source "ourairports_runways.csv" "https://davidmegginson.github.io/ourairports-data/runways.csv"; then
    RUNWAY_CSV_AVAILABLE=1
fi

INCLUDE_ROADS=0
if [[ "${ROADS}" == "yes" || ( "${ROADS}" == "auto" && -n "${BBOX}" ) ]]; then
    INCLUDE_ROADS=1
fi

INCLUDE_WATER=0
if [[ "${WATER}" == "yes" || ( "${WATER}" == "auto" && -n "${BBOX}" ) ]]; then
    INCLUDE_WATER=1
fi

ROADS_AVAILABLE=0
if [[ "${INCLUDE_ROADS}" -eq 1 ]]; then
    if download_optional_source "ne_10m_roads.zip" "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip"; then
        ROADS_AVAILABLE=1
    fi
fi

LAKES_AVAILABLE=0
RIVERS_AVAILABLE=0
if [[ "${INCLUDE_WATER}" -eq 1 ]]; then
    if download_optional_source "ne_10m_lakes.zip" "https://naciscdn.org/naturalearth/10m/physical/ne_10m_lakes.zip"; then
        LAKES_AVAILABLE=1
    fi

    if download_optional_source "ne_10m_rivers_lake_centerlines.zip" "https://naciscdn.org/naturalearth/10m/physical/ne_10m_rivers_lake_centerlines.zip"; then
        RIVERS_AVAILABLE=1
    fi
fi

# FAA runway geometry. This endpoint has changed before, so keep the downloaded
# archive cached and prefer --offline after one successful fetch.
RUNWAYS_AVAILABLE=0
if download_optional_source "faa_runways.zip" "https://opendata.arcgis.com/datasets/4d8fa46181aa470d809776c57a8ab1f6_0.zip"; then
    RUNWAYS_AVAILABLE=1
fi

extract_source "ne_10m_admin_1_states_provinces.zip"
extract_source "ne_10m_coastline.zip"
extract_source "ne_10m_populated_places.zip"
extract_source "ne_10m_airports.zip"
if [[ "${ROADS_AVAILABLE}" -eq 1 ]]; then
    extract_source "ne_10m_roads.zip"
fi
if [[ "${LAKES_AVAILABLE}" -eq 1 ]]; then
    extract_source "ne_10m_lakes.zip"
fi
if [[ "${RIVERS_AVAILABLE}" -eq 1 ]]; then
    extract_source "ne_10m_rivers_lake_centerlines.zip"
fi
if [[ "${RUNWAYS_AVAILABLE}" -eq 1 ]]; then
    extract_source "faa_runways.zip"
fi

converter_args=(
    --maplayer "admin=${WORK_DIR}/ne_10m_admin_1_states_provinces.shp"
    --maplayer "coast=${WORK_DIR}/ne_10m_coastline.shp"
    --mapnames "${WORK_DIR}/ne_10m_populated_places.shp"
    --airportnames "${WORK_DIR}/ne_10m_airports.shp"
    --output-dir "${OUTPUT_DIR}"
    --minpop "${MINPOP}"
    --tolerance "${TOLERANCE}"
)

if [[ "${ROADS_AVAILABLE}" -eq 1 && -f "${WORK_DIR}/ne_10m_roads.shp" ]]; then
    converter_args+=(--maplayer "roads=${WORK_DIR}/ne_10m_roads.shp")
fi

if [[ "${LAKES_AVAILABLE}" -eq 1 && -f "${WORK_DIR}/ne_10m_lakes.shp" ]]; then
    converter_args+=(--maplayer "water=${WORK_DIR}/ne_10m_lakes.shp")
fi

if [[ "${RIVERS_AVAILABLE}" -eq 1 && -f "${WORK_DIR}/ne_10m_rivers_lake_centerlines.shp" ]]; then
    converter_args+=(--maplayer "water=${WORK_DIR}/ne_10m_rivers_lake_centerlines.shp")
fi

if [[ "${RUNWAYS_AVAILABLE}" -eq 1 && -f "${WORK_DIR}/Runways.shp" ]]; then
    converter_args+=(--airportfile "${WORK_DIR}/Runways.shp")
elif [[ "${RUNWAY_CSV_AVAILABLE}" -eq 1 && -f "${CACHE_DIR}/ourairports_runways.csv" ]]; then
    converter_args+=(--airportcsv "${CACHE_DIR}/ourairports_runways.csv")
fi

if [[ -n "${BBOX}" ]]; then
    converter_args+=("--bbox=${BBOX}")
fi

python3 mapconverter.py "${converter_args[@]}"

echo "Generated offline map assets in ${OUTPUT_DIR}"
