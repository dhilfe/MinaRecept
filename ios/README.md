# iOS-klient (SwiftUI) – MVP

Den här mappen innehåller en minimal iOS-app som pratar med ReceptApps API.

## Förutsättningar
- Xcode (valfri modern version)
- XcodeGen (för att generera `.xcodeproj`)

Installera XcodeGen (macOS):
- `brew install xcodegen`

## Generera projekt
Kör:
- `cd ios`
- `xcodegen generate`

Öppna sedan `ReceptAppiOS.xcodeproj` i Xcode.

## Konfiguration
Appen läser `API_BASE_URL` från Info.plist (via XcodeGen). Default är:
- `http://127.0.0.1:8000/api/`

Obs: För fysisk iPhone behöver du byta till datorns LAN-IP.

## Körning
1) Starta backend:
- `python manage.py runserver`

2) Kör appen i Simulator
3) Logga in med ditt vanliga konto
