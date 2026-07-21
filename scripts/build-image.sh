#!/usr/bin/env bash
# Builda a imagem com a tag de versão (arquivo VERSION) e também :latest.
# Uso: ./scripts/build-image.sh [podman|docker]
set -euo pipefail

cd "$(dirname "$0")/.."

ENGINE="${1:-podman}"
VERSION="$(cat VERSION)"

# Podman builda em formato OCI por padrão, que não suporta HEALTHCHECK;
# forçar --format docker pra manter o healthcheck da imagem funcionando.
FORMAT_FLAG=()
[ "$ENGINE" = "podman" ] && FORMAT_FLAG=(--format docker)

echo "Buildando rockfeed-rj:${VERSION} e rockfeed-rj:latest com ${ENGINE}..."
"$ENGINE" build \
    "${FORMAT_FLAG[@]}" \
    --build-arg VERSION="$VERSION" \
    -t "rockfeed-rj:${VERSION}" \
    -t "rockfeed-rj:latest" \
    .

echo "OK: rockfeed-rj:${VERSION} e rockfeed-rj:latest"
