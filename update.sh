#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Esegui come root"; exit 1; }
cd /opt/bollette
git pull --ff-only
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m compileall -q app
systemctl restart bollette
systemctl restart bollette-worker.timer
sleep 2
if ! systemctl is-active --quiet bollette; then
  echo "ERRORE: il servizio Bollette non e' partito."
  journalctl -u bollette -n 40 --no-pager
  exit 1
fi
echo "Aggiornamento completato. Servizio Bollette attivo."
