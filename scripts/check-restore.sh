#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
backup="$(realpath "${1:?Informe a pasta do backup}")"
test -s "$backup/database.dump"
test -s "$backup/pdfs.tar.gz"
database="aleph_restore_$(date +%s)"
docker compose exec -T db createdb -U aleph "$database"
trap 'docker compose exec -T db dropdb -U aleph "$database" >/dev/null' EXIT
docker compose exec -T db pg_restore -U aleph -d "$database" --exit-on-error < "$backup/database.dump"
docker compose exec -T db psql -U aleph -d "$database" -c 'SELECT count(*) AS registros FROM catalog_work; SELECT count(*) AS arquivos FROM catalog_document;'
# Extract into a disposable directory, then check every PDF against its stored hash.
docker compose exec -T db psql -U aleph -d "$database" -At -c "SELECT sha256 || '  pdfs/' || file FROM catalog_document ORDER BY id" > "$backup/pdf-checksums.txt"
validation_dir="$(mktemp -d /tmp/aleph-restore-XXXXXX)"
tar -xzf "$backup/pdfs.tar.gz" -C "$validation_dir"
if test -s "$backup/pdf-checksums.txt"; then
    (cd "$validation_dir" && sha256sum -c "$backup/pdf-checksums.txt")
fi
echo "Banco restaurado em base temporária e PDFs extraídos em $validation_dir."
