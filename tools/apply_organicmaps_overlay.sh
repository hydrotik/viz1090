#!/usr/bin/env bash
set -euo pipefail

OMIM_DIR="${OMIM_DIR:-external/organicmaps}"
PATCH_FILE="${PATCH_FILE:-tools/organicmaps_viz1090_aircraft_overlay.patch}"

usage() {
    cat <<'EOF'
Usage: tools/apply_organicmaps_overlay.sh

Applies the viz1090 aircraft overlay patch to the ignored Organic Maps checkout.

Environment:
  OMIM_DIR      Organic Maps checkout. Default: external/organicmaps
  PATCH_FILE    Patch file. Default: tools/organicmaps_viz1090_aircraft_overlay.patch
EOF
}

if [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ ! -d "${OMIM_DIR}/.git" ]]; then
    echo "Organic Maps checkout not found at ${OMIM_DIR}" >&2
    echo "Run: tools/bootstrap_organicmaps.sh" >&2
    exit 2
fi

if [[ ! -f "${PATCH_FILE}" ]]; then
    echo "Patch not found: ${PATCH_FILE}" >&2
    exit 2
fi

PATCH_ABS="$(cd "$(dirname "${PATCH_FILE}")" && pwd)/$(basename "${PATCH_FILE}")"

if git -C "${OMIM_DIR}" apply --check "${PATCH_ABS}" 2>/dev/null; then
    git -C "${OMIM_DIR}" apply "${PATCH_ABS}"
    echo "Applied ${PATCH_FILE} to ${OMIM_DIR}"
    exit 0
fi

if git -C "${OMIM_DIR}" apply --reverse --check "${PATCH_ABS}" 2>/dev/null; then
    echo "Patch is already applied to ${OMIM_DIR}"
    exit 0
fi

echo "Patch could not be applied cleanly. Check Organic Maps checkout state:" >&2
echo "  git -C ${OMIM_DIR} status --short" >&2
exit 1
