#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
destination="${1:-backups/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$destination"
chmod 700 "$destination"
# Prevent writes while taking the matching database/file snapshot.
docker compose stop backend
trap 'docker compose start backend >/dev/null' EXIT
docker compose exec -T db pg_dump -U aleph -d aleph -Fc > "$destination/database.dump"
docker compose run --rm -T --no-deps --user 1000 backend tar -C /data -czf - pdfs > "$destination/pdfs.tar.gz"
chmod 600 "$destination"/*
echo "Backup salvo em $destination"
