#!/usr/bin/env bash
# Publica as tags ghcr.io/wallacepnts/rockfeed-rj (versão + latest) no GHCR.
# Requer login prévio: podman login ghcr.io -u wallacepnts --password-stdin
# Uso: ./scripts/push-image.sh [podman|docker]
set -euo pipefail

cd "$(dirname "$0")/.."

ENGINE="${1:-podman}"
VERSION="$(cat VERSION)"
GHCR_REPO="ghcr.io/wallacepnts/rockfeed-rj"

echo "Publicando ${GHCR_REPO}:${VERSION} e ${GHCR_REPO}:latest com ${ENGINE}..."
"$ENGINE" push "${GHCR_REPO}:${VERSION}"
"$ENGINE" push "${GHCR_REPO}:latest"

echo "OK: publicado."
