#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source_file="${1:?Informe o arquivo JSON do LibraryThing}"
username="${2:-roberto}"
options=()
for option in "${@:3}"; do
  case "$option" in
    --dry-run|--repair-publication) options+=("$option") ;;
    *) printf 'Opção desconhecida: %s\n' "$option" >&2; exit 2 ;;
  esac
done
report="docs/librarything-$(date +%Y%m%d-%H%M%S).json"
docker compose cp "$source_file" backend:/tmp/librarything-import.json
docker compose exec -T backend python manage.py import_librarything /tmp/librarything-import.json --username "$username" --report /tmp/librarything-report.json "${options[@]}"
docker compose cp backend:/tmp/librarything-report.json "$report"
printf 'Relatório: %s\n' "$report"
