
⸻

Programvaruspecifikation – MinaRecept (arbetsnamn)

1. Syfte & vision

MinaRecept ska göra det enkelt att samla, strukturera och använda recept oavsett var användaren hittar dem (sociala medier, webbsidor, kokböcker, egna idéer).

Appen ska:
	•	Minska “varje-dag-vad-ska-vi-äta”-stress.
	•	Göra det enkelt att spara recept från andra plattformar med ett klick.
	•	Hjälpa användaren att snabbt skapa veckomenyer baserat på smak, tid, svårighetsgrad och typ av måltid.

⸻

2. Målgrupp
	•	Privatpersoner som ofta sparar recept från:
	•	Instagram
	•	Facebook
	•	Matbloggar och receptsidor
	•	Pinterest
	•	TikTok / YouTube (matvideos)
	•	Fysiska kokböcker och tidningar (genom foto)
	•	Användare som vill:
	•	Ha en central plats för alla recept.
	•	Snabbt skapa veckomenyer.
	•	Filtrera på enkla/snabba rätter respektive “finare” middagar.

⸻

3. Plattform & utvecklingsfaser

3.1 Fas 1 – MVP (webbapplikation)

Syfte: Validera funktionalitet, flöden och användarupplevelse.
	•	Plattform: Responsiv webbsida (desktop först, fungerar även på mobil/surfplatta).
	•	Inloggning:
	•	Admin sätter upp användarkonton.
	•	Användare loggar in med tilldelat användarnamn + lösenord.
	•	Första steg: enkel, intern användarhantering (ingen självregistrering).

3.2 Fas 2 – Utökad autentisering
	•	Lägg till:
	•	Inloggning med Google-konto.
	•	Inloggning med Apple-ID.
	•	Målsättning: Användaren ska kunna logga in med sitt befintliga konto (Single Sign-On).

3.3 Fas 3 – Mobilappar (iOS & Android)
	•	Native eller cross-platform app (t.ex. Flutter/React Native, beslutas senare).
	•	Publiceras i:
	•	Apple App Store (iOS).
	•	Google Play (Android).
	•	Användare:
	•	Får en länk (olika för iOS & Android) som leder till respektive app-butik.
	•	Loggas in via Google/Apple-ID (ingen extra registrering behövs om möjligt).

⸻

4. Användarflöden (User Journeys)

4.1 Spara recept från sociala medier / webben

Mål: Med ett klick kunna spara ett recept man ser i sitt flöde.

Möjliga lösningar (kan implementeras stegvis):
	1.	Dela-funktion i mobil (Share/Skicka till):
	•	Användaren trycker på “Dela” i t.ex. Instagram/Facebook.
	•	Väljer “Spara till MinaRecept” i delningsmenyn.
	•	Appen tar emot:
	•	Länk till inlägget / sidan.
	•	Eventuell text (caption/beskrivning).
	•	Användaren kan sedan redigera och komplettera receptet i appen.
	2.	Webbläsartillägg (Chrome/Edge/Safari):
	•	Användaren klickar på en knapp i webbläsaren “Spara i MinaRecept”.
	•	Appen:
	•	Hämtar sidans titel, bild och text.
	•	Försöker identifiera ingredienslista och instruktioner.
	3.	Klistra in länk manuellt (basfunktion):
	•	Användaren kopierar en länk.
	•	Öppnar MinaRecept.
	•	Väljer “Nytt recept från länk”.
	•	Appen försöker hämta relevant innehåll automatiskt (titel, bild, text).

(Exakta integrationsnivån med Instagram/Facebook etc. beror på deras API-begränsningar, men detta är målbilden.)

⸻

5. Funktionella krav

5.1 Recept

Användaren ska kunna:
	•	Skapa, läsa, uppdatera och ta bort (CRUD) recept.
	•	Spara följande information:
	•	Titel
	•	Kort beskrivning
	•	Ingredienser (lista)
	•	Tillagningssteg
	•	Tillagningstid / total tid
	•	Svårighetsgrad (t.ex. Enkel / Medel / Avancerad)
	•	Typ av rätt (t.ex. Vardagsmat, Helgmiddag, Fest, Vegetariskt, Efterrätt etc.)
	•	Taggar/kategorier (fritext-taggar)
	•	Bild(er)
    •   Sortera på antal personer recptet ska vara för och uppdatera samtliga ingrediensers mängd därefter

5.2 Automatisk kategorisering

Systemet ska:
	•	Försöka automatiskt kategorisera recept baserat på:
	•	Maträttens namn (t.ex. “Pasta Bolognese” → Pasta / Italienskt).
	•	Innehåll/ingredienser (t.ex. innehåller kyckling → “Kycklingrätter”).
	•	Exempel på kategorier:
	•	Proteinkälla: Kyckling, Nötkött, Fisk, Vegetariskt, Vegan.
	•	Typ av rätt: Huvudrätt, Förrätt, Efterrätt, Tillbehör.
	•	Tillfälle: Vardag, Fredagsmys, Bjudmiddag, Snabbt (<30 min).
	•	Användaren ska kunna:
	•	Justera kategori manuellt.
	•	Lägga till egna taggar.
    •   Lägga till som favoriter

5.3 Veckomeny-funktion

Användaren ska kunna skapa en veckomeny för t.ex. måndag–söndag med ett tryck.

Funktioner:
	1.	Automatisk veckomeny (slump):
	•	Välj “Skapa veckomeny”.
	•	Appen väljer rätter slumpvis från användarens receptbank.
	•	Inställningar:
	•	Antal måltider (t.ex. 5 vardagar eller 7 dagar).
	•	Maximal tillagningstid per dag (t.ex. max 30 min).
	•	Uteslut vissa kategorier (t.ex. inga fiskrätter).
	2.	Slumpa från valda kategorier:
	•	Användaren markerar t.ex. “Vardagsmat” och “Vegetariskt”.
	•	Appen skapar meny endast från dessa kategorier.
	3.	Manuell veckomeny:
	•	Användaren väljer själv recept ur sin lista och placerar dem i kalendern (Mån–Sön).
	4.	Filter för typ av mat:
	•	Knappval t.ex.:
	•	“Laga något enkelt”
	•	“Laga en finare middag”
	•	Systemet filtrerar recept med:
	•	Enkel → kort tillagningstid / låg svårighetsgrad.
	•	Finare middag → markerade som “bjudmat/fest” eller högre svårighetsgrad.

5.4 Manuellt lägga in recept

Användaren ska kunna:
	•	Skapa ett recept från tom mall.
	•	Klistra in text från:
	•	Receptbok (egen tolkning).
	•	Webbsida.
	•	Eget dokument.
	•	Lägga till/inspela bild.

5.5 Foto / OCR från receptbok

Funktionalitet:
	•	Användaren fotar ett recept i en fysisk kokbok/tidning.
	•	Systemet:
	•	Kör textigenkänning (OCR).
	•	Försöker separera:
	•	Titel
	•	Ingredienser
	•	Instruktioner
	•	Skapar ett nytt recept i appen.
	•	Användaren kan:
	•	Redigera texten.
	•	Välja kategori/taggar.
	•	Spara receptet.

⸻

6. Konton, roller & behörigheter

6.1 Användare (slutanvändare)
	•	Har egen receptsamling.
	•	Ser endast sina egna recept.
	•	Kan dela recept (ex. exportera länk/skriv ut/skicka till vän – definieras senare).

6.2 Admin
	•	Skapar användarkonton i första versionen (fas 1).
	•	Kan:
	•	Se lista på användare.
	•	Återställa lösenord.
	•	Aktivera/inaktivera konto.

⸻

7. Autentisering & inloggning

Fas 1
	•	Inloggning med användarnamn + lösenord som tilldelas av admin.
	•	Enkel sida:
	•	Fält: användarnamn, lösenord.
	•	Funktion “Glömt lösenord” kan initialt vara manuell (kontaktar admin).

Fas 2
	•	Stöd för:
	•	Google Sign-In
	•	Apple Sign-In
	•	Möjlighet att:
	•	Knyta befintligt konto till Google/Apple (konto-länkning).
	•	Nyregistrering via Google/Apple (beroende på krav).

⸻

8. Pris- och licensmodell

8.1 Gratisversion (initialt fokus)
	•	Appen är kostnadsfri vid start.
	•	Eventuell begränsning:
	•	Max t.ex. 10 recept per konto.
	•	Alla grundfunktioner, men viss funktionalitet kan reserveras för betalversion på sikt.

8.2 Betalversion (framtid)
	•	Lås upp via:
	•	In-App Purchase (iOS/Android).
	•	Alternativt via webb-betalning (Stripe / Swish etc.) – beslut senare.
	•	Fördelar i betalversion:
	•	Obegränsat antal recept.
	•	Extra funktioner (t.ex. avancerade filter, delade familjekonton, inköpslistor etc.).

⸻

9. Icke-funktionella krav
	•	Prestanda:
	•	Appen ska upplevas snabb även med många recept (hundratals).
	•	Användbarhet:
	•	Enkel, ren design.
	•	Få steg för att spara ett recept.
	•	Säkerhet & integritet:
	•	Lösenord lagras säkert (hashade).
	•	Personuppgifter hanteras enligt GDPR.
	•	Backup & tillförlitlighet:
	•	Databasen ska säkerhetskopieras regelbundet.
	•	Portabilitet:
	•	Samma backend ska kunna användas av både webbapp och mobilappar.

⸻

10. Fasindelning – översikt

Fas 1 – MVP (Webb)
	•	Inloggning (admin-skapade konton).
	•	Skapa/visa/redigera/ta bort recept manuellt.
	•	Enkel kategorisering + grundläggande filtrering.
	•	Enkel veckomeny (manuell + enkel slump).

Fas 2 – Förfining & integrationer
	•	Google/Apple-inloggning.
	•	Smartare automatisk kategorisering.
	•	Bättre veckomenylogik (filter för “enkelt” / “finare middag”).
	•	Foto/OCR från kokbok.

Fas 3 – Mobilappar & delningsintegration
	•	iOS- och Android-app.
	•	“Dela till MinaRecept” från andra appar.
	•	Publicering i App Store/Google Play.
	•	In-App Purchase / uppgradering till betalversion.

På sikt kan veckomenyn även kopplas till inköpslista

⸻
