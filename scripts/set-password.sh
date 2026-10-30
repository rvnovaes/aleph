#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec backend python manage.py changepassword "${1:-roberto}"
