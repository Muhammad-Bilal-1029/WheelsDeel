# WheelDeal

A car marketplace: people sign up, post car ads with photos, browse and filter listings, mark cars as sold, and report bad ads. Admins moderate through an admin panel.

- **Backend:** Python, FastAPI, SQLAlchemy (SQLite by default, MySQL optional)
- **Frontend:** plain HTML / CSS / JavaScript (no build step), served by the same FastAPI server
- **Everything is behind login.** Visitors only see the login and sign-up pages.

---

## Quick start (Windows)

Run these from the project root (the folder that contains `backend` and `frontend`).

| Step | Command | What it does |
|---|---|---|
| 1 (once) | `setup.bat` | Creates `backend\venv`, installs packages, creates `backend\.env` |
| 2 | `run.bat` | Development server with auto-reload at http://127.0.0.1:8000 |
| 2 (alt) | `run_server.bat` | Server for other devices on the network (`0.0.0.0:8000`, 2 workers) |
| Admin | `make_admin.bat <username>` | Makes an existing user an admin (see below) |

Run `setup.bat` again whenever `backend\requirements.txt` changes (for example after pulling new code).

Open http://127.0.0.1:8000, sign up, then log in.
If email verification is on and SMTP is not configured, the verification link is printed in the **server terminal**. Open that link in the browser.

### Making an admin
A website user can never make themselves admin. On the server machine:

```
make_admin.bat bilal            # make "bilal" admin (the user must already exist)
make_admin.bat bilal --remove   # remove admin rights
make_admin.bat --list           # show all admins
```
Log in again afterwards: an **Admin** link appears in the menu.

---

## Project structure

```
WheelDeal/
├── setup.bat / run.bat / run_server.bat / make_admin.bat   helper scripts (Windows)
├── .gitignore
├── backend/
│   ├── requirements.txt        exact package versions (what we tested with)
│   ├── requirements.lock.txt   every package incl. sub-dependencies
│   ├── .env.example            all settings, documented  ->  copy to .env
│   ├── make_admin.py           command-line tool to create/remove admins
│   ├── wheeldeal.db            SQLite database (created automatically, not in git)
│   ├── uploads/cars/           uploaded photos (created automatically, not in git)
│   └── app/
│       ├── main.py             app setup, login gate (middleware), auth routes, report, analytics
│       ├── cars.py             car list/filter/sort, detail, create, edit, delete, My Ads, photos
│       ├── admin.py            admin API: reports, hide/restore ads, ban/unban users, audit log
│       ├── models.py           database tables
│       ├── schemas.py          request/response shapes + input validation
│       ├── auth_utils.py       passwords, session cookie, CSRF check, current user, admin check
│       ├── images.py           photo checking, resizing, thumbnails
│       ├── ratelimit.py        rate limiting (counted in the database)
│       ├── migrate.py          adds new columns to an existing database automatically
│       ├── mailer.py           verification emails (SMTP) or link printed to the console
│       ├── config.py           reads settings from .env
│       ├── database.py        database engine / session
│       └── utils.py            small shared helpers
└── frontend/
    ├── HTML/                   pages (see the table below)
    ├── css/
    │   ├── style.css           the original theme (large file)
    │   ├── overrides.css       small tweaks: nav size, header search, status colours, contact map
    │   └── ads-features.css    photo cards, filters, sell/edit form, My Ads, detail page, sold style
    └── js/
        ├── app.js              loaded on every page: login check, navigation, API helper, car cards, filters
        ├── auth.js             login and sign-up forms
        ├── sell.js             post / edit an ad (+ photo upload)
        ├── my-ads.js           My Ads page
        ├── car.js              car detail page
        └── admin.js            admin panel
```

> **Naming note:** the folder `frontend/HTML` is served at the URL path `/carhtml/` (for example `frontend/HTML/index.html` is http://127.0.0.1:8000/carhtml/index.html). This is set in `backend/app/main.py`. If you ever rename the folder or URL, update `main.py` (`PUBLIC_EXACT_PATHS`, the redirects and the `app.mount` lines).

### Pages

| Page | Script | Notes |
|---|---|---|
| `login.html`, `signup.html` | `auth.js` | Only pages visible without login |
| `index.html` | `app.js` | Home: header search, filters, sorting, "Load more" |
| `car.html?id=12` | `app.js`, `car.js` | Car detail with photo gallery |
| `sell.html` / `sell.html?id=12` | `app.js`, `sell.js` | Post a new ad / edit your ad |
| `my-ads.html` | `app.js`, `my-ads.js` | Your ads: status, edit, delete |
| `analytics.html` | `app.js` | Counts + current listings (sold cars are not listed) |
| `services.html`, `contact.html` | `app.js` | Static content (contact has a Google Map) |
| `admin.html` | `admin.js` | Admins only |

**Rule:** on every page, `app.js` must be loaded **first**. Page scripts use its helpers (`apiRequest`, `onWheelDealReady`, `createCarCard`, ...).
CSS order: `style.css` → `overrides.css` → `ads-features.css` (later files win).

---

## How things work

- **Login:** a session cookie that JavaScript cannot read (HttpOnly). Logging out ends the session on the server for every device. Changing state (POST/PATCH/DELETE) needs the `X-Requested-With: WheelDeal` header and a same-site `Origin` (CSRF protection).
- **Login gate:** `main.py` middleware sends anyone without a valid session to `login.html`. Pages, photos (`/media/...`) and the car API are all behind it. Only login/sign-up pages, CSS/JS and `/api/*` are public (and `/api/*` has its own checks).
- **Ads:** required fields are brand, model, year, price, city, mileage, fuel, transmission, condition and phone. Engine cc, colour, description and photos are optional. Status is `available`, `pending` or `sold`.
- **Deleting an ad** only marks it deleted (so reports and evidence are kept). Admin can still see it, marked "DELETED BY OWNER".
- **Photos:** up to 8 per ad, JPEG/PNG/WebP, 5 MB each. The server opens every upload as a real image, removes EXIF data, resizes (max 1600 px) and makes a 480 px thumbnail. Files are stored in `backend/uploads/cars/` with random names.
- **Moderation:** users can report an ad (once per ad). Admins can hide/restore ads, ban/unban users and every action is written to an activity log. Banning logs the user out everywhere and hides all their ads.
- **Rate limits** (counted in the database): login attempts, sign-ups, new ads, reports, photo uploads, verification emails.
- **Database changes:** `migrate.py` runs on every start and adds missing columns to an existing database, so old data is kept.

### Main API routes
All under `/api`. Everything except sign-up, login, verify-email, resend-verification and health needs login.

```
POST /signup  /login  /logout        GET /me            GET /health
GET  /cars?q=&city=&fuel_type=&transmission=&condition=&min_price=&max_price=
         &min_year=&max_year=&status=&sort=&limit=&offset=   -> {items, total}
GET  /cars/{id}        POST /cars        PATCH /cars/{id}        DELETE /cars/{id}
PATCH /cars/{id}/status                  GET /my/cars
POST /cars/{id}/images (raw image bytes) DELETE /cars/{id}/images/{image_id}
POST /cars/{id}/images/{image_id}/cover  POST /cars/{id}/report
GET  /analytics
/admin/*  (admins only): stats, reports, cars, users, ban/unban, hide/restore, log
```
Interactive docs: http://127.0.0.1:8000/docs

---

## Settings (`backend/.env`)

Copy `backend/.env.example` to `backend/.env`. Every setting is explained there. The important ones:

| Setting | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | empty = SQLite file | Put a `mysql+pymysql://...` URL to use MySQL |
| `WHEELDEAL_SECRET_KEY` | auto-generated into `backend/.secret_key` | At least 32 characters. Changing it logs everyone out |
| `TOKEN_EXPIRE_HOURS` | 24 | Session length (max 168) |
| `REQUIRE_EMAIL_VERIFICATION` | true | Users must verify email before logging in |
| `SMTP_*`, `PUBLIC_BASE_URL` | empty | Needed to send real emails (production) |
| `CORS_ORIGINS` | `*` | Set your real domain(s) when deploying |
| `MAX_IMAGE_MB`, `MAX_IMAGES_PER_AD` | 5, 8 | Photo limits |
| `MAX_ADS_PER_HOUR/DAY/USER` | 5, 15, 100 | Anti-spam limits |

**Never commit** `backend/.env`, `backend/.secret_key`, `backend/wheeldeal.db` or `backend/uploads/` (they are in `.gitignore`).

---

## Where do I change...?

| I want to change | Edit |
|---|---|
| Nav links / menu | `frontend/js/app.js` → `buildNavigation` |
| What a car card shows | `frontend/js/app.js` → `createCarCard` |
| Filter options on Home | `frontend/HTML/index.html` (form) + `FILTER_FIELDS` in `app.js` + filters in `backend/app/cars.py` → `list_cars` |
| Fields of an ad | `models.py` (column) + `migrate.py` (old databases) + `schemas.py` (validation) + `cars.py` (`serialize`) + `sell.html`/`sell.js` + `car.js` |
| Photo size / count | `.env` (`MAX_IMAGE_MB`, `MAX_IMAGES_PER_AD`); sizes in `images.py` |
| Colours of Available/Pending/Sold | `frontend/css/overrides.css` (`--status-*`), sold card look in `ads-features.css` |
| Heading / nav font sizes | `frontend/css/overrides.css` (variables at the top) |
| Rate limits | `backend/app/config.py` |
| Login message | `backend/app/main.py` → `login` |

---

## Troubleshooting

- **"Pillow"/"No module named PIL" at start:** run `setup.bat` again.
- **Everyone got logged out after an update:** expected after security changes; log in again.
- **Old CSS/JS after an update:** hard refresh with Ctrl+F5.
- **PowerShell blocks `activate`:** use the `.bat` files, or `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.
- **Photos not visible:** you must be logged in; check `backend/uploads/cars/` has the files.
- **Server refuses to start with "secret key too short":** remove `WHEELDEAL_SECRET_KEY` from `.env` (a strong one is generated) or use 32+ characters.

---

## Known gaps / ideas

- No automated tests are committed yet.
- No password reset ("forgot password") and no change-password page.
- HTTPS is not built in: put the app behind nginx or Caddy when deploying, then set `COOKIE_SECURE=true`.
- No notification to the seller/admin when a report arrives.
- Possible clean-up later: merge the three CSS files into one, and move the auth routes out of `main.py` into their own file.
