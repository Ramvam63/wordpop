<p align="center">
  <img src="frontend/icons/icon-192.png" width="96" alt="WordPop icon" />
</p>

<h1 align="center">WordPop</h1>

<p align="center">
  <b>Save new English words and get them as reminders on your phone until you know them.</b>
</p>

<p align="center">
  <a href="https://wordpopapp.onrender.com"><img src="docs/open-wordpop.png" width="420" alt="Open WordPop – wordpopapp.onrender.com" /></a>
</p>

<p align="center">
  <a href="https://github.com/Ramvam63/wordpop/actions/workflows/ci.yml"><img src="https://github.com/Ramvam63/wordpop/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/FastAPI-backend-009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PostgreSQL-Neon-336791" alt="PostgreSQL on Neon" />
  <img src="https://img.shields.io/badge/PWA-installable-F7B901" alt="PWA" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license" />
</p>

---

## Try it – free, no download from an app store

<table>
<tr>
<td width="62%">

**On iPhone** (Safari)
1. Open **[wordpopapp.onrender.com](https://wordpopapp.onrender.com)** in **Safari**
2. Tap **Share ⬆ → Add to Home Screen → Add**
3. Open **WordPop** from your Home Screen and create an account
4. Go to **Settings → Turn on notifications**

**On Android** (Chrome): open the link and tap **Install**.

**On a computer**: just open the link in any browser.

</td>
<td align="center">

<img src="docs/qr-wordpop.png" width="200" alt="QR code for wordpopapp.onrender.com" /><br/>
<sub>Scan with your phone camera</sub>

</td>
</tr>
</table>

## Screenshots

| Words | Quiz | Progress | Settings |
|---|---|---|---|
| ![Words](docs/screenshots/words.png) | ![Quiz](docs/screenshots/quiz.png) | ![Progress](docs/screenshots/progress.png) | ![Settings](docs/screenshots/settings.png) |

| Categories | iPhone install guide | Sign up |
|---|---|---|
| ![Categories](docs/screenshots/categories.png) | ![Install guide](docs/screenshots/install-guide.png) | ![Sign up](docs/screenshots/signup.png) |

## Features

- **Reminders on your phone** – each notification shows only the word, so you try to recall the meaning; tap it to check
- **Auto-filled words** – type a word or phrase, get its meaning, an example, pronunciation and audio
- **Categories** – a word can belong to several; switch reminders on or off per category
- **Your own schedule** – how often, active hours, active days, daily limit, pause for 3 hours / a day / a week, and your own time zone
- **Spaced-repetition quiz** – words you forget come back sooner; words you know are spaced out
- **Progress page** – streak, mastered words, accuracy, 7-day activity and hardest words
- **Starter lists** – Vocabulary, Phrasal Verbs, Idioms and Casual English for a useful first day
- **Installable app (PWA)** – Home Screen icon, opens instantly from cache, step-by-step iPhone install guide
- **Accounts & security** – bcrypt-hashed passwords, HTTP-only session cookies, **forgot-password emails** with one-time links (stored hashed, rate-limited), reset signs out other devices
- **Privacy** – delete your account and all data in one tap
- **Admin analytics** – sign-ups, weekly active users and day-1/7/28 retention

## Tech stack

| Area | Technology | Why |
|---|---|---|
| Backend | **Python 3.12, FastAPI**, SQLAlchemy 2, Pydantic | Fast, typed REST API with automatic docs at `/docs` |
| Database | **PostgreSQL on [Neon](https://neon.com)** (serverless, free tier); SQLite for tests | Real relational database with a many-to-many words ↔ categories model |
| Frontend | **Progressive Web App** – vanilla JavaScript, service worker, Web App Manifest | Installs on iPhone/Android without an app store; no build step |
| Notifications | **Web Push** with VAPID keys (`pywebpush`) | Native-looking reminders on iPhone (iOS 16.4+), Android and desktop |
| Hosting | **[Render](https://render.com)** (Docker web service) | Deploys automatically on every `git push` to `main` |
| Scheduling & uptime | **[UptimeRobot](https://uptimerobot.com)** calls a secret task URL every 5 minutes | Sends due reminders on time and keeps the free server awake |
| Email | **SMTP** (Gmail App Password) | Password-reset emails |
| Word data | **Free Dictionary API** + **Wiktionary** fallback | Definitions, examples, phonetics and audio; Wiktionary covers phrases and idioms |
| Quality | **pytest** (37 tests), **ruff**, **GitHub Actions CI** | Every push is linted and tested automatically |
| Packaging | **Docker**, docker compose | Same container locally and in production |

## Architecture

```mermaid
flowchart LR
    U["📱 User's phone<br/>PWA + service worker"] -- HTTPS / JSON --> API["FastAPI app<br/>on Render"]
    API -- SQLAlchemy --> DB[("PostgreSQL<br/>Neon")]
    API -- look up word --> DICT["Dictionary API<br/>+ Wiktionary"]
    API -- reset emails --> MAIL["Gmail SMTP"]
    UR["⏱ UptimeRobot<br/>every 5 min"] -- secret task URL --> API
    API -- runs --> SCH["Scheduler<br/>who is due?"]
    SCH --> DB
    SCH -- Web Push --> PUSH["Apple / Google<br/>push service"]
    PUSH -- notification --> U
    GH["GitHub"] -- push to main --> API
    GH -- CI: lint + tests --> GH
```

**How a reminder is chosen.** Every 5 minutes UptimeRobot calls `/api/tasks/send-notifications?key=…`.
For each user with notifications on, the scheduler checks: paused? one of their active days and hours
*in their own time zone*? enough time since the last reminder, and under the daily limit? If so it picks
the most overdue word from a category with reminders switched on and sends it to all of the user's
devices. Expired push subscriptions are cleaned up automatically, and one failing device never stops
the run for everyone else.

### Database

```mermaid
erDiagram
    users ||--o{ words : owns
    users ||--o{ categories : owns
    users ||--o{ push_subscriptions : has
    users ||--o{ review_events : answers
    users ||--o{ password_reset_tokens : requests
    words }o--o{ categories : "word_categories"
    words ||--o{ review_events : "reviewed in"
```

## Run it locally

You need Python 3.12+.

```bash
git clone https://github.com/Ramvam63/wordpop.git
cd wordpop
cp .env.example .env                    # then edit the values
python scripts/generate_vapid_keys.py   # paste the two lines into .env
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload           # open http://localhost:8000
```

Leave `DATABASE_URL` empty to use a local SQLite file. Without SMTP settings, password-reset links are
printed in the terminal instead of emailed.

**With Docker** (includes a PostgreSQL container):

```bash
docker compose up --build
```

**Tests and lint:**

```bash
cd backend
pytest -q
ruff check .
```

## Deploy (all free tiers)

1. **Database** – create a project on [Neon](https://neon.com) and copy its connection string.
2. **Web app** – create a Docker **Web Service** on [Render](https://render.com) from this repository and add
   the variables from `.env.example` (use your real `https://` address as `APP_URL`, a long random
   `SECRET_KEY` and a random `CRON_SECRET`).
3. **Reminders** – create an HTTP(s) monitor on [UptimeRobot](https://uptimerobot.com) for
   `https://YOUR-APP.onrender.com/api/tasks/send-notifications?key=YOUR_CRON_SECRET` with a 5-minute interval.
4. **Email** (optional) – add a Gmail App Password as `SMTP_PASSWORD` to enable "Forgot password?" emails.

> The *Send notifications* GitHub Actions workflow is an optional backup scheduler; it is disabled when
> UptimeRobot is used, so reminders are never sent twice.

## API

Interactive documentation: **[wordpopapp.onrender.com/docs](https://wordpopapp.onrender.com/docs)**

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/signup` · `login` · `logout` · `forgot-password` · `reset-password` · `GET/DELETE /api/auth/me` |
| Words | `GET/POST /api/words` · `PATCH/DELETE /api/words/{id}` · `GET /api/dictionary/{word}` |
| Categories | `GET/POST /api/categories` · `PATCH/DELETE /api/categories/{id}` |
| Quiz | `GET /api/quiz/next` · `POST /api/quiz/answer` |
| Settings & progress | `GET/PUT /api/me/settings` · `POST /api/me/pause` · `GET /api/me/progress` |
| Push | `GET /api/push/public-key` · `POST /api/push/subscribe` · `unsubscribe` · `test` |
| Starter lists | `GET /api/starter-lists` · `POST /api/starter-lists/{key}/import` |
| Tasks | `GET /api/tasks/send-notifications?key=…` (called by UptimeRobot) |
| Admin | `GET /api/admin/stats` |

## Project structure

```
wordpop/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app: serves the API and the PWA
│   │   ├── models.py          # database tables
│   │   ├── routers/           # API endpoints by area (auth, words, quiz, tasks, …)
│   │   ├── scheduler.py       # decides who gets a reminder and sends it
│   │   ├── notifications.py   # schedule rules + Web Push delivery
│   │   ├── srs.py             # spaced repetition (Leitner boxes)
│   │   ├── dictionary.py      # Dictionary API + Wiktionary look-ups
│   │   ├── mailer.py          # password-reset emails
│   │   └── data/starter_lists.json
│   └── tests/                 # 37 pytest tests
├── frontend/                  # the PWA: index.html, app.js, sw.js, styles.css, icons
├── scripts/                   # VAPID keys, icons, QR code, GitHub issues
├── docs/                      # screenshots, QR code, roadmap
├── .github/workflows/         # CI (lint + tests) and backup scheduler
├── Dockerfile
└── docker-compose.yml
```

## Roadmap

- [x] v1 – personal script: SQLite + ntfy notifications
- [x] v2 – multi-user PWA: accounts, categories, schedules, quiz, progress, web push
- [x] Forgot password by email
- [x] Amber design, reliable 5-minute reminders, instant start
- [ ] Sign in with Google / magic-link email
- [ ] Translations into the learner's own language
- [ ] Database migrations with Alembic
- [ ] Import / export words as CSV
- [ ] Native iOS app (Swift) using the same API

See [docs/ROADMAP.md](docs/ROADMAP.md) for details.

## Privacy

WordPop stores only what it needs: email, hashed password, your words and settings, quiz answers and
push addresses. No ads, no selling of data. See the [privacy page](https://wordpopapp.onrender.com/privacy.html).

## License

[MIT](LICENSE) © 2026 Hamed Ghorbanian
