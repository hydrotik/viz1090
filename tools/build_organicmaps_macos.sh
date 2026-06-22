#!/usr/bin/env bash
set -euo pipefail

OMIM_DIR="${OMIM_DIR:-external/organicmaps}"
ARCH="${ARCH:-$(uname -m)}"
JOBS="${JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || echo 8)}"
BUILD_PARENT="${OMIM_BUILD_PARENT:-external/omim-build-${ARCH}}"

usage() {
    cat <<'EOF'
Usage: tools/build_organicmaps_macos.sh

Builds the ignored Organic Maps checkout as a native macOS desktop app.

Environment:
  OMIM_DIR            Organic Maps checkout. Default: external/organicmaps
  OMIM_BUILD_PARENT   Build parent directory. Default: external/omim-build-$(uname -m)
  ARCH                CMake macOS architecture. Default: $(uname -m)
  JOBS                Parallel build jobs. Default: macOS CPU count

Run tools/bootstrap_organicmaps.sh first if external/organicmaps does not exist.
EOF
}

if [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This helper is only for macOS. Use Organic Maps docs/INSTALL.md on Linux." >&2
    exit 2
fi

if [[ ! -d "${OMIM_DIR}/.git" ]]; then
    echo "Organic Maps checkout not found at ${OMIM_DIR}" >&2
    echo "Run: tools/bootstrap_organicmaps.sh" >&2
    exit 2
fi

if [[ "${ARCH}" == "arm64" ]]; then
    BREW_PREFIX="${BREW_PREFIX:-/opt/homebrew}"
else
    BREW_PREFIX="${BREW_PREFIX:-/usr/local}"
fi

QT_PREFIX="${QT_PREFIX:-${BREW_PREFIX}/opt/qt}"
if [[ ! -d "${QT_PREFIX}" && -d "${BREW_PREFIX}/opt/qt@6" ]]; then
    QT_PREFIX="${BREW_PREFIX}/opt/qt@6"
fi

if [[ ! -x "${BREW_PREFIX}/bin/cmake" || ! -x "${BREW_PREFIX}/bin/ninja" || ! -d "${QT_PREFIX}" ]]; then
    echo "Missing native build dependencies under ${BREW_PREFIX}." >&2
    echo "Install them with: ${BREW_PREFIX}/bin/brew install cmake ninja qt" >&2
    exit 2
fi

mkdir -p "$(dirname "${BUILD_PARENT}")"
BUILD_PARENT_ABS="$(cd "$(dirname "${BUILD_PARENT}")" && pwd)/$(basename "${BUILD_PARENT}")"

if ! grep "DEFAULT_URLS_JSON" "${OMIM_DIR}/private.h" >/dev/null 2>&1; then
    (cd "${OMIM_DIR}" && bash ./configure.sh)
fi

echo "Building Organic Maps for ${ARCH}"
echo "  checkout: ${OMIM_DIR}"
echo "  Qt:       ${QT_PREFIX}"
echo "  output:   ${BUILD_PARENT_ABS}/omim-build-release/OMaps.app"

(
    cd "${OMIM_DIR}"
    PATH="${QT_PREFIX}/bin:${BREW_PREFIX}/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    CMAKE_PREFIX_PATH="${QT_PREFIX}" \
    CMAKE_CONFIG="-DCMAKE_OSX_ARCHITECTURES=${ARCH} -DCMAKE_PREFIX_PATH=${QT_PREFIX} ${CMAKE_CONFIG:-}" \
    tools/unix/build_omim.sh -r -p "${BUILD_PARENT_ABS}" -n "${JOBS}" desktop
)

APP="${BUILD_PARENT_ABS}/omim-build-release/OMaps.app"
BIN="${APP}/Contents/MacOS/OMaps"
echo
echo "Built: ${APP}"
if [[ -x "${BIN}" ]]; then
    file "${BIN}"
fi
