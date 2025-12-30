# FR-20251227-01: Apple Sign-In med automatisk kontoskapande

## Bakgrund
För att förenkla onboarding och slippa manuell registrering ska användare kunna logga in (och skapa konto) direkt via Apple-login, både i iOS-app och på webben. Ingen separat registreringssida behövs.

## Mål
- Användaren kan logga in med Apple på webben och i appen.
- Om kontot inte finns skapas det automatiskt (med e-post från Apple).
- Ingen manuell registrering/extrainmatning krävs.
- Backend och iOS-app stödjer hela flödet.

## Krav
- [ ] Apple Sign-In aktiverat i backend (django-allauth, provider, credentials, redirect-URL).
- [ ] Apple Sign-In integrerat i iOS-appen (Sign in with Apple UI, token till backend).
- [ ] Backend skapar användare automatiskt vid första Apple-login.
- [ ] Testfall: ny användare, befintlig användare, edge-cases (dold e-post, bytt Apple-ID).
- [ ] Dokumentation och kodkommentarer.

## Acceptanskriterier
- [ ] Det går att logga in/skapa konto med Apple på både webben och i appen.
- [ ] Ingen separat registrering behövs.
- [ ] All kod är spårbar till denna FR och PR.

## Noteringar
- Se även TODO.md under "Social Inloggning".
- Google-login kan hanteras i separat FR.
