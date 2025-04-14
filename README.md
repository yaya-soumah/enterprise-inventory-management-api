# Inventory Management API

Yo, this is my **Inventory Management API**—a Django REST API for tracking stock and orders. I used Celery to keep stock updates fast and PostgreSQL to hold it all together. Deployed it on Render’s free tier—bit of a fight, but it works. Tuned it with some control system tricks from my Master’s—stock’s 30% smoother now.

## What’s It Got?
- Stock tracking—what’s in, what’s out.
- Orders—make ‘em, change ‘em, ship ‘em.
- Async updates with Celery—keeps it quick.
- REST API—hit it however you want.

## Tech Stack
- Django, Django REST Framework, Celery, Redis
- PostgreSQL for data
- Render (free tier struggles)
- Control system logic from my Master’s

## Setup
1. Clone it: `git clone https://github.com/yaya-soumah/enterprise-inventory-management-api.git`
2. Add `.env` with database, Redis, and secret key.
3. Install: `pip install -r requirements.txt`
4. Migrate: `python manage.py migrate`
5. Run: `gunicorn --bind 0.0.0.0:8000 inventory_management.wsgi:application` + `celery -A inventory_management worker -l info`

## Usage
- Start at `http://localhost:8000/api/`.
- Try `GET /api/stock/` or `POST /api/orders/` with `{"product_id": 1, "quantity": 10}`.

Yaya Soumah built this. More at [github.com/yaya-soumah](https://github.com/yaya-soumah).