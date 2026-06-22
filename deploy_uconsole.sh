#!/usr/bin/env bash
set -euo pipefail

REMOTE="${REMOTE:-djdonovan@192.168.1.195}"
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/codex_uconsole_nopass}"
REMOTE_DIR="${REMOTE_DIR:-~/viz1090}"
SYNC_TILES=0
RUN_AFTER=0
TILE_PROFILES=("starter")
RUN_ARGS=()

usage() {
    cat <<'EOF'
Usage: ./deploy_uconsole.sh [options] [-- run_uconsole_station.sh args]

Syncs the viz1090 codebase to the uConsole with build artifacts excluded.
Optionally syncs selected raster MBTiles packs and starts the station launcher.

Options:
  --remote <user@host>       Default: djdonovan@192.168.1.195
  --ssh-key <path>           Default: ~/.ssh/codex_uconsole_nopass
  --remote-dir <path>        Default: ~/viz1090
  --tiles [profiles...]      Sync raster packs. Profiles/groups: starter,
                             conus-regions, all-us, nyc, northeast, etc.
  --run                      Start ./run_uconsole_station.sh after syncing.
  --help                     Show this help.

Examples:
  ./deploy_uconsole.sh
  ./deploy_uconsole.sh --tiles starter
  ./deploy_uconsole.sh --tiles conus-regions -- --weather-profile regional
  ./deploy_uconsole.sh --run -- --map-tile-profile auto --weather-profile regional
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --remote)
            REMOTE="$2"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY="$2"
            shift 2
            ;;
        --remote-dir)
            REMOTE_DIR="$2"
            shift 2
            ;;
        --tiles)
            SYNC_TILES=1
            shift
            TILE_PROFILES=()
            while [[ $# -gt 0 && "$1" != --* ]]; do
                TILE_PROFILES+=("$1")
                shift
            done
            if [[ "${#TILE_PROFILES[@]}" -eq 0 ]]; then
                TILE_PROFILES=("starter")
            fi
            ;;
        --run)
            RUN_AFTER=1
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        --)
            shift
            RUN_ARGS+=("$@")
            break
            ;;
        *)
            RUN_ARGS+=("$1")
            shift
            ;;
    esac
done

ssh_args=(-i "${SSH_KEY}" -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4)

rsync -av --delete \
    --exclude .git/ \
    --exclude __pycache__/ \
    --exclude '*.o' \
    --exclude viz1090 \
    --exclude tests/core_tests \
    --exclude mapdata/ \
    --exclude weather/ \
    --exclude external/ \
    --exclude uconsole-screen.bmp \
    --exclude uconsole-screen.png \
    -e "ssh ${ssh_args[*]}" \
    ./ \
    "${REMOTE}:${REMOTE_DIR}/"

if [[ "${SYNC_TILES}" -eq 1 ]]; then
    mapfile -t tile_files < <(
        python3 - "${TILE_PROFILES[@]}" <<'PY'
import sys
from tools.coverage_profiles import MAP_PROFILES, profile_names_for_group

seen = set()
for value in sys.argv[1:]:
    for name in profile_names_for_group(value):
        if name in seen:
            continue
        seen.add(name)
        print(MAP_PROFILES[name]["output"])
PY
    )

    ssh "${ssh_args[@]}" "${REMOTE}" "mkdir -p ${REMOTE_DIR}/mapdata/tiles"
    for tile in "${tile_files[@]}"; do
        if [[ -f "${tile}" ]]; then
            rsync -av -e "ssh ${ssh_args[*]}" "${tile}" "${REMOTE}:${REMOTE_DIR}/mapdata/tiles/"
        else
            echo "Skipping missing tile pack ${tile}" >&2
        fi
    done
fi

if [[ "${RUN_AFTER}" -eq 1 ]]; then
    ssh "${ssh_args[@]}" "${REMOTE}" "cd ${REMOTE_DIR} && ./run_uconsole_station.sh ${RUN_ARGS[*]}"
fi
