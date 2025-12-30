# Deploy-guide: MinaRecept på AWS EC2

Denna guide beskriver hur du sätter upp en produktionsserver från scratch på en AWS EC2-instans med Ubuntu 24.04/22.04 LTS.

## 1. Förberedelser i AWS Console

1.  **Starta en instans:**
    *   Gå till EC2 Dashboard > "Launch Instance".
    *   **Name:** MinaRecept-Prod
    *   **OS Image:** Ubuntu Server 24.04 LTS (x86)
    *   **Instance Type:** t3.small (rekommenderas för minne) eller t3.micro (gratis nivå, men kan få slut på minne vid byggen).
    *   **Key Pair:** Skapa ett nytt (t.ex. `receptapp-key`). Ladda ner `.pem`-filen.
    *   **Network settings:**
        *   Allow SSH traffic from: "My IP" (säkras) eller "Anywhere".
        *   Allow HTTPS traffic from the internet.
        *   Allow HTTP traffic from the internet.

2.  **Elastic IP (Rekommenderas):**
    *   Gå till "Elastic IPs" i menyn.
    *   "Allocate Elastic IP address".
    *   Välj den nya IP:n -> "Associate Elastic IP address" -> Välj din instans.
    *   *Detta ger dig en fast IP-adress som inte ändras vid omstart.*

## 2. Logga in på servern

Öppna din terminal på din dator.

```bash
# Ändra rättigheter på nyckeln (om du inte gjort det)
chmod 400 receptapp-key.pem

# Logga in (byt ut IP mot din Elastic IP)
ssh -i receptapp-key.pem ubuntu@<DIN-IP-ADRESS>
```

## 3. Installera systemberoenden

Kör följande kommandon på servern:

```bash
# Uppdatera paketlistor
sudo apt update && sudo apt upgrade -y

# Installera Python, pip, venv, Git, Nginx och PostgreSQL
sudo apt install -y python3-pip python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx git curl
```

## 4. Konfigurera Databas (PostgreSQL)

```bash
# Logga in som postgres-användaren
sudo -u postgres psql

# Kör följande SQL-kommandon (byt ut 'starkt_losenord' mot ett riktigt lösenord!):
CREATE DATABASE receptapp;
CREATE USER receptappuser WITH PASSWORD 'starkt_losenord';
ALTER ROLE receptappuser SET client_encoding TO 'utf8';
ALTER ROLE receptappuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE receptappuser SET timezone TO 'Europe/Stockholm';
GRANT ALL PRIVILEGES ON DATABASE receptapp TO receptappuser;
GRANT ALL ON SCHEMA public TO receptappuser;

# Avsluta psql
\q
```

## 5. Klona projektet och sätt upp miljön

```bash
# Gå till webbroten (eller hemkatalogen)
cd /home/ubuntu

# Klona repot (använd din repo-URL)
# Om det är privat, använd en Deploy Key eller Personal Access Token
git clone https://github.com/DITT-ANVÄNDARNAMN/ReceptApp.git
cd ReceptApp

# Skapa virtuell miljö
python3 -m venv venv
source venv/bin/activate

# Installera beroenden
pip install -r requirements.txt
pip install gunicorn psycopg2-binary python-dotenv

# Installera Playwright browsers (om det behövs för import, annars skippa)
# pip install playwright
# playwright install chromium
```

## 6. Miljövariabler (.env)

Skapa en `.env`-fil för produktionsinställningar:

```bash
nano .env
```

Klistra in följande (anpassa värdena!):

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=generera-en-lång-slumpmässig-sträng-här
DJANGO_ALLOWED_HOSTS=din-domän.se,api.din-domän.se,DIN-IP-ADRESS

# Databas
DATABASE_URL=postgres://receptappuser:starkt_losenord@localhost:5432/receptapp

# E-post (exempel AWS SES eller Gmail)
EMAIL_HOST=email-smtp.eu-north-1.amazonaws.com
EMAIL_PORT=587
EMAIL_HOST_USER=DITT_SES_USER
EMAIL_HOST_PASSWORD=DITT_SES_PASSWORD
DEFAULT_FROM_EMAIL=no-reply@receptapp.se

# Apple Sign-In
APPLE_CLIENT_ID=se.receptapp.ios
APPLE_TEAM_ID=XXXXXXXXXX
APPLE_KEY=ABC123DEFG
APPLE_SECRET=... (innehållet i din p8-fil, med \n för radbrytningar) ...
```
*(Spara med Ctrl+O, Enter, Ctrl+X)*

**OBS:** För att Django ska läsa `.env` automatiskt behöver vi uppdatera `manage.py` och `wsgi.py` att använda `python-dotenv`, eller ladda dem via systemd. Vi gör det via systemd nedan.

## 7. Kör migreringar och samla statiska filer

Du behöver ändra i `settings.py` för att läsa databas från URL om du inte redan gjort det, eller manuellt sätta in databasuppgifterna i `settings.py`.
*Tips: För enkelhetens skull i denna guide, uppdatera `settings.py` lokalt att använda `dj_database_url` eller läs `os.getenv` för varje DB-fält, committa och pusha.*

```bash
# Applicera migreringar
python manage.py migrate

# Skapa superuser
python manage.py createsuperuser

# Samla statiska filer (CSS/JS)
python manage.py collectstatic
```

## 8. Konfigurera Gunicorn (App Server)

Skapa en service-fil så att appen startar automatiskt:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Klistra in:

```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/ReceptApp
ExecStart=/home/ubuntu/ReceptApp/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/home/ubuntu/ReceptApp/receptapp.sock \
          receptapp_project.wsgi:application
EnvironmentFile=/home/ubuntu/ReceptApp/.env

[Install]
WantedBy=multi-user.target
```

Starta tjänsten:

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl status gunicorn
```

## 9. Konfigurera Nginx (Web Server)

Skapa en konfigurationsfil för Nginx:

```bash
sudo nano /etc/nginx/sites-available/receptapp
```

Klistra in (ersätt `DIN_DOMÄN` med din domän eller IP):

```nginx
server {
    listen 80;
    server_name DIN_DOMÄN api.DIN_DOMÄN;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    # Statiska filer
    location /static/ {
        root /home/ubuntu/ReceptApp;
    }

    # Mediafiler (uppladdade bilder)
    location /media/ {
        root /home/ubuntu/ReceptApp;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/ReceptApp/receptapp.sock;
    }
    
    # Tillåt större uppladdningar (för bilder)
    client_max_body_size 10M;
}
```

Aktivera siten:

```bash
sudo ln -s /etc/nginx/sites-available/receptapp /etc/nginx/sites-enabled
sudo nginx -t  # Testa konfigurationen
sudo systemctl restart nginx
```

## 10. Sätt upp HTTPS (Certbot)

För att appen ska fungera säkert (och för att Apple Login ska fungera) måste du ha HTTPS.

1.  Peka din domän (DNS) till EC2-instansens IP (A-record).
2.  Kör Certbot:

```bash
sudo apt install python3-certbot-nginx
sudo certbot --nginx -d DIN_DOMÄN -d api.DIN_DOMÄN
```

Följ instruktionerna. Certbot uppdaterar automatiskt Nginx-konfigurationen.

## 11. Klar!

Nu ska din app vara live på `https://DIN_DOMÄN`.

---

### Felsökning

*   **Fel 502 Bad Gateway?** Gunicorn körs inte. Kolla loggar: `sudo journalctl -u gunicorn`
*   **Statiska filer visas inte?** Kolla rättigheter på mappen `/home/ubuntu/ReceptApp/static`. `www-data` måste kunna läsa. `chmod 755 /home/ubuntu`.

