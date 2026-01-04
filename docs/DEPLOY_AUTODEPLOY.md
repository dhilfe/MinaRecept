# Auto-deploy (Raspberry Pi) — följ `stage`

Denna guide sätter upp **automatisk uppdatering** på din Raspberry Pi så att den regelbundet hämtar senaste kod från `origin/stage` och kör `docker compose up -d --build`.

Vi följer **`stage`** tills projektet är helt stabilt. Sen kan vi byta till deploy från `main`.

## Förutsättningar

- Projektet finns klonat på pajen, t.ex. `/home/bgp4/MinaRecept`
- Docker + Docker Compose fungerar (du kan köra `docker compose up -d --build`)
- Du har en fungerande `docker-compose.yml` i projektmappen
- Du har SSH-access och `sudo`

## 1) Deploy-script

Skapa filen:

- `/home/bgp4/MinaRecept/scripts/deploy_stage.sh`

Innehåll:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /home/bgp4/MinaRecept

git fetch origin
git checkout stage
git reset --hard origin/stage

docker compose up -d --build
```

Gör den körbar:

```bash
chmod +x /home/bgp4/MinaRecept/scripts/deploy_stage.sh
```

## 2) systemd service (oneshot)

Skapa filen:

- `/etc/systemd/system/minarecept-deploy.service`

Innehåll:

```ini
[Unit]
Description=MinaRecept deploy from stage
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=bgp4
WorkingDirectory=/home/bgp4/MinaRecept
ExecStart=/home/bgp4/MinaRecept/scripts/deploy_stage.sh
```

## 3) systemd timer

Skapa filen:

- `/etc/systemd/system/minarecept-deploy.timer`

Innehåll:

```ini
[Unit]
Description=Run MinaRecept deploy periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=minarecept-deploy.service

[Install]
WantedBy=timers.target
```

## 4) Aktivera

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now minarecept-deploy.timer
```

## 5) Verifiera

Status:

```bash
systemctl status minarecept-deploy.timer
```

Senaste deploy-loggar:

```bash
journalctl -u minarecept-deploy.service -n 200 --no-pager
```

## Vanliga problem

- **Fel filnamn med kolon**: om du råkar skapa `/etc/systemd/system/minarecept-deploy.timer:` (med `:`) så hittar systemd den inte. Byt namn:

```bash
sudo mv /etc/systemd/system/minarecept-deploy.timer: /etc/systemd/system/minarecept-deploy.timer
```

- **Git vill inte pulla pga lokala ändringar**: scriptet använder `git reset --hard origin/stage` som alltid slänger lokala ändringar.

- **Docker bygger långsamt**: första gången kan ta tid. Sen går det snabbare.

## Byta till `main` senare

När vi är redo för prod: byt `stage` → `main` i `deploy_stage.sh` (eller skapa `deploy_main.sh`) och uppdatera systemd-service att köra rätt script.


