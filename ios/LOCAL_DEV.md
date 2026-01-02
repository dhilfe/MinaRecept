## Lokal utveckling mot fysisk iPhone (utan prod-backend)

När du kör appen på en **fysisk telefon** kan den inte nå din dator via `127.0.0.1` (det pekar på telefonen själv).

### Snabbfix (rekommenderas för lokalt dev)
- Ta reda på din Macs IP på WiFi (t.ex. `192.168.x.y`)
- Uppdatera i `ios/project.yml` (temporärt, commit:a inte):
  - `INFOPLIST_KEY_API_BASE_URL` under `ReceptAppiOS -> settings -> configs -> Debug`
  - och samma under `ReceptAppShare -> settings -> configs -> Debug`
- Lägg också till din IP i `NSAppTransportSecurity -> NSExceptionDomains` (för Debug) om du kör HTTP.

### Starta Django så den lyssnar på nätverket

```bash
python manage.py runserver 0.0.0.0:8000
```


