#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-djdonovan@192.168.1.195}"
REMOTE_AIRCRAFT="${REMOTE_AIRCRAFT:-/run/user/1000/viz1090-aircraft.geojson}"
REMOTE_WEATHER="${REMOTE_WEATHER:-/home/djdonovan/viz1090/weather/radar_tiles.csv}"
LOCAL_AIRCRAFT="${LOCAL_AIRCRAFT:-/tmp/viz1090-aircraft.geojson}"
LOCAL_WEATHER="${LOCAL_WEATHER:-/tmp/viz1090-radar_tiles.csv}"
INTERVAL="${INTERVAL:-1}"

usage() {
    cat <<'EOF'
Usage: tools/bridge_uconsole_feeds.sh [user@host]

Mirrors live viz1090 aircraft and weather overlay feeds from the uConsole to
local /tmp files for the patched Organic Maps desktop app. Uses one persistent
SSH session, so password authentication prompts once instead of once per file.

Environment:
  REMOTE_AIRCRAFT  Default: /run/user/1000/viz1090-aircraft.geojson
  REMOTE_WEATHER   Default: /home/djdonovan/viz1090/weather/radar_tiles.csv
  LOCAL_AIRCRAFT   Default: /tmp/viz1090-aircraft.geojson
  LOCAL_WEATHER    Default: /tmp/viz1090-radar_tiles.csv
  INTERVAL         Default: 1
EOF
}

if [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

AIRCRAFT_TMP="${LOCAL_AIRCRAFT}.tmp"
WEATHER_TMP="${LOCAL_WEATHER}.tmp"
state=""

ssh "${HOST}" \
    "REMOTE_AIRCRAFT='${REMOTE_AIRCRAFT}' REMOTE_WEATHER='${REMOTE_WEATHER}' INTERVAL='${INTERVAL}' sh -s" <<'REMOTE' |
while true; do
  echo "__VIZ1090_AIRCRAFT_BEGIN__"
  if [ -s "$REMOTE_AIRCRAFT" ]; then
    cat "$REMOTE_AIRCRAFT"
  fi
  echo
  echo "__VIZ1090_AIRCRAFT_END__"
  echo "__VIZ1090_WEATHER_BEGIN__"
  if [ -s "$REMOTE_WEATHER" ]; then
    cat "$REMOTE_WEATHER"
  fi
  echo "__VIZ1090_WEATHER_END__"
  sleep "$INTERVAL"
done
REMOTE
while IFS= read -r line; do
    case "${line}" in
        __VIZ1090_AIRCRAFT_BEGIN__)
            : > "${AIRCRAFT_TMP}"
            state="aircraft"
            ;;
        __VIZ1090_AIRCRAFT_END__)
            if [[ -s "${AIRCRAFT_TMP}" ]]; then
                mv "${AIRCRAFT_TMP}" "${LOCAL_AIRCRAFT}"
                printf 'updated %s %s\n' "${LOCAL_AIRCRAFT}" "$(date '+%H:%M:%S')"
            fi
            state=""
            ;;
        __VIZ1090_WEATHER_BEGIN__)
            : > "${WEATHER_TMP}"
            state="weather"
            ;;
        __VIZ1090_WEATHER_END__)
            if [[ -s "${WEATHER_TMP}" ]]; then
                mv "${WEATHER_TMP}" "${LOCAL_WEATHER}"
                printf 'updated %s %s\n' "${LOCAL_WEATHER}" "$(date '+%H:%M:%S')"
            fi
            state=""
            ;;
        *)
            if [[ "${state}" == "aircraft" ]]; then
                printf '%s\n' "${line}" >> "${AIRCRAFT_TMP}"
            elif [[ "${state}" == "weather" ]]; then
                printf '%s\n' "${line}" >> "${WEATHER_TMP}"
            fi
            ;;
    esac
done
