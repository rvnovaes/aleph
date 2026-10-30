#!/usr/bin/env bash
set -euo pipefail
umask 077
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$repo_root/backups/production"
# SSH uses the configured aleph host and identity. Nothing is uploaded.
rsync -az --partial --chmod=D700,F600 aleph:/opt/aleph/backups/ "$repo_root/backups/production/"
