# Apple Sign-In – Backendkonfiguration

Denna dokumentation gäller FR-20251227-01 (Apple-login).

## Credentials (Apple Developer Portal)
1. Skapa en ny Service ID (eller använd befintlig) för din app på https://developer.apple.com/account/resources/identifiers/list/serviceId
2. Skapa och ladda ner en ny private key (p8) under Certificates, Identifiers & Profiles > Keys.
3. Notera följande värden:
   - **Client ID** (Service ID, t.ex. se.receptapp.ios)
   - **Team ID** (från Apple Developer)
   - **Key ID** (för din p8-nyckel)
   - **Private Key** (innehållet i .p8-filen)

## Miljövariabler
Lägg in dessa i din miljö (t.ex. .env, server, GitHub Secrets):

```
APPLE_CLIENT_ID=se.receptapp.ios
APPLE_TEAM_ID=XXXXXXXXXX
APPLE_KEY=YYYYYYYYYY
APPLE_SECRET="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
```

## Django settings.py
Apple-credentials hämtas automatiskt från miljövariabler:

```
SOCIALACCOUNT_PROVIDERS = {
    'apple': {
        'APP': {
            'client_id': os.getenv('APPLE_CLIENT_ID', ''),
            'team_id': os.getenv('APPLE_TEAM_ID', ''),
            'key': os.getenv('APPLE_KEY', ''),
            'secret': os.getenv('APPLE_SECRET', ''),
        },
    },
}
```

## Redirect URL
Lägg till denna i Apple Developer Portal:

```
https://<din-domän>/accounts/apple/login/callback/
```

## Testa
- Gå till /accounts/login/ och testa "Sign in with Apple".
- Vid första login skapas konto automatiskt.

Se även FR-20251227-01_apple_login.md för acceptanskriterier.
