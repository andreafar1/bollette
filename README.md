# Bollette

Dashboard self-hosted per gestire bollette in un container LXC Debian 13 su Proxmox.

## Funzioni MVP
- Dashboard web responsive
- Bollette pagate / da pagare / scadute
- Inserimento manuale
- Upload PDF con estrazione euristica di importo, scadenza e gestore
- PostgreSQL
- Worker periodico systemd
- Connettore IMAP opzionale per allegati PDF
- Dati e segreti fuori dal repository Git

## Installazione su LXC Proxmox
Crea un CT Debian 13 (consigliati 2 vCPU, 2 GB RAM, 20 GB disco), entra come root e lancia:

```bash
apt update && apt install -y git
git clone https://github.com/andreafar1/bollette.git /opt/bollette
cd /opt/bollette
chmod +x install.sh update.sh
./install.sh
```

Poi apri `http://IP_DEL_CONTAINER:8080`.

## Configurazione
File locale: `/etc/bollette/bollette.env`.
I PDF sono salvati in `/var/lib/bollette/storage`.

Per IMAP compila le variabili `IMAP_*` nel file env e imposta `IMAP_ENABLED=true`.
Per Gmail è preferibile in futuro il connettore OAuth; non mettere password nel repository.

## Aggiornamento
```bash
cd /opt/bollette
sudo ./update.sh
```

## Servizi
```bash
systemctl status bollette
systemctl status bollette-worker.timer
journalctl -u bollette -f
```

> MVP: l'estrazione PDF è euristica e va verificata dall'utente. I connettori diretti ai portali dei gestori non sono ancora inclusi.
