# Feature Requests

Det här dokumentet används för att spåra feature requests när vi jobbar i brancher.

## Mall

- **ID:** FR-YYYYMMDD-XX
- **Titel:**
- **Beskrivning:**
- **Acceptanskriterier:**
- **Påverkar:** (vy/template/model/test)
- **Branch:**
- **Status:** (requested | in-progress | done | shipped)

---

## FR-20251224-01 – Git remote + push senare
- **Beskrivning:** Lägg till remote (GitHub/GitLab) och pusha till `main` vid senare tillfälle.
- **Acceptanskriterier:**
  - Remote tillagd.
  - `main` pushad.
- **Påverkar:** docs
- **Branch:** feature/fr-20251224-01-git-remote-todo
- **Status:** requested

---

## FR-20251224-02 – Stage-branch + CI-gate (unit + E2E)
- **Beskrivning:** Inför en `stage`-branch som alla feature-brancher mergas till först. Merge/PR mot `stage` ska trigga full unit + E2E (Playwright) och endast tillåtas om allt är grönt.
- **Acceptanskriterier:**
  - GitHub Actions-workflow körs på PR mot `stage` och på push till `stage`.
  - Workflow kör `./scripts/test_all.sh` (unit + E2E).
  - Branch protection på `stage` kräver workflow-status innan merge.
- **Påverkar:** CI, git-workflow
- **Branch:** feature/fr-20251224-02-stage-ci-gate
- **Status:** in-progress

---

## FR-20251224-03 – iOS-spår: förutsättningar för iOS-app
- **Beskrivning:** Skapa förutsättningar för att kunna bygga en iOS-app som använder ReceptApp (iOS-spåret). Fokus är grundarkitektur/kontrakt, inte full app-funktionalitet.
- **Målbild:** En iOS-klient kan autentisera, hämta data och använda Cook Mode/inköpslistor via en stabil backend.
- **Acceptanskriterier (iOS-spår):**
  - API-kontrakt definierat (minsta endpoints för recept, veckomeny, inköpslistor, cook/timers).
  - Autentisering för app-klient definierad (t.ex. token-baserad auth för API).
  - CORS/CSRF-strategi beskriven för mobilapp.
  - Mediehantering för bilder (upload + serving) tydliggjord.
  - CI-plan för mobil (framtida) dokumenterad.
- **Avgränsningar:**
  - Ingen native iOS-kod i denna FR (endast backend-förutsättningar + dokumentation).
- **Påverkar:** API, auth, docs
- **Branch:** feature/fr-20251224-03-ios-app-foundation
- **Leverans:** docs/API.md + /api-endpoints + API-tester
- **Status:** ready-for-merge

---

## FR-20251224-04 – Understryk ingredienser i instruktioner
- **Beskrivning:** I receptdetaljen ("Gör så här") och i Cook Mode ska ord/fraser som matchar ingredienslistan understrykas för att bli tydligare under matlagning.
- **Acceptanskriterier:**
  - Ingrediensnamn understrukna i receptdetaljens instruktioner.
  - Ingrediensnamn understrukna i Cook Mode steg-text.
  - Matchning är case-insensitiv och matchar även böjningar/plural (t.ex. "tomat" → "tomaterna").
  - Tester uppdaterade (minst E2E) som verifierar understrykning.
- **Påverkar:** templates, templatetags, tests
- **Branch:** feature/fr-20251224-04-underline-ingredients
- **Status:** ready-for-merge

---

## FR-20251224-05 – iOS-app (SwiftUI) MVP
- **Beskrivning:** Bygg en körbar iOS-app som använder ReceptApps API. Fokus på en minimal men användbar klient: login → receptlista → receptdetalj (ingredienser + steg) → Cook Mode.
- **Acceptanskriterier:**
  - App kan logga in mot `/api/auth/token/` och spara token lokalt.
  - App kan hämta `/api/recipes/` och visa lista.
  - App kan visa detaljvy för recept och rendera ingredienslistan (parsar `ingredients` JSON-strängen).
  - App har en enkel Cook Mode-vy (steg-för-steg) med Nästa/Föregående.
  - Cook Mode detekterar tidsuttryck (t.ex. "10 min", "1 h 30 min") och kan starta en nedräkning.
  - Logout rensar token och återgår till login.
  - Projekt kan genereras/byggas via Xcode (scaffold via XcodeGen).
- **Avgränsningar:**
  - Ingen inköpslista/veckoplan i iOS i denna FR (kommer senare).
- **Påverkar:** ios/, docs
- **Branch:** feature/fr-20251224-05-ios-app-mvp
- **Status:** ready-for-merge

---

## FR-20251225-01 – iOS: Inköpslistor (tab)
- **Beskrivning:** Lägg till en enkel "Inköpslistor"-tab i iOS-appen som kan visa användarens inköpslistor och rader via API.
- **Acceptanskriterier:**
  - Tabbar: "Mina recept" och "Inköpslistor".
  - Inköpslistor: lista (`GET /api/shopping-lists/`).
  - Inköpslista detalj: visar items för vald lista (`GET /api/shopping-list-items/?shopping_list={id}`).
  - Checked-status visas tydligt för items.
- **Avgränsningar:**
  - Ingen CRUD i iOS i denna FR (endast läsa/visa).
- **Påverkar:** ios/, docs
- **Branch:** feature/fr-20251225-01-ios-shopping-lists
- **Status:** ready-for-merge
