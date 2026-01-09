# MinaRecept - Att göra

## Kända problem (Known issues)

- **Instagram Reels-import:** Om ingredienserna bara syns som text i videon (overlay i frames) och inte finns i captionen eller i den bild/thumbnail som iOS delar, kan backend inte extrahera ingredienser. Workaround: dela en screenshot som innehåller ingredienserna, eller fyll i manuellt efter import.

- [x] **Välkomstsida vid första appstart**
    - [x] Skapa en välkomstsida som visas första gången appen startas (text finns sparad, se bilder på telefonen).

- [ ] **Kodkommentarer & Dokumentation**
    - [ ] Gå igenom hela kodbasen och uppdatera med relevanta kommentarer där det finns behov (funktioner, klasser, svårtolkad logik, API-kontrakt etc).

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
    - [x] Skapa repo på GitHub/GitLab
    - [x] Lägg till `origin` remote
    - [ ] Pusha `main` till `origin`
    - [x] Pusha `stage` till `origin` (första gången)
    - [ ] Slå på Branch protection för `stage`
    - [ ] Kräv GitHub Actions-status (CI) för merge till `stage`
    - [ ] (Valfritt) Blockera direkt-push till `stage` och kräv PR
    - [x] CI: kör backend + E2E på `stage` (GitHub Actions)
    - [x] CI: kör iOS XCTest på macOS (FR-20251225-03)

- [x] **iOS Share Extension (One-click save)**
    - [x] Backend API för import
    - [x] iOS Share Extension target
    - [x] Hantera delade URL:er
    - [x] Deep linking till huvudappen
    - [ ] (Fine tuning) Lägg till timing-loggar i Share Extension (t.ex. preview → thumbnail → upload → response) för att kunna pinpointa 3–10s-latens

- [x] **Robust Recept-import från URL**
    - [x] Hämta HTML från URL
    - [x] Extrahera data via JSON-LD (strukturerad data)
    - [x] Hantera URLer utan `http://` eller `https://`
    - [x] Hantera URLer som kräver `www.` (automatisk retry)
    - [x] Parsa ISO-format för tid (t.ex. PT1H30M)
    - [x] **TEST:** Verifiera import från `landleyskok.se` (fixtures)
    - [x] **TEST:** Verifiera import från `ica.se` (fixtures)
    - [x] **TEST:** Verifiera import från `coop.se` (fixtures)
    - [x] **TEST:** Verifiera import från `koket.se` (fixtures)
    - [x] Felhantering: Tydligt felmeddelande om sidan inte går att läsa
    - [x] FR-20251225-04: Import – fixtures/kompatibilitetstester för landleys/ica/coop/koket
    - [ ] **FRAMTIDA:** Förbättra text-parsning för Instagram/Sociala medier (Just nu sparas bara länk/bild/råtext)
    - [ ] **FRAMTIDA:** Bakgrundsvalidering av länkar (Kontrollera att sparade receptlänkar fortfarande fungerar, varna användaren om de är trasiga)

- [ ] **Lokalisering (Svenska)**
    - [x] Översätta statiska texter i templates
    - [x] Översätta formulär-etiketter (Labels)
    - [x] Översätta modell-namn (Verbose names)
    - [x] **TEST:** Kontrollera att alla felmeddelanden (Django forms) är på svenska
    - [x] **TEST:** Kontrollera datumformat (svensk standard i iOS)

- [x] **UI/UX Polering**
    - [x] Förbättra layout för import-sidan (tydligare instruktioner)
    - [x] Bekräftelse vid borttagning av recept (Modal eller separat sida - *Finns separat sida nu*)
    - [ ] Responsivitetstest: Meny på mobil

## Fas 2: Externa Integrationer & Avancerade funktioner

    - [ ] Lägga till så att man kan skriva in egna taggar direkt när man sparar ner ett recept (iOS + web)
        - [x] Söka/filtrera recept bland sina sparade recept på taggar (iOS
    - [ ] Smart föreslå taggar vid sparande av nytt recept (egen skrivet eller vid import)
    - [ ] Taggar är user-specifik (per användare)

- [ ] **Web/App gemensam yta och look**
    - [ ] Omarbeta utseende för webgränssnittet så att det efterliknar appen
    - [ ] Säkerställ att data som sparas på webb/app dyker upp på båda ställena oavsett vart det sparas

- [ ] **Inspiration (iOS)**
    - [ ] Lägg till en flik i appens startsida som heter ”Inspiration”
    - [ ] Innehåller en förpopulerad lista av recept (global) som användaren kan importera till sitt egna bibliotek

- [x] **iOS-spår: förutsättningar för iOS-app (backend)**
    - [x] Lägg till REST API-ramverk (DRF) + grundkonfiguration
    - [x] Token-auth för app (login → token)
    - [x] CORS-strategi för mobilapp (dev/prod)
    - [x] API-endpoints (minsta) för app-klient
        - [x] Recept: lista, detalj, skapa/uppdatera
        - [x] Inköpslistor: lista, detalj, items (skapa/uppdatera/ta bort)
        - [x] Veckoplan: hämta aktuell + uppdatera dag
        - [x] Sparade veckomenyer: lista + detalj
    - [x] Bild/media: returnera absoluta URL:er till bilder i API
    - [x] API-tester (unit) för auth + scopes (endast egna data)
    - [x] Dokumentera API-kontrakt (request/response exempel) för iOS-klienten (se docs/API.md)
    - [ ] (Senare) Push-notiser/alarmljud: strategi för iOS (native)

- [ ] **API & Arkitektur**
    - [ ] Förbereda API-endpoints (Django REST Framework?)
    - [ ] Token-baserad autentisering för API

- [ ] **Android-spår (senare): förutsättningar för Android-app**
    - [ ] Spegla iOS-spårets backend-förutsättningar (API-kontrakt + auth)
    - [ ] Verifiera push-notiser/alarmljud-strategi för Android (framtida)
    - [ ] Dokumentera bygg/deploy-flöde för Android (framtida)

- [x] **Social Inloggning (Release-krav)**
    - [x] Apple Sign-In (Backend & iOS)
    - [ ] Google Sign-In (Framtida)
    - [ ] Koppla socialt konto till befintligt konto (Framtida)

- [ ] **Avancerad Import**
    - [ ] **FR-20251226-01: OCR-tolkning av bilder (Fota recept)**
        - [x] UI för bilduppladdning
        - [x] Backend-stöd för bildhantering
        - [ ] Integration mot OCR/Vision-tjänst (OpenAI/Tesseract)
        - [ ] **TEST:** Verifiera flödet med riktig OpenAI API-nyckel
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

- [x] **FR-20251224-04: Understryk ingredienser i instruktioner**
    - [x] Understryk ingrediensnamn i "Gör så här" (receptdetalj)
    - [x] Understryk ingrediensnamn i Cook Mode steg-text
    - [x] Lägg test som verifierar understrykning

- [ ] **Minimalistisk Design**
    - [x] Rensa upp receptvyn: Fokus på Bild, Ingredienser, Steg
    - [x] Dölj metadata (datum, kategorier) tills man klickar "Visa mer"
    - [x] Rensa upp receptlistan: större fokus på bild + titel

## Fas 4: Mobilapp & Publicering

- [x] **FR-20251224-05: iOS-app (SwiftUI) MVP**
    - [x] Skapa `ios/`-projekt (XcodeGen) och checka in `project.yml`
    - [x] Implementera login (token) + lagring (Keychain)
    - [x] Receptlista (GET `/api/recipes/`)
    - [x] Receptdetalj (GET `/api/recipes/{id}/`) inkl. ingredienser + steg
    - [x] Logout

- [x] **FR-20251225-01: iOS: Inköpslistor (tab)**
    - [x] Tab "Inköpslistor" med lista av inköpslistor
    - [x] Detaljvy som visar items per inköpslista
    - [x] Visa checked-status
    - [x] Toggle checked-status och persistera via API (PATCH)

- [x] **iOS: Sätt production API URL (Release) (FR-20251225-02)**
    - [x] Bestäm riktig prod-domän/endpoint (ersätt placeholder)
    - [x] Uppdatera `ios/project.yml` (Release `INFOPLIST_KEY_API_BASE_URL`)
    - [ ] Verifiera att Release-build startar och kan logga in mot prod

- [x] **iOS: Share Extension Auth (App Groups)**
    - [ ] Konfigurera App Groups i Apple Developer Portal
    - [x] Uppdatera `project.yml` med App Group entitlements
    - [x] Dela Keychain/Token mellan huvudapp och extension (Token sparas till Shared UserDefaults)
    - [ ] Verifiera att Share Extension kan posta recept som inloggad användare

- [ ] **Mobilapp (Flutter/React Native)**
    - [ ] Grundläggande vy för receptlista
    - [ ] Inloggning via API

- [ ] **Publicering**

# --- App live checklist (sammanfattning, se docs/app_live_cheklist.md för detaljer) ---


- [x] **Backend & produktion**
    - [x] Välj och konfigurera produktionsdomän (settings förberett)
    - [ ] Sätt upp hosting för Django-backend (VPS/PaaS)
    - [x] DEBUG=False och korrekta ALLOWED_HOSTS i prod (settings.py uppdaterad)
    - [ ] Sätt upp HTTPS (TLS-cert, t.ex. Let's Encrypt)
    - [x] CORS: endast tillåt iOS-appens domän i prod (settings.py uppdaterad)
    - [x] Loggning: logga ej lösenord/tokens (settings.py uppdaterad)
    - [x] Standard-felsidor (404/500) (Templates finns)

- [ ] **Integritet & villkor**
    - [x] Publicera Privacy Policy (Integritetspolicy) på egen URL
    - [x] Publicera Terms & Conditions (Användarvillkor) på egen URL
    - [ ] Kontakt/support-sida eller e-post (ex. support@receptapp.se)

- [ ] **iOS: Produktion & Share Extension**
    - [x] Sätt production API URL i ios/project.yml (INFOPLIST_KEY_API_BASE_URL)
    - [x] Sätt versionsnummer (1.0.0) i project.yml
    - [ ] Bygg och testa Release mot prod-backend
    - [ ] Konfigurera App Groups för huvudapp + Share Extension
    - [x] Implementera delad auth/token mellan app och extension
    - [ ] Testa Share Extension mot prod-backend

- [x] **UX, lokalisering & polish**
    - [x] Gå igenom alla felmeddelanden och bekräftelser (svenska/engelska)
    - [x] Testa datum/tidsformat i appen (svensk stil: "tim", "min")
    - [ ] Testa responsivitet på små och stora skärmar

- [ ] **Testning inför App Store**
    - [ ] Säkerställ att CI körs grönt på stage/main
    - [ ] Lås in merges till stage med branch protection
    - [ ] Testa end-to-end-flöden på fysisk iPhone (konto, recept, veckomeny, inköpslista, Cook Mode, Share Extension)
    - [ ] TestFlight: ladda upp build, bjud in testers, samla feedback

- [ ] **App Store Connect & metadata**
    - [ ] Skapa App i App Store Connect (namn, bundle ID, ikon, kategori, språk)
    - [ ] Fyll i metadata (beskrivning, nyckelord, support-URL, Privacy Policy, Terms)
    - [ ] Ladda upp skärmdumpar (alla skärmstorlekar)
    - [ ] Fyll i App Privacy-formulär

- [ ] **Skicka in för review**
    - [ ] Välj build, kontrollera version/build-nummer, fyll i alla fält, submit for review
