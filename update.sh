#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Esegui come root"; exit 1; }
cd /opt/bollette
git pull --ff-only
.venv/bin/pip install -r requirements.txt
systemctl restart bollette
systemctl restart bollette-worker.timer
echo "Aggiornamento completato."
