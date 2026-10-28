# Grafik na proxmox-hp

**Stan 28.10.2026: produkcja https://grafik.sudomie.pl** — LXC **108** `grafik` (Debian 13, 2 GB + 1 GB swap,
12 GB), alias `grafik-prod` (`~/.ssh/config`, klucz `~/.ssh/id_ed25519_grafik`). Tunel `grafik` z terminala:
cert konta w `/root/.cloudflared/cert.pem`, `config.yml` + poświadczenia w `/opt/grafik/deploy/cloudflared/`.
Admin `konrad`: hasło w `/root/grafik-start.txt` (600). Backup: cron 03:15 UTC → `deploy/backups/` (700/600).
Port 8090 tylko na 127.0.0.1. Do zrobienia: rezerwacja DHCP na routerze (MAC w `pct config 108`).

Wzór: HotelAgenda `deploy/PROXMOX-HP.md`. Zasada: **agent nigdy nie dostaje hypervisora** — Konrad tworzy LXC,
agent dostaje alias SSH `grafik-prod` z osobnym kluczem `~/.ssh/id_ed25519_grafik` i robi resztę.

## 1. LXC + Docker + klucz — Konrad, zwykły terminal (hasło do proxmox-hp, `!` w Claude Code nie ma TTY)

```bash
ssh proxmox-hp 'bash -s' < ~/Claude/Grafik/deploy/lxc-create.sh
```

Ostatnia linia: `=== GRAFIK VMID=… IP=… hwaddr=…`. IP → `~/.ssh/config` (alias `grafik-prod`), MAC → rezerwacja DHCP na routerze.

## 2. Tunel Cloudflare z terminala (cloudflared w kontenerze na LXC, własny `tunnel login`)

`docker run --rm --user 0 -v /root/.cloudflared:/root/.cloudflared cloudflare/cloudflared:2026.9.3 tunnel login`
→ link w przeglądarce (strefa sudomie.pl) → *Authorize*. **Login musi czekać** (28.10: `timeout 600`) — wtedy
cloudflared sam pobiera `cert.pem` na serwer; ubity po wyciągnięciu linku nie odbierze certu (pierwsza próba przepadła). Potem `tunnel create grafik`,
`tunnel route dns grafik grafik.sudomie.pl`, `config.yml` + `<UUID>.json` w `/opt/grafik/deploy/cloudflared/`
(uid 65532, 400; `push.sh` tego katalogu nie nadpisuje).

## 3. Aplikacja — agent

`deploy/push.sh grafik-prod:/opt/grafik` → `.env` z `env.production.example` (sekrety generowane na serwerze)
→ `deploy/deploy.sh` → konto admina → `deploy/smoke.sh https://grafik.sudomie.pl` → cron `backup.sh`.

Rollback: `vzdump <VMID> --storage local --compress zstd --mode snapshot` (Konrad, na proxmox-hp).
