# Deploy-guide: MinaRecept på Raspberry Pi med Docker

Denna guide beskriver hur du sätter upp en produktionsserver på en Raspberry Pi (4 eller 5 rekommenderas) med Docker. Detta är en kostnadseffektiv och flyttbar lösning.

## Strategi
Vi använder **Docker Compose** för att köra:
1.  **Django** (Appen)
2.  **PostgreSQL** (Databasen)
3.  **Nginx** (För statiska filer och proxy)
4.  **Cloudflare Tunnel** (För att exponera appen säkert mot internet utan att öppna portar i routern)

## 1. Förbered Raspberry Pi (OS & Säkerhet)

### A. Installera OS
1.  Ladda ner **Raspberry Pi Imager**.
2.  Välj OS: **Raspberry Pi OS Lite (64-bit)**. (Välj *inte* Desktop-versionen, den tar onödiga resurser).
3.  Klicka på kugghjulet (inställningar) innan du skriver:
    *   Sätt hostname: `receptapp-pi`
    *   Aktivera SSH -> "Use password authentication" (eller public key om du kan det).
    *   Sätt username: `pi` (eller valfritt).
    *   Konfigurera Wi-Fi om du inte kör kabel (kabel rekommenderas starkt!).
4.  Skriv till SD-kortet och stoppa in i Pajen. Starta upp.

### B. Hitta IP och logga in
Kolla i din router vilken IP den fick, eller kör `ping receptapp-pi.local` i terminalen.
```bash
ssh pi@receptapp-pi.local
# eller
ssh pi@192.168.x.x
```

### C. Säkra upp servern (Viktigt!)
Kör dessa kommandon på Pajen:

```bash
# Uppdatera allt
sudo apt update && sudo apt upgrade -y

# Installera brandvägg
sudo apt install ufw -y
sudo ufw allow ssh
sudo ufw enable
# (Vi behöver inte öppna port 80/443 om vi använder Cloudflare Tunnel!)

# Installera Fail2Ban (skyddar mot brute-force på SSH)
sudo apt install fail2ban -y
```

## 2. Installera Docker

Vi använder det officiella installationsscriptet:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Lägg till din användare i docker-gruppen så du slipper skriva 'sudo' hela tiden
sudo usermod -aG docker $USER

# Logga ut och in igen för att det ska gälla
exit
# (Logga in igen med ssh...)
```

Verifiera att det funkar:
```bash
docker ps
# Ska inte ge "permission denied"
```

## 3. Förbered projektet på Pajen

Vi ska flytta din kod till Pajen. Det enklaste är att använda `git`.

### A. Generera SSH-nyckel på Pajen (för GitHub)
```bash
ssh-keygen -t ed25519 -C "din@email.com"
cat ~/.ssh/id_ed25519.pub
```
Kopiera nyckeln och lägg till den på GitHub under Settings -> SSH and GPG keys.

### B. Klona repot
```bash
git clone git@github.com:DITT-ANVÄNDARNAMN/ReceptApp.git
cd ReceptApp
```

### C. Skapa .env.prod
Skapa filen med dina hemligheter:
```bash
nano .env.prod
```

Klistra in detta (anpassa värdena!):

```ini
DEBUG=0
SECRET_KEY=en-lång-slumpmässig-sträng-här-som-du-hittar-på
DJANGO_ALLOWED_HOSTS=receptapp-pi,localhost,127.0.0.1,DIN-DOMÄN.se
DATABASE=postgres

# Databas (matcha docker-compose.yml)
SQL_ENGINE=django.db.backends.postgresql
SQL_DATABASE=receptapp
SQL_USER=receptapp_user
SQL_PASSWORD=ett_hemligt_db_lösenord
SQL_HOST=db
SQL_PORT=5432
DATABASE_URL=postgres://receptapp_user:ett_hemligt_db_lösenord@db:5432/receptapp

# Postgres Container Env
POSTGRES_DB=receptapp
POSTGRES_USER=receptapp_user
POSTGRES_PASSWORD=ett_hemligt_db_lösenord

# Apple Sign-In
APPLE_CLIENT_ID=se.receptapp.ios
APPLE_TEAM_ID=XXXXXXXXXX
APPLE_KEY=ABC123DEFG
APPLE_SECRET=... (innehållet i din p8-fil, allt på en rad med \n, eller hantera filen separat) ...
```

*(Spara med Ctrl+O, Enter, Ctrl+X)*

## 4. Exponera mot nätet (Cloudflare Tunnel)

Detta är det absolut smidigaste sättet.

1.  Skaffa en domän på Cloudflare (eller flytta DNS dit). Det är gratis DNS-hantering.
2.  Gå till **Zero Trust** -> **Networks** -> **Tunnels** i Cloudflare Dashboard.
3.  Klicka "Create a Tunnel". Välj "Cloudflared" (docker).
4.  Namnge den, t.ex. "hemma-pi".
5.  Du får ett kommando som ser ut typ: `docker run cloudflare/cloudflared:latest tunnel --token EY...`
    *   Kopiera **token**-delen (strängen efter `--token`).
6.  Spara denna token i din `.env.prod`:
    ```ini
    CLOUDFLARE_TUNNEL_TOKEN=EY...
    ```
7.  Avkommentera `tunnel`-tjänsten i din `docker-compose.yml` (ta bort `#` framför raderna).
8.  I Cloudflare Dashboard, klicka "Next" och konfigurera "Public Hostname":
    *   **Subdomain:** `api` (eller vad du vill, t.ex. bara root `@`).
    *   **Domain:** `dindomän.se`.
    *   **Service:** `http://nginx:80` (Viktigt! Vi pekar på nginx-containern, inte localhost).

## 5. Starta allt!

Nu smäller vi igång det.

```bash
docker compose up -d --build
```

Docker kommer nu att:
1.  Bygga din Django-app.
2.  Ladda hem Postgres och Nginx.
3.  Starta upp databasen.
4.  Köra migreringar (tack vare `entrypoint.sh`).
5.  Starta tunneln.

### Verifiera
```bash
docker compose logs -f
```
Se så att allt ser grönt ut.

Om du använde Cloudflare Tunnel ska du nu kunna surfa till `https://dindomän.se/admin` och se inloggningen! HTTPS fungerar automatiskt.

## 6. Underhåll

**Uppdatera appen:**
```bash
git pull
docker compose up -d --build
```
Då byggs den nya koden in i containern och den startas om. Databasen ligger kvar säkert i sin volym.

**Backup:**
För att ta backup på databasen:
```bash
docker exec -t receptapp_db pg_dumpall -c -U receptapp_user > dump_`date +%d-%m-%Y"_"%H_%M_%S`.sql
```
Spara `.sql`-filen på en annan dator/molnet.

