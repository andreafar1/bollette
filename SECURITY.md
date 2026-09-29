# Sicurezza

- Non committare mai `/etc/bollette/bollette.env`.
- L'MVP ascolta sulla porta 8080 della LAN. Non esporla direttamente su Internet.
- Per accesso remoto usare VPN (es. WireGuard/Tailscale) oppure reverse proxy HTTPS con autenticazione.
- Il connettore IMAP è opzionale. Per Gmail, l'obiettivo è sostituire password/app-password con OAuth.
- I PDF possono contenere dati personali: proteggere backup e snapshot Proxmox.
