#!/usr/bin/env bash
# Build and start production on the server (run in the project directory on the server).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Brak .env — skopiuj deploy/env.production.example do .env i uzupełnij."; exit 1; }
if grep -qE 'replace-with|example\.pl' .env; then
  echo "W .env zostały wartości z szablonu:"; grep -nE 'replace-with|example\.pl' .env; exit 1
fi
grep -q '^DEBUG=0' .env || { echo "Produkcja wymaga DEBUG=0 w .env"; exit 1; }
profile=(); [ -f deploy/cloudflared/config.yml ] && profile=(--profile tunnel)
docker compose "${profile[@]}" build
docker compose "${profile[@]}" up -d
echo "Czekam na API…"
for _ in $(seq 1 60); do
  [ "$(docker compose ps api --format '{{.Health}}')" = healthy ] && break; sleep 3
done
[ "$(docker compose ps api --format '{{.Health}}')" = healthy ] || { docker compose logs --tail 50 api; exit 1; }
docker compose exec -T api python manage.py check --deploy --fail-level ERROR
docker compose exec -T api python manage.py test grafik core
docker compose ps
echo "Gotowe. Sprawdź z zewnątrz: deploy/smoke.sh https://<domena>"
