#!/usr/bin/env bash
set -euo pipefail

DEST="external/organicmaps"
BUILD=0

usage() {
    cat <<'EOF'
Usage: tools/bootstrap_organicmaps.sh [options]

Clones Organic Maps into an ignored local workspace for ADS-B overlay work.

Options:
  --dest <path>       Checkout directory. Default: external/organicmaps
  --build-desktop     After clone/update, try a desktop release build.
  --help              Show this help.

Notes:
  This does not vendor Organic Maps into viz1090.
  Build Organic Maps on a Mac or Linux workstation first; the uConsole is a
  runtime target, not the fastest place to compile this large Qt/C++ project.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dest)
            DEST="$2"
            shift 2
            ;;
        --build-desktop)
            BUILD=1
            shift
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

if [[ ! -d "${DEST}/.git" ]]; then
    mkdir -p "$(dirname "${DEST}")"
    git clone \
        --depth 1 \
        --filter=blob:limit=128k \
        --recurse-submodules \
        --shallow-submodules \
        https://github.com/organicmaps/organicmaps.git \
        "${DEST}"
else
    git -C "${DEST}" fetch --depth 1 origin
    git -C "${DEST}" pull --ff-only
    git -C "${DEST}" submodule update --init --recursive --depth 1
fi

cat <<EOF
Organic Maps checkout is ready at:
  ${DEST}

Desktop dependency notes:
  macOS:  brew install cmake ninja qt@6
  Debian/Ubuntu 24.04+: see ${DEST}/docs/INSTALL.md

ADS-B feed from viz1090:
  ./run_uconsole.sh --organic-feed /run/user/\$(id -u)/viz1090-aircraft.geojson

Organic Maps overlay work should consume that GeoJSON file from a lightweight
custom layer or polling source inside the Organic Maps checkout.
EOF

if [[ "${BUILD}" -eq 1 ]]; then
    (cd "${DEST}" && bash ./configure.sh && tools/unix/build_omim.sh -r desktop)
fi
