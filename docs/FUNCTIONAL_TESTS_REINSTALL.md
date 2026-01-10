# Funktionstester vid ominstallation (iOS)

Syfte: snabb, reproducerbar checklista för att verifiera att app + backend fungerar korrekt efter att du installerat om appen (och ev. driftsatt senaste backend på stage/prod).

## Bra att ha: backend-kommandon (Docker Compose)

Kör i mappen där din `docker-compose.yml` ligger.

- Status:
  - `docker compose ps`
  - `docker compose images`

- Start (i bakgrunden):
  - `docker compose up -d`

- Stoppa:
  - `docker compose down`

- Rebuild + start (vanligast efter kodändring):
  - `docker compose up -d --build`

- Tvinga “ren” rebuild (om du misstänker cache-problem):
  - `docker compose build --no-cache`
  - `docker compose up -d`

- Loggar:
  - Alla services: `docker compose logs -f --tail=200`
  - En specifik service (ex `web`): `docker compose logs -f --tail=200 web`

- In i containern (ex `web`):
  - `docker compose exec web bash`

- Django-admin i container (ex `web`):
  - Migrations: `docker compose exec web python manage.py migrate`
  - Skapa migrations: `docker compose exec web python manage.py makemigrations`
  - Collectstatic: `docker compose exec web python manage.py collectstatic --noinput`

- Snabb felsökning:
  - Se env i service: `docker compose exec web env | sort`
  - Starta om bara `web`: `docker compose restart web`

## Förutsättningar
- Du testar mot rätt miljö (t.ex. stage) och har nät.
- Backend är uppdaterad och migrations är körda (om du nyss deployat).
- Du har minst ett testkonto (Apple-login) och gärna ett “tomt” konto.

## 0) Ren ominstallation
- Avinstallera appen helt.
- Installera om.
- Starta appen.

**Förväntat:** appen startar utan crash, och UI är ljus (Light Mode) överallt.

## 1) Inloggning
- Logga in (Apple).

**Förväntat:** du hamnar i appen utan felmeddelanden.

## 2) Home / Receptlista (Grundflöden)
- Gå till receptlistan.
- Pull-to-refresh.
- Öppna ett recept.

**Förväntat:** recept laddas, detaljsidan laddas, inga “tomma” listor om du har data på kontot.

## 3) Kokböcker (0-by-default + skapa via “Lägg till i kokbok”)
### 3.1 Tomt konto (viktigt)
- Med ett konto som inte har kokböcker: öppna ett recept.
- Tryck “Lägg till i kokbok”.

**Förväntat:**
- Du ser tomt tillstånd (“Du har inga kokböcker än”).
- Du kan skapa en kokbok via namn-prompten (Lägg till/Avbryt).
- Efter skapande: receptet läggs till i den kokboken och sheet stängs.

### 3.2 Befintliga kokböcker
- Med ett konto som har kokböcker: öppna ett recept.
- Tryck “Lägg till i kokbok”.
- Välj en kokbok.

**Förväntat:** receptet läggs till och sheet stängs utan fel.

### 3.3 Kokbok-listning + navigering
- Gå till “Dina kokböcker” på Home.
- Verifiera att kokbokskorten visar thumbnails (om kokboken har recept med bild/url).
- Tryck på en kokbok.

**Förväntat:** du ser en lista med recepten i kokboken; raderna har thumbnail + titel.

## 4) Inköpslistor (A)
### 4.1 Lista listor
- Öppna fliken Inköpslistor.

**Förväntat:**
- Om du saknar listor: modern empty state + knapp “Skapa lista”.
- Om listor finns: raderna visar ikon, namn, count, datum (och “Stående” om återkommande).

### 4.2 Skapa stående lista
- Skapa en ny stående lista via menyn “Ny lista”.

**Förväntat:** listan skapas och dyker upp i listan.

### 4.3 Detaljvy
- Öppna en inköpslista.

**Förväntat:**
- Om tom: empty state + “Lägg till vara”.
- Rader visar namn + (valfritt) mängd/enhet på en andra rad.

### 4.4 Bocka av / grönt check
- Tryck på en rad för att bocka av.

**Förväntat:** ikonen blir grön checkmark och texten stryks; tryck igen togglar tillbaka.

### 4.5 Lägg till en vara manuellt
- Tryck “+” och lägg till:
  - Namn: Mjölk
  - Mängd: 1
  - Enhet: l

**Förväntat:** varan syns i listan med (mängd/enhet) på egen rad.

### 4.6 Lägg till från recept – hela listan
- I ett recept: tryck “Lägg till i inköpslista”.

**Förväntat:** ingredienserna läggs till i huvudlistan (om det är vad knappen gör i din version).

### 4.7 Lägg till från recept – enskild ingrediens
- I ett recept: tryck kundvagn/knapp vid en enskild ingrediensrad.

**Förväntat:** endast den valda ingrediensen läggs till (inte alla).

## 5) Portioner/Servings och skalning av ingredienser (kritisk)
- Öppna ett recept som har numeriska mängder (t.ex. “2 dl …”).
- Gå till redigera recept.
- Ändra “Portioner” från t.ex. 4 → 8.
- Spara.
- Öppna receptet igen och kontrollera ingrediensmängder.

**Förväntat:**
- `servings` uppdateras.
- Mängderna i ingredienslistan är skalade (ex: 2 dl → 4 dl).

## 6) Skapa recept (C)
- Skapa ett nytt recept via “Nytt recept”.
- Fyll i:
  - Titel
  - Portioner
  - Tid
  - Ingredienser (flera rader)
  - Steg (flera rader)
- Spara.

**Förväntat:** receptet skapas, dyker upp i listan, och ingredienser visas korrekt.

## 7) Redigera recept (C)
- Öppna ett recept och välj redigera.
- Ändra titel, tid, portioner, taggar.
- Spara.

**Förväntat:** uppdateringar syns direkt efter sparande; fel visas som bottom-banner om något går fel.

## 8) Snabb regression check
- Logga ut och logga in igen.
- Testa pull-to-refresh på receptlistan.
- Öppna ett par recept med/utan bilder.

**Förväntat:** inget crash, inga konstiga tomlägen.

## Noteringar / felsökning (om något fallerar)
- Skriv ned:
  - Vilket teststeg (t.ex. “5) Portioner-skalning”).
  - Kontots status (tomt konto eller befintlig data).
  - Exakt felmeddelande i appen.
  - Om backend nyligen deployats: vilken branch/commit och om migrations körts.
