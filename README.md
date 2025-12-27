# ReceptApp (Spara_Recept)

ReceptApp är en Django-webbapp + en iOS-app (SwiftUI) för att spara recept, planera veckomeny och skapa inköpslistor.

## Innehåll

- `receptapp_project/`, `recipes/`: Django-projekt + app
- `ios/`: iOS-app (XcodeGen-projekt) + Share Extension
- `docs/`: specifikation, API-kontrakt och feature requests
- `scripts/test_all.sh`: kör hela testsviten (backend + E2E + iOS build/test)

## Kom igång (Backend)

Krav: Python 3, macOS/Linux (Windows funkar ofta men är inte primärt), samt en virtuell miljö.

```bash
cd ReceptApp
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python manage.py migrate
./venv/bin/python manage.py createsuperuser
./venv/bin/python manage.py runserver
```

Öppna sedan:
- Webb: `http://127.0.0.1:8000/`
- API: `http://127.0.0.1:8000/api/`

## Tester

Kör allt (unit + e2e + iOS build/test på macOS):

```bash
./scripts/test_all.sh
```

Notera: iOS-steget försöker köra XCTest om schemat är konfigurerat för test; annars faller det tillbaka till `xcodebuild build` för att åtminstone verifiera att appen bygger.

## Kom igång (iOS)

Krav: macOS + Xcode + `xcodegen`.

```bash
cd ios
xcodegen generate
xcodebuild -project ReceptAppiOS.xcodeproj -scheme ReceptAppiOS -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build
```

Du kan även öppna projektet via Xcode:
- `ios/ReceptAppiOS.xcodeproj`

### Share Extension

Det finns en iOS Share Extension som kan spara recept via backend-API. För att köra den i praktiken behövs ofta App Groups/Keychain-delning (se TODO/FR i `docs/`).

## Dokumentation

- Spec: `docs/specification.md`
- API-kontrakt: `docs/API.md`
- Backlog: `docs/TODO.md`

## Vanliga kommandon

- Skapa migrationer: `./venv/bin/python manage.py makemigrations`
- Migrera: `./venv/bin/python manage.py migrate`
- Kör server: `./venv/bin/python manage.py runserver`
- Kör backend-tester: `./venv/bin/python manage.py test`
