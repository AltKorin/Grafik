#!/usr/bin/env bash
# Smoke test of a running instance from the outside. Usage: deploy/smoke.sh https://grafik.firma.pl
set -uo pipefail
base="${1:?Podaj adres, np. https://grafik.firma.pl}"; base="${base%/}"
fails=0
check() { if eval "$2"; then echo "OK    $1"; else echo "BŁĄD  $1"; fails=$((fails + 1)); fi; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@"; }
check "API zdrowe" '[ "$(code "$base/api/health/")" = 200 ]'
check "bez pętli przekierowań (max 3)" '[ "$(code -L --max-redirs 3 "$base/api/health/")" = 200 ]'
check "panel" '[ "$(code "$base/panel")" = 200 ]'
check "logowanie admina" '[ "$(code "$base/admin/login/")" = 200 ]'
check "statyki admina" '[ "$(code "$base/static/admin/css/base.css")" = 200 ]'
headers="$(curl -s -D - -o /dev/null --max-time 15 "$base/api/session/")"  # GET: HEAD sets no cookie
check "nagłówek CSP" 'grep -qi "^content-security-policy:" <<<"$(curl -sI --max-time 15 "$base/panel")"'
check "API prywatne (no-store)" 'grep -qi "cache-control: private, no-store" <<<"$headers"'
check "zły token = 404" '[ "$(code "$base/api/nfc/$(head -c 32 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 43)/")" = 404 ]'
if [[ "$base" == https://* ]]; then
  host="${base#https://}"
  check "http → https" '[[ "$(curl -s -o /dev/null -w "%{redirect_url}" --max-time 15 "http://$host/panel")" == https://* ]]'
  check "ciasteczka Secure" 'grep -qi "set-cookie: csrftoken=.*secure" <<<"$headers"'
fi
echo; [ "$fails" -eq 0 ] && echo "Wszystko OK." || { echo "Błędów: $fails"; exit 1; }
