
⸻

🧱 Steg 1 – Backend & produktion (domän, hosting, API)

Mål: Stabil, säker prod-backend som iOS-appen kan prata med.
	•	Välj prod-domän
	•	Ex: receptapp.se eller app.dindomän.se.
	•	Ska användas både för:
	•	API, t.ex. api.receptapp.se
	•	Webb (om du vill), t.ex. receptapp.se
	•	Privacy Policy / Terms-länkar.
	•	Välj hosting för Django-backend
	•	VPS (t.ex. Hetzner/Contabo), PaaS (Railway, Render, Fly.io, etc.) eller liknande.
	•	Se till att:
	•	Du kör med produktionsserver (Gunicorn/Uvicorn + Nginx/liknande).
	•	DEBUG = False i prod.
	•	Korrekt ALLOWED_HOSTS (domän + ev. IP vid test).
	•	Sätt upp HTTPS
	•	Lägg på TLS-cert (t.ex. via Let’s Encrypt) på din prod-domän.
	•	Verifiera att alla API-anrop från appen går mot https://....
	•	CORS & auth för mobil
	•	Konfigurera CORS så att iOS-klienten får prata med API:et (domain-baserat, inte * i prod).
	•	Verifiera att token-auth endast ger åtkomst till egna recept/veckomenyer/inköpslistor (vilket du redan testat i API-testerna, men gör en “prod sanity-check”).
	•	Loggning & felhantering
	•	Ha logging på servern (info/error) men logga inte lösenord eller tokens.
	•	Standard-felsidor (500/404) – inget intern stacktrace till användare.

⸻

🔐 Steg 2 – Integritet, GDPR, villkor

Mål: Ha allt legalt på plats för App Store + EU-användare.
	•	Privacy Policy (Integritetspolicy)
	•	Skriv en enkel sida: vad du lagrar (konto, recept, bilder, metadata).
	•	Förklara kort:
	•	Hur data används.
	•	Hur användare kan begära radering (t.ex. maila support).
	•	Publicera på en URL, t.ex. https://receptapp.se/privacy.
	•	Terms & Conditions (Användarvillkor)  (matchar din TODO under “Publicering”)
	•	Beskriv:
	•	Vad appen gör.
	•	Ansvarsbegränsning (t.ex. inga garantier etc).
	•	Vad som gäller för användarkonton.
	•	Publicera på https://receptapp.se/terms.
	•	Kontakt & support
	•	Skapa enkel sida eller mailadress för support, t.ex. support@receptapp.se.
	•	Använd samma adress i App Store Connect.

⸻

📱 Steg 3 – iOS-projektet (konkret kopplat till din TODO)

Mål: Huvudapp + Share Extension korrekt konfigurerade för prod.
	•	Slutför “iOS: Sätt production API URL (FR-20251225-02)”
	•	Bestäm slutgiltig API-bas-URL, t.ex. https://api.receptapp.se.
	•	Uppdatera ios/project.yml → INFOPLIST_KEY_API_BASE_URL för Release.
	•	Builda en Release (Archive) och verifiera att appen:
	•	Startar.
	•	Kan logga in mot prod-backend.
	•	Hämtar receptlista/receptdetalj utan att du ändrar något manuellt.
	•	App Groups + Share Extension Auth
	•	Kopplat till sektionen: “iOS: Share Extension Auth (App Groups)”
	•	I Apple Developer Portal:
	•	Skapa App ID för huvudapp.
	•	Skapa App ID för Share Extension.
	•	Skapa ett App Group, t.ex. group.se.dittnamn.receptapp.
	•	I project.yml:
	•	Lägg till App Group entitlement för huvudapp.
	•	Lägg till samma App Group för Share Extension.
	•	Implementera delad auth:
	•	Lagra token i en gemensam container (App Group) så Share Extension kan posta recept som inloggad användare.
	•	Test:
	•	Installera appen på fysisk enhet.
	•	Dela ett recept från Safari → MinaRecept Share Extension.
	•	Verifiera att receptet hamnar på rätt användare i backend (med prod-URL).

⸻

🎨 Steg 4 – UX, lokalisering & polish (miniminivå innan review)

Kopplat till “Lokalisering” och “UI/UX Polering”.
	•	Lokalisering (svenska)
	•	Gå igenom formulär- och valideringsfel i iOS-appen och backend-svar:
	•	Rimlig svensk text (eller neutralt engelska konsekvent).
	•	Kolla datum- och tidsformat i appen: svensk stil där det är användar-facing.
	•	Bekräftelser & felmeddelanden
	•	Bekräftelse vid borttagning av data i appen (ex. recept, inköpslistor).
	•	Tydliga fel vid:
	•	Inloggning misslyckas.
	•	API inte nås (visa “Ingen anslutning” istället för att bara snurra).
	•	Responsivitet & småskärmar
	•	Testa på minst: iPhone SE (liten), iPhone 14/15 (normal).
	•	Navigering & knappar funkar bra även med stor textstorlek.

⸻

🧪 Steg 5 – Testning inför App Store

Mål: Inga dumma överraskningar i review eller för första användare.
	•	Unit- & integrationstester (backend + iOS)
	•	Se till att nuvarande GitHub Actions-workflow (backend + iOS XCTest) körs grönt på:
	•	stage
	•	ev. main/release-branch
	•	Lås in via Branch protection:
	•	Inga merges till stage utan grön CI (matchar din TODO).
	•	End-to-end-flöden (manuellt på device)
	•	På fysisk iPhone:
	•	Skapa konto / logga in.
	•	Skapa recept.
	•	Lägg till i veckomeny.
	•	Skapa inköpslista + toggle items.
	•	Använd Cook Mode i verkligt “köksscenario”.
	•	Prova Share Extension från Safari/Instagram-länk.
	•	TestFlight
	•	Ladda upp en build via Xcode (Archive → Distribute via TestFlight).
	•	Bjud in:
	•	Interna testers (eget Apple-ID).
	•	Några externa (familj/vänner).
	•	Samla feedback på:
	•	Buggar.
	•	Otydlig UI.
	•	Prestanda (känns appen snappy?).

⸻

🍏 Steg 6 – App Store Connect: inställningar & metadata

Mål: Ha allt klart för att trycka på “Submit for Review”.
	•	Apple Developer & App-poster
	•	Apple Developer-konto aktivt.
	•	Skapa App i App Store Connect:
	•	Namn (t.ex. “MinaRecept” – kolla att det är ledigt).
	•	Bundle ID matchar det Xcode använder.
	•	Ikon, kategori (Food & Drink), språk (svenska/engelska).
	•	Metadata i App Store Connect
	•	Kort beskrivning (subtitle) – t.ex. “Veckomenyer & recept på ett ställe”.
	•	Lång beskrivning – fokus på:
	•	Spara recept från webben.
	•	Veckomenyer & inköpslistor.
	•	Cook Mode.
	•	Nyckelord (svenska mat-relaterade ord).
	•	Support-webb/URL.
	•	Privacy Policy URL.
	•	Terms & Conditions URL.
	•	Skärmdumpar
	•	Minst för 6.7” (Pro Max) och 6.1” (Pro/vanlig).
	•	Visa:
	•	Receptlista.
	•	Receptdetalj.
	•	Cook Mode.
	•	Inköpslista.
	•	Import-/Share-flöde (om du vill highlighta det).
	•	Integritetsfrågor (App Privacy)
	•	Fyll i formuläret:
	•	Vilken data samlas in?
	•	Om den är kopplad till identitet?
	•	Om den används för tracking (troligen nej om du inte kör ads eller cross-app analytics).

⸻

🚀 Steg 7 – Skicka in för review
	•	Välj build (från TestFlight) som ska knytas till app-versionen.
	•	Kontrollera:
	•	Version-/build-nummer matchar i Xcode och App Store Connect.
	•	Alla fält är ifyllda.
	•	Klicka Submit for Review.
	•	När godkänd:
	•	Välj om du vill “Release manually” eller “Release automatically” när den godkänns.

⸻
