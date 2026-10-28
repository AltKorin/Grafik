#!/usr/bin/env bash
# Create the Grafik LXC on proxmox-hp, install Docker and the deploy key (run by Konrad, never by the agent).
# Usage, in a normal terminal on the laptop: ssh proxmox-hp 'bash -s' < deploy/lxc-create.sh
set -euo pipefail
PUBKEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMcHdZYsiTt/ctmJTJQcsZ+To+VdguE5luUcP5T5f6Im grafik-deploy'

pveam update >/dev/null
TMPL=$(pveam available --section system | awk '/debian-13-standard_.*_amd64/ {print $2}' | sort -V | tail -1)
case "$TMPL" in *_amd64.tar.*) ;; *) echo "Zły szablon: '$TMPL'"; exit 1;; esac
pveam list local | grep -q "$TMPL" || pveam download local "$TMPL"
VMID=$(pvesh get /cluster/nextid)
# No PDF rendering here: Postgres + API + Caddy + cloudflared fit in 2 GB; swap covers the frontend build.
pct create "$VMID" "local:vztmpl/$TMPL" \
  --hostname grafik \
  --cores 2 --memory 2048 --swap 1024 \
  --rootfs local-lvm:12 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 --features nesting=1,keyctl=1 \
  --onboot 1 --start 1
sleep 8

pct exec "$VMID" -- env PUBKEY="$PUBKEY" bash -s <<'EOF'
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl openssh-server rsync
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<'SRC'
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
SRC
apt-get update -q
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker ssh
docker info --format 'Storage driver: {{.Driver}}'
mkdir -p -m 700 /root/.ssh /root/.cloudflared
echo "$PUBKEY" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys
mkdir -p /opt/grafik
EOF

echo "=== GRAFIK VMID=$VMID IP=$(pct exec "$VMID" -- hostname -I | awk '{print $1}') $(pct config "$VMID" | grep -o 'hwaddr=[^,]*')"
