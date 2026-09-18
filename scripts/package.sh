#!/usr/bin/env bash
# Package the kubemq-next chart into docs/ and refresh the Helm repo index served by GitHub Pages.
# Existing packaged versions in docs/ are kept: a released chart version is never rebuilt.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO_URL="https://kubemq-io.github.io/charts-next"
version="$(awk '/^version:/ {print $2}' kubemq-next/Chart.yaml)"
pkg="docs/kubemq-next-${version}.tgz"

helm lint kubemq-next --set key=lint
if [[ -f "$pkg" ]]; then
  echo "refusing to overwrite released package $pkg — bump version in kubemq-next/Chart.yaml" >&2
  exit 1
fi
helm package kubemq-next -d docs
if [[ -f docs/index.yaml ]]; then
  helm repo index docs --url "$REPO_URL" --merge docs/index.yaml
else
  helm repo index docs --url "$REPO_URL"
fi
echo "packaged $pkg"
