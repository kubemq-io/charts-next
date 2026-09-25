#!/usr/bin/env bash
# Package the kubemq-next chart into docs/ and refresh the Helm repo index served by GitHub Pages.
# Existing packaged versions in docs/ are kept: a released chart version is never rebuilt.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO_URL="https://kubemq-io.github.io/charts-next"
version="$(awk '/^version:/ {print $2}' kubemq-next/Chart.yaml)"
pkg="docs/kubemq-next-${version}.tgz"

helm lint kubemq-next --set licenseKey=lint
if [[ -f "$pkg" ]]; then
  echo "refusing to overwrite released package $pkg — bump version in kubemq-next/Chart.yaml" >&2
  exit 1
fi
remote_pkg="$REPO_URL/$(basename "$pkg")"
remote_status=$(curl -sSI -o /dev/null -w '%{http_code}' "$remote_pkg") || {
  echo "unable to verify whether chart version $version is already published ($remote_pkg)" >&2
  exit 1
}
case "$remote_status" in
  200)
    echo "refusing to reuse remotely published chart version $version ($remote_pkg)" >&2
    exit 1
    ;;
  404) ;;
  *)
    echo "unable to verify chart version $version: $remote_pkg returned HTTP $remote_status" >&2
    exit 1
    ;;
esac
helm package kubemq-next -d docs
if [[ -f docs/index.yaml ]]; then
  helm repo index docs --url "$REPO_URL" --merge docs/index.yaml
else
  helm repo index docs --url "$REPO_URL"
fi
duplicate_versions=$(awk '/^    version: / { print $2 }' docs/index.yaml | sort | uniq -d)
if [[ -n "$duplicate_versions" ]]; then
  echo "duplicate chart versions in docs/index.yaml: $duplicate_versions" >&2
  exit 1
fi
echo "packaged $pkg"
