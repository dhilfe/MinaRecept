# FR-20251226-01: OCR-tolkning av receptbilder

## Bakgrund
Användare vill kunna fotografera ett recept (t.ex. från en kokbok eller tidning) och automatiskt få in det i appen som ett strukturerat recept (Titel, Ingredienser, Instruktioner).

## Mål
1.  Kunna ladda upp en bild (eller ta foto med mobilen) i webbgränssnittet.
2.  Systemet analyserar bilden och extraherar text.
3.  Systemet strukturerar texten till ett recept-utkast.
4.  Användaren får granska och redigera utkastet innan det sparas.

## Tekniska Vägval

### 1. Frontend
-   Ny knapp/sida: "Importera från bild".
-   Standard HTML `<input type="file" accept="image/*" capture="environment">` fungerar bra för mobila enheter.
-   Förhandsvisning av bilden.

### 2. Backend (Django)
-   Ny vy för att ta emot bilduppladdning.
-   Tillfällig lagring av bilden (eller direkt bearbetning i minnet).

### 3. Bildanalys & Text-extraktion (OCR)
Detta är den svåra biten. Att bara få ut "råtext" är enkelt med Tesseract, men att förstå vad som är ingredienser vs instruktioner är svårt pga layout (spalter, faktarutor etc).

**Alternativ:**
*   **Alternativ A: LLM med Vision (t.ex. OpenAI GPT-4o / Claude 3.5 Sonnet)**
    *   **Fördelar:** Överlägset bäst på att förstå layout och struktur. Kan returnera färdig JSON.
    *   **Nackdelar:** Kostar pengar per anrop. Kräver API-nyckel.
*   **Alternativ B: Cloud Vision API (Google/Azure/AWS)**
    *   **Fördelar:** Bra OCR.
    *   **Nackdelar:** Kostar också (ofta free tier). Ger bara text + koordinater, kräver komplex logik för att gruppera texten rätt.
*   **Alternativ C: Lokal OCR (Tesseract)**
    *   **Fördelar:** Gratis, körs lokalt.
    *   **Nackdelar:** Sämre kvalitet på svenska tecken ibland. Ingen layout-analys (returnerar ofta text rad för rad rakt över spalter). Kräver installation av binärer på servern.

**Rekommendation:**
För "ett bra sätt" (hög kvalitet) är **Alternativ A (LLM)** bäst idag. Vi kan bygga ett interface så att vi enkelt kan byta backend.

## Genomförandeplan
1.  [ ] Skapa UI för bilduppladdning (`recipes/templates/recipes/recipe_import_image.html`).
2.  [ ] Skapa Django-vy och URL för uppladdning.
3.  [ ] Skapa en `ImageRecipeParser`-service.
4.  [ ] Implementera en första version av parsern.
    *   *Fråga användaren:* Har vi tillgång till OpenAI API-nyckel?
    *   Om inte, kan vi testa med en enkel Tesseract-lösning (om `tesseract` finns installerat) eller bara en "mock" som visar hur flödet fungerar.
5.  [ ] Fyll i `RecipeForm` med extraherad data (samma flöde som URL-import).

## Datamodell
Inga nya modeller krävs nödvändigtvis, vi använder sessionen för att mellanlagra data innan `RecipeCreateView` (precis som för URL-import).
