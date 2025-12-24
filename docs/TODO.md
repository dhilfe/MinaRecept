# ReceptApp - Att göra

## Fas 1: Grundläggande MVP (Klar & Testad)

- [x] **Projektstruktur & Layout**
    - [x] Django-projekt uppsatt
    - [x] Bootstrap 5 integrerat
    - [x] Responsiv grundlayout (Navbar, Footer)

- [x] **Datamodeller**
    - [x] User-modell (standard Django)
    - [x] Recipe-modell (titel, ingredienser, steg, bild, etc.)
    - [x] Koppling mellan User och Recipe

- [x] **Autentisering**
    - [x] Inloggning (användarnamn/lösenord)
    - [x] Utloggning
    - [x] Skyddade vyer (@login_required)

- [x] **Recept-hantering (CRUD)**
    - [x] Skapa recept
    - [x] Lista recept ("Mina recept")
    - [x] Visa receptdetaljer
    - [x] Redigera recept
    - [x] Ta bort recept
    - [x] Bilduppladdning

- [x] **Veckomeny**
    - [x] Visa veckomeny (Mån-Sön)
    - [x] Lägga till recept i veckomeny
    - [x] Ta bort recept från veckomeny
    - [x] Tömma veckomeny

- [x] **Slumpgenerator**
    - [x] Slumpa fram en hel vecka
    - [x] Filtrera på taggar/kategorier vid slumpning

## Fas 1.5: Förbättringar & Robusthet (Pågående)

- [ ] **Git / Remote**
    - [ ] Skapa repo på GitHub/GitLab
    - [ ] Lägg till `origin` remote
    - [ ] Pusha `main` till `origin`
    - [ ] Pusha `stage` till `origin` (första gången)
    - [ ] Slå på Branch protection för `stage`
    - [ ] Kräv GitHub Actions-status (CI) för merge till `stage`
    - [ ] (Valfritt) Blockera direkt-push till `stage` och kräv PR

- [ ] **Robust Recept-import från URL**
    - [x] Hämta HTML från URL
    - [x] Extrahera data via JSON-LD (strukturerad data)
    - [x] Hantera URLer utan `http://` eller `https://`
    - [x] Hantera URLer som kräver `www.` (automatisk retry)
    - [x] Parsa ISO-format för tid (t.ex. PT1H30M)
    - [ ] **TEST:** Verifiera import från `landleyskok.se` (Användare)
    - [ ] **TEST:** Verifiera import från `ica.se`
    - [ ] **TEST:** Verifiera import från `coop.se`
    - [ ] **TEST:** Verifiera import från `koket.se`
    - [ ] Felhantering: Tydligt felmeddelande om sidan inte går att läsa
    - [ ] **FRAMTIDA:** Förbättra text-parsning för Instagram/Sociala medier (Just nu sparas bara länk/bild/råtext)
    - [ ] **FRAMTIDA:** Bakgrundsvalidering av länkar (Kontrollera att sparade receptlänkar fortfarande fungerar, varna användaren om de är trasiga)

- [ ] **Lokalisering (Svenska)**
    - [x] Översätta statiska texter i templates
    - [x] Översätta formulär-etiketter (Labels)
    - [x] Översätta modell-namn (Verbose names)
    - [ ] **TEST:** Kontrollera att alla felmeddelanden (Django forms) är på svenska
    - [ ] **TEST:** Kontrollera datumformat (svensk standard)

- [ ] **UI/UX Polering**
    - [ ] Förbättra layout för import-sidan (tydligare instruktioner)
    - [ ] Bekräftelse vid borttagning av recept (Modal eller separat sida - *Finns separat sida nu*)
    - [ ] Responsivitetstest: Meny på mobil

## Fas 2: Externa Integrationer & Avancerade funktioner

- [ ] **API & Arkitektur**
    - [ ] Förbereda API-endpoints (Django REST Framework?)
    - [ ] Token-baserad autentisering för API

- [ ] **Social Inloggning**
    - [ ] Google Sign-In
    - [ ] Apple Sign-In
    - [ ] Koppla socialt konto till befintligt konto

- [ ] **Avancerad Import**
    - [ ] OCR-tolkning av bilder (Fota recept)
    - [ ] Webbläsartillägg

## Fas 3: Anchovy-inspirerad UX (Fokus på matlagning)

- [x] **"Cook Mode" (Steg-för-steg läge)**
    - [x] Ny vy som visar ett steg i taget i fullskärm
    - [x] Stor, tydlig typografi
    - [x] Navigering (Nästa/Föregående) med stora knappar eller swipe
    - [x] "No-sleep" funktion (förhindra att skärmen släcks)
    - [x] Timers synliga även när man byter steg
    - [x] Portions-skalning i Cook Mode
    - [x] Bocka av ingredienser (persistens per recept)

- [x] **Interaktiva Timers**
    - [x] Detektera tidsangivelser i texten (t.ex. "koka i 10 min")
    - [x] Gör dem klickbara för att starta en nedräkning direkt i vyn

- [ ] **Minimalistisk Design**
    - [x] Rensa upp receptvyn: Fokus på Bild, Ingredienser, Steg
    - [x] Dölj metadata (datum, kategorier) tills man klickar "Visa mer"
    - [x] Rensa upp receptlistan: större fokus på bild + titel

## Fas 4: Mobilapp & Publicering

- [ ] **Mobilapp (Flutter/React Native)**
    - [ ] Grundläggande vy för receptlista
    - [ ] Inloggning via API

- [ ] **Publicering**
    - [ ] Terms & Conditions (Användarvillkor) innan publik lansering
    - [ ] App Store
    - [ ] Google Play
