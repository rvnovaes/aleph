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
docker compose run --rm -T --no-deps --user 1000 backend tar -C /data -I 'gzip -1' -cf - pdfs > "$destination/pdfs.tar.gz"
cp .env compose.yml "$destination/"
(cd "$destination" && sha256sum database.dump pdfs.tar.gz > SHA256SUMS)
touch "$destination/complete"
# Keep three complete copies; the PDF collection makes fourteen daily copies exceed disk capacity.
# Incomplete attempts are retained for investigation. Off-server copies are cumulative.
mapfile -t completed < <(find /opt/aleph/backups -mindepth 2 -maxdepth 2 -name complete -printf '%h\n' | sort -r)
for old in "${completed[@]:3}"; do rm -rf -- "$old"; done
echo "$destination"
