#!/usr/bin/env bash
# Daily database backup (cron on the server), keeps the newest 14 dumps, then RODO retention
# (after the dump, so erased rows live on only in backups that expire within 14 days).
# cron: 15 3 * * * /opt/grafik/deploy/backup.sh >> /opt/grafik/deploy/backups/backup.log 2>&1
set -euo pipefail
umask 077  # dumps hold personal data: root only
cd "$(dirname "$0")/.."
mkdir -p deploy/backups
file="deploy/backups/grafik-$(date +%Y%m%d-%H%M).dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$file"
[ -s "$file" ] || { echo "Pusty backup: $file"; rm -f "$file"; exit 1; }
docker compose exec -T db pg_restore --list < "$file" > /dev/null  # the dump must be readable
ls -1t deploy/backups/*.dump | tail -n +15 | xargs -r rm --
echo "$(date '+%F %T') OK $file ($(du -h "$file" | cut -f1))"
docker compose exec -T api python manage.py retencja_danych
