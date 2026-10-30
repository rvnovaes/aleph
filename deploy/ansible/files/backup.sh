#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/aleph
exec 9>/opt/aleph/operation.lock
flock -n 9 || { echo "Another backup/deploy is running" >&2; exit 1; }
destination="/opt/aleph/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$destination"
was_running="$(docker compose ps --status running -q backend)"
if [[ -n "$was_running" ]]; then
    docker compose stop backend
    trap 'docker compose start backend >/dev/null' EXIT
fi
docker compose exec -T db pg_dump -U aleph -d aleph -Fc > "$destination/database.dump"
docker compose run --rm -T --no-deps --user 1000 backend tar -C /data -czf - pdfs > "$destination/pdfs.tar.gz"
cp .env compose.yml "$destination/"
(cd "$destination" && sha256sum database.dump pdfs.tar.gz > SHA256SUMS)
touch "$destination/complete"
# Keep a fortnight of completed backups; incomplete attempts are retained for investigation.
find /opt/aleph/backups -mindepth 2 -maxdepth 2 -name complete -mtime +14 -print0 |
while IFS= read -r -d '' marker; do rm -rf -- "$(dirname "$marker")"; done
echo "$destination"
