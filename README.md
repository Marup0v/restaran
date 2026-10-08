# Restoran buyurtma tizimi

Bu loyiha restoran menyusi, serverdagi savat, buyurtma, oshxona navbati va Telegram botni o'z ichiga oladi.

## Ishga tushirish

```bash
cd /home/ubuntu/Desktop/restaran
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Brauzerda `http://127.0.0.1:8000/api/menu/` manzilini oching. API JWT ishlatadi.

## API asosiy manzillari

- `POST /api/auth/telegram/` - mijoz uchun token olish
- `GET /api/menu/` - faol menyu
- `GET /api/cart/` - serverdagi savat
- `POST /api/cart/items/` - savatga taom qo'shish
- `POST /api/orders/` - savatdan buyurtma yaratish
- `GET /api/kitchen/queue/` - oshxona navbati
- `POST /api/orders/<id>/cancel/` - yangi buyurtmani bekor qilish

## Telegram bot

`.env` ichiga `TELEGRAM_BOT_TOKEN` yozing va ishga tushiring:

```bash
./.venv/bin/python manage.py runbot
```

Bot menyuni ko'rsatadi, taomni serverdagi savatga qo'shadi va buyurtma yaratadi.

## PostgreSQL

PostgreSQL ishlatilsa `.env` ichida `DB_ENGINE=postgresql` qilib, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` va `DB_PORT` qiymatlarini yozing. Tayyor lokal baza uchun:

```bash
docker compose up -d db
```

Keyin `.env` ichida `DB_ENGINE=postgresql` qiling va:

```bash
./.venv/bin/python manage.py migrate
```
# restaran
# restaran
# restaran
