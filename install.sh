#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Esegui come root"; exit 1; }
. /etc/os-release
echo "Installazione Bollette su ${PRETTY_NAME}"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib libpq-dev git
install -d -m 750 /etc/bollette /var/lib/bollette/storage
python3 -m venv /opt/bollette/.venv
/opt/bollette/.venv/bin/pip install --upgrade pip
/opt/bollette/.venv/bin/pip install -r /opt/bollette/requirements.txt
DBPASS="$(openssl rand -hex 24)"
runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='bollette'" | grep -q 1 || runuser -u postgres -- psql -c "CREATE USER bollette WITH PASSWORD '${DBPASS}'"
runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='bollette'" | grep -q 1 || runuser -u postgres -- createdb -O bollette bollette
if [ ! -f /etc/bollette/bollette.env ]; then
  cat >/etc/bollette/bollette.env <<EOF
DATABASE_URL=postgresql+psycopg://bollette:${DBPASS}@127.0.0.1/bollette
STORAGE_DIR=/var/lib/bollette/storage
IMAP_ENABLED=false
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=
IMAP_PASSWORD=
IMAP_FOLDER=INBOX
EOF
  chmod 600 /etc/bollette/bollette.env
fi
cat >/etc/systemd/system/bollette.service <<'EOF'
[Unit]
Description=Bollette web app
After=network.target postgresql.service
[Service]
WorkingDirectory=/opt/bollette
EnvironmentFile=/etc/bollette/bollette.env
ExecStart=/opt/bollette/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
User=root
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/bollette-worker.service <<'EOF'
[Unit]
Description=Bollette mail importer
After=network.target postgresql.service
[Service]
Type=oneshot
WorkingDirectory=/opt/bollette
EnvironmentFile=/etc/bollette/bollette.env
ExecStart=/opt/bollette/.venv/bin/python -m app.worker
EOF
cat >/etc/systemd/system/bollette-worker.timer <<'EOF'
[Unit]
Description=Controllo periodico bollette
[Timer]
OnBootSec=5min
OnUnitActiveSec=30min
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now postgresql bollette.service bollette-worker.timer
IP="$(hostname -I | awk '{print $1}')"
echo
echo "Installazione completata: http://${IP:-IP_DEL_CONTAINER}:8080"
echo "Configurazione: /etc/bollette/bollette.env"
