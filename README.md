# BEAUTYSUPPLYMSK Channel Bot

A Telegram bot that lets the admins of the **BEAUTYSUPPLYMSK** beauty-supply store manage their Telegram channel entirely from a private chat with the bot — no technical skills required.

## What the bot does

- **Compose posts** step by step: text → up to 10 photos → inline URL buttons → live preview.
- **Publish instantly** or **schedule** for later (`25.12.2026 18:30`, `18:30`, `+2h`, …). Scheduled posts are stored in the database, so they **survive bot restarts** — anything that came due while the bot was down is published right after startup.
- **Edit published posts** (text/caption and buttons) directly in the channel, including multi-photo albums.
- **Delete published posts** from the channel, including every message of an album.
- **Templates** with `{placeholders}` — 7 ready-made store templates (new arrival, sale, restock, deal of the day, customer review, opening hours, how to order) are seeded on first start; admins can add, update, and delete their own.
- **Admin-only**: every content-management action is restricted to the Telegram user IDs listed in `ADMIN_IDS`. Everyone else gets a polite read-only reply.

## How it's built

| Piece | Choice |
|---|---|
| Language | Python 3.12 |
| Bot framework | [aiogram 3](https://docs.aiogram.dev/) (async, FSM-based wizards) |
| Database | PostgreSQL via SQLAlchemy 2 + asyncpg (SQLite fallback for local dev) |
| Scheduler | DB-backed poller — schedule state lives in the `posts` table, restart-safe by design |
| Updates | Long polling by default; optional webhook mode (`RUN_MODE=webhook`) |
| Deploy | Docker on [Railway](https://railway.app) |

```
bot/
  main.py            # entrypoint: wiring, polling/webhook runners
  config.py          # env-var configuration
  core/              # pure logic (unit-tested): templates, states, buttons, time parsing
  db/                # SQLAlchemy models, repository, seed templates
  services/          # channel publisher, persistent scheduler
  handlers/          # aiogram routers: composing, managing, templates, access control
tests/               # pytest suite for the core logic
```

---

## 1. Create the bot with @BotFather

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, choose a display name (e.g. *BEAUTYSUPPLYMSK Admin*) and a username ending in `bot`.
3. BotFather replies with a **token** like `1234567890:AAE...` — this is your `BOT_TOKEN`. Keep it secret.

## 2. Get the channel ID and add the bot as channel admin

1. In your channel: **⋮ → Manage channel → Administrators → Add Admin**, find your bot by username and grant it at least **Post messages**, **Edit messages of others**, and **Delete messages of others**.
2. To get `CHANNEL_ID`:
   - If the channel is public you can simply use `@your_channel_username`.
   - For a private channel (or to be safe), **forward any post from the channel to your bot** once it's running — the bot replies with the numeric ID (looks like `-1001234567890`).
3. To get your `ADMIN_IDS`: send `/id` to the bot (works for everyone) — it replies with your numeric user ID. List every store admin's ID, comma-separated.

## 3. Run locally

```bash
git clone https://github.com/BEAUTYSUPPLYMSK/beauty-landing-2026.git
cd beauty-landing-2026
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # fill in BOT_TOKEN, CHANNEL_ID, ADMIN_IDS
export $(grep -v '^#' .env | xargs)

python -m bot.main
```

With `DATABASE_URL` left empty, the bot uses a local `bot.db` SQLite file — perfect for testing. Message your bot, send `/start`, and you should see the admin menu.

Run the tests and linter:

```bash
pip install -r requirements-dev.txt
pytest
ruff check bot tests
```

---

## 4. Deploy to Railway

You need: a [Railway](https://railway.app) account (GitHub login works), this repository in your GitHub account, and the `BOT_TOKEN` from step 1.

1. **Create the project.** In the Railway dashboard click **New Project → Deploy from GitHub repo**, authorize Railway to access GitHub if asked, and pick `BEAUTYSUPPLYMSK/beauty-landing-2026`. Railway detects the `Dockerfile` and uses it as the build source (also declared in `railway.json`).
2. **Add PostgreSQL.** In the project canvas click **+ New → Database → Add PostgreSQL**. A `Postgres` service appears alongside your bot service.
3. **Set the environment variables.** Railway does **not** read `.env.example` from the repo — variables must be added manually. The fastest way is to import the ready-made list:

   - Open the **bot service → Variables** tab → **Import Variables**.
   - Paste the entire contents of [`railway-vars.env`](railway-vars.env) from this repo. All variable names appear at once with empty (or default) values.
   - Now just fill in the values:

   | Variable | Value |
   |---|---|
   | `BOT_TOKEN` | the token from @BotFather |
   | `CHANNEL_ID` | `-100…` numeric ID or `@channelname` |
   | `ADMIN_IDS` | e.g. `111111111,222222222` |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` — if it was imported as a literal string, open the value and pick **Variable Reference → Postgres.DATABASE_URL** |
   | `TIMEZONE` | `Europe/Moscow` (already prefilled) |
   | `RUN_MODE` | `polling` (already prefilled) |

   You can also add the variables one-by-one instead of importing. Do **not** set `WEBHOOK_URL` — it is only used in webhook mode (see below). Do **not** configure an HTTP health-check path in Settings: in polling mode the worker exposes no port, and a health check would keep the deploy from ever going "healthy".
4. **Deploy.** Railway builds and deploys automatically after you save the variables (or click **Deploy** if prompted). Wait for the build to finish.
5. **Check the logs.** Open the bot service → **Deployments → View Logs**. A healthy start looks like:

   ```
   INFO bot.main: seeded 7 default templates      (first start only)
   INFO bot.services.scheduler: scheduler started (poll every 20s)
   INFO bot.main: starting long polling
   ```

6. **Verify the bot responds.** In Telegram, open your bot and send `/start`. As an admin you'll see the admin help; `/templates` should list the 7 store templates.
7. **Add it to the channel** (if you haven't in step 2): make the bot a channel administrator with post/edit/delete rights, then in the bot run `/new`, compose a quick test post, and press **🚀 Опубликовать сейчас**. The post should appear in the channel — you're live. 🎉

### Optional: webhook mode

Polling is recommended and needs nothing else. If you prefer webhooks:

1. In the bot service, open **Settings → Networking → Generate Domain** and copy the public URL (e.g. `https://your-app.up.railway.app`).
2. Add variables: `RUN_MODE=webhook` and `WEBHOOK_URL=https://your-app.up.railway.app`.
3. Redeploy. The app now listens on Railway's `PORT`, serves Telegram updates on `/webhook`, and exposes `GET /health` — only in this mode may you set `/health` as the health-check path in Settings.

---

## Command reference

All commands are sent to the bot in a private chat. Commands marked 🔒 work for admins only.

| Command | What it does |
|---|---|
| `/start`, `/help` | Show help (admin menu for admins, read-only info otherwise) |
| `/id` | Show your Telegram user ID and the current chat ID |
| 🔒 `/new` | Compose a new post: text → photos (up to 10, single or album) → inline URL buttons → preview → publish now / schedule / keep as draft |
| 🔒 `/templates` | List templates; tap one to create a post from it (the bot asks for each `{placeholder}` value), 👁 to view, 🗑 to delete |
| 🔒 `/addtemplate` | Add a new template or update an existing one (same name = update) |
| 🔒 `/posts` | Browse recent posts; open one to publish, reschedule, edit text/buttons, preview, or delete |
| 🔒 `/scheduled` | Show the queue of scheduled posts, soonest first |
| 🔒 `/cancel` | Abort the current wizard/action |

**Button format** (one row per line, `&&` between buttons in a row):

```
🛍 Каталог | https://t.me/BEAUTYSUPPLYMSK
💬 WhatsApp | https://wa.me/79990000000 && ☎️ Позвонить | https://t.me/manager
```

**Schedule time formats** (interpreted in `TIMEZONE`): `25.12.2026 18:30` · `25.12 18:30` · `18:30` (today/tomorrow) · `+30m` / `+2h` / `+1d`.

**Telegram limits handled by the bot:** 4096 characters for text-only posts, 1024 for photo captions, max 10 photos per album; albums can't carry inline keyboards, so the bot attaches the buttons as a reply message under the album.

## Environment variables

See [`.env.example`](.env.example) for the documented list: `BOT_TOKEN`, `CHANNEL_ID`, `ADMIN_IDS`, `DATABASE_URL`, `TIMEZONE`, `RUN_MODE`, and — webhook mode only — `WEBHOOK_URL`, `WEBHOOK_SECRET` and `PORT`.
