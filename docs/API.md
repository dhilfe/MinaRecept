# ReceptApp API (för iOS-klient)

Bas-URL:
- Dev: `http://127.0.0.1:8000/api/`

Auth:
- Alla endpoints kräver inloggning via Token Auth.
- Klienten skickar: `Authorization: Token <token>`

## 1) Hämta token (login)

`POST /api/auth/token/`

Request (JSON):
```json
{
  "username": "din_användare",
  "password": "ditt_lösenord"
}
```

Response 200:
```json
{
  "token": "0123456789abcdef..."
}
```

Fel:
- 400 vid felaktiga credentials.

## 2) Recept

### Lista recept
`GET /api/recipes/`

Response 200 (array):
```json
[
  {
    "id": 1,
    "user": 1,
    "title": "Pasta",
    "description": "...",
    "ingredients": "[{\"amount\":\"1\",\"unit\":\"st\",\"name\":\"Tomat\"}]",
    "steps": "Steg 1\nSteg 2",
    "cooking_time": 20,
    "difficulty": "easy",
    "dish_type": "everyday",
    "tags": "",
    "servings": 4,
    "image": "/media/recipes/fil.jpg",
    "image_url": "http://127.0.0.1:8000/media/recipes/fil.jpg",
    "is_favorite": false,
    "created_at": "2025-12-24T10:00:00Z",
    "updated_at": "2025-12-24T10:00:00Z"
  }
]
```

Notera:
- `ingredients` är lagrat som en textsträng (JSON) i nuläget.
- `image_url` är absolut URL (kan vara `null` om ingen bild finns).

### Hämta recept
`GET /api/recipes/{id}/`

### Skapa recept
`POST /api/recipes/`

Request (JSON, exempel):
```json
{
  "title": "Pasta",
  "description": "Snabb vardagsmat",
  "ingredients": "[{\"amount\":\"1\",\"unit\":\"st\",\"name\":\"Tomat\"}]",
  "steps": "Steg 1\nSteg 2",
  "cooking_time": 20,
  "difficulty": "easy",
  "dish_type": "everyday",
  "tags": "",
  "servings": 4,
  "is_favorite": false
}
```

### Uppdatera recept
- `PATCH /api/recipes/{id}/`
- `PUT /api/recipes/{id}/`

## 3) Inköpslistor

### Lista inköpslistor
`GET /api/shopping-lists/`

### Skapa inköpslista
`POST /api/shopping-lists/`

Request (JSON):
```json
{
  "name": "Veckohandling",
  "is_recurring": false
}
```

### Hämta inköpslista
`GET /api/shopping-lists/{id}/`

## 4) Inköpsrader (items)

### Lista items
`GET /api/shopping-list-items/`

Filtrera per lista:
- `GET /api/shopping-list-items/?shopping_list={shopping_list_id}`

### Skapa item
`POST /api/shopping-list-items/`

Request (JSON):
```json
{
  "shopping_list": 1,
  "recipe": null,
  "name": "Tomat",
  "amount": "2",
  "unit": "st",
  "checked": false
}
```

Notera:
- `shopping_list` måste tillhöra den inloggade användaren.
- Om `recipe` anges måste receptet också tillhöra användaren.

### Uppdatera item
- `PATCH /api/shopping-list-items/{id}/`

### Ta bort item
- `DELETE /api/shopping-list-items/{id}/`

## 5) Veckoplan

### Lista veckoplanrader
`GET /api/weekly-plan/`

Response 200 (array):
```json
[
  {
    "id": 10,
    "user": 1,
    "day": "mon",
    "recipe": 1,
    "recipe_title": "Pasta"
  }
]
```

### Skapa veckoplanrad
`POST /api/weekly-plan/`

Request (JSON):
```json
{
  "day": "mon",
  "recipe": 1
}
```

Notera:
- `recipe` måste tillhöra användaren.
- Modellen har en unik constraint per (`user`, `day`, `recipe`).

## 6) Sparade veckomenyer

### Lista menyer
`GET /api/weekly-menus/`

Response inkluderar `items` (read-only).

### Skapa meny
`POST /api/weekly-menus/`

Request (JSON):
```json
{
  "name": "Vecka 1",
  "week_number": 1,
  "year": 2026
}
```

## 7) Menyrader (WeeklyMenuItem)

### Lista menyrader
`GET /api/weekly-menu-items/`

Filtrera per meny:
- `GET /api/weekly-menu-items/?menu={menu_id}`

### Skapa menyrad
`POST /api/weekly-menu-items/`

Request (JSON):
```json
{
  "menu": 1,
  "day": "tue",
  "recipe": 2
}
```

Notera:
- `menu` måste tillhöra användaren.
- `recipe` måste tillhöra användaren.
- Modellen har en unik constraint per (`menu`, `day`).

## CORS (dev)

I DEBUG-läge är CORS tillåtet för alla origins för att förenkla utveckling av iOS-klient. I produktion bör `CORS_ALLOW_ALL_ORIGINS` ersättas med en allowlist.

## Drift/migrering

Token Auth kräver att `rest_framework.authtoken` är migrerad (kör `python manage.py migrate`).
