#!/usr/bin/env bash
# Builda a imagem com a tag de versão (arquivo VERSION), :latest e os
# equivalentes ghcr.io/wallacepnts/rockfeed-rj (usados pelo Quadlet).
# Uso: ./scripts/build-image.sh [podman|docker]
set -euo pipefail

cd "$(dirname "$0")/.."

ENGINE="${1:-podman}"
VERSION="$(cat VERSION)"
GHCR_REPO="ghcr.io/wallacepnts/rockfeed-rj"

# Podman builda em formato OCI por padrão, que não suporta HEALTHCHECK;
# forçar --format docker pra manter o healthcheck da imagem funcionando.
FORMAT_FLAG=()
[ "$ENGINE" = "podman" ] && FORMAT_FLAG=(--format docker)

echo "Buildando rockfeed-rj:${VERSION} (+ latest, + tags ${GHCR_REPO}) com ${ENGINE}..."
"$ENGINE" build \
    "${FORMAT_FLAG[@]}" \
    --build-arg VERSION="$VERSION" \
    -t "rockfeed-rj:${VERSION}" \
    -t "rockfeed-rj:latest" \
    -t "${GHCR_REPO}:${VERSION}" \
    -t "${GHCR_REPO}:latest" \
    .

echo "OK: rockfeed-rj:${VERSION}, rockfeed-rj:latest, ${GHCR_REPO}:${VERSION}, ${GHCR_REPO}:latest"
