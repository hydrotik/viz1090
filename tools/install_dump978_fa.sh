#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-/usr/local}"
BUILD_DIR="${BUILD_DIR:-$HOME/src/dump978-fa}"

usage() {
    cat <<'EOF'
Usage: tools/install_dump978_fa.sh

Builds and installs FlightAware dump978-fa from source. Run on the uConsole.
Requires sudo, network access, and enough memory/swap for a C++ build.

Environment:
  BUILD_DIR  clone/build directory. Default: $HOME/src/dump978-fa
  PREFIX     install prefix. Default: /usr/local
EOF
}

if [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

sudo apt update
sudo apt install -y \
    build-essential \
    git \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libboost-regex-dev \
    libsoapysdr-dev \
    soapysdr0.8-module-rtlsdr \
    soapysdr-tools

mkdir -p "$(dirname "${BUILD_DIR}")"
if [[ ! -d "${BUILD_DIR}/.git" ]]; then
    git clone https://github.com/flightaware/dump978.git "${BUILD_DIR}"
fi

cd "${BUILD_DIR}"
git pull --ff-only
make

sudo install -m 0755 dump978-fa "${PREFIX}/bin/dump978-fa"
if [[ -x skyaware978 ]]; then
    sudo install -m 0755 skyaware978 "${PREFIX}/bin/skyaware978"
fi

echo "Installed dump978-fa to ${PREFIX}/bin/dump978-fa"
dump978-fa --help | head -40 || true
