# UniFind / FindIt – Backend (FastAPI + MySQL)

Runs on **http://localhost:4000** so the React frontend (`VITE_API_URL=http://localhost:4000/api`) works with no code changes.

## 1. Requirements
- Python 3.10+
- MySQL 8 (optional – SQLite works for a quick start)

## 2. Install
```bash
cd unifind-backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```
Open `.env` and set `SECRET_KEY` to a long random value:
`python -c "import secrets; print(secrets.token_hex(32))"`

## 3. Database
**Quick start (SQLite):** keep `DATABASE_URL=sqlite:///./unifind.db` – nothing else to do.

**MySQL (recommended):**
1. Run `schema.sql` in MySQL Workbench / terminal (`mysql -u root -p < schema.sql`). Change the password inside first.
2. In `.env` set
   `DATABASE_URL=mysql+pymysql://unifind_user:YourPassword@localhost:3306/unifind`

Tables are created automatically on first start.

## 4. Seed + run
```bash
python seed.py                                   # sample items + admin user
uvicorn app.main:app --reload --port 4000
```
- API docs (try every endpoint): http://localhost:4000/docs
- Health check: http://localhost:4000/api/health
- Default admin: `admin@unifind.lk` / `ChangeMe12345` → **change it** (set `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars before seeding).

## 5. Run the frontend
```bash
cd unifind-frontend
npm install
npm run dev          # http://localhost:5173
```
The Explore page now loads items from the API, and "Submit report" saves to the database (with photos). If the backend is off, the app falls back to sample data.

## 6. Tests
```bash
pytest
```

## API
| Method | Path | Notes |
|---|---|---|
| GET | `/api/items` | filters: `q`, `type` (Lost/Found), `category`, `district`, `sort` (newest/oldest), `limit`, `offset` |
| GET | `/api/items/{id}` | one item |
| POST | `/api/items` | create report – **login required**; `owner_id` is set to the logged-in user |
| POST | `/api/items/{id}/images` | multipart `files` – PNG/JPG/WEBP, max 5 MB, max 5 photos (report owner or admin) |
| GET | `/api/items/mine` | my reports (login) |
| PATCH | `/api/items/{id}/status` | `Active` / `Resolved` (owner or admin) |
| DELETE | `/api/items/{id}` | owner or admin |
| POST | `/api/auth/register`, `/api/auth/login` | returns JWT |
| GET | `/api/auth/me` | current user |
| GET / PUT / DELETE | `/api/saved`, `/api/saved/{id}` | saved items (login) |
| POST | `/api/conversations` | body `{item_id}` – open (or re-open) a chat with the reporter of that item. Login required |
| GET | `/api/conversations` | my chats, newest first, with last message + unread count |
| GET | `/api/conversations/{id}/messages` | messages; `?after_id=N` returns only newer ones (used for polling). Opening marks the other person's messages as read |
| POST | `/api/conversations/{id}/messages` | body `{body}` (1–1000 chars). Notifies the other person |
| GET | `/api/notifications` | my notifications |
| GET | `/api/notifications/summary` | `{unread_notifications, unread_messages}` for the badges |
| POST | `/api/notifications/{id}/read`, `/api/notifications/read-all` | mark as read |
| GET | `/api/admin/stats` | admin only |
| GET | `/api/meta` | categories + districts |

Send the token as `Authorization: Bearer <token>`.

## Structure
```
app/
  main.py        app, CORS, static files
  config.py      settings from .env (+ category/district lists)
  database.py    engine + session
  models.py      User, Item, ItemImage, SavedItem, Conversation, Message, Notification
  schemas.py     request/response validation
  security.py    bcrypt + JWT, current-user helpers
  routers/       auth, items, saved, conversations, notifications, admin
seed.py  schema.sql  tests/
```

## How users and reports are linked
`items.owner_id` is a foreign key to `users.id`. Check it in MySQL:
```sql
SHOW CREATE TABLE items;   -- look for FOREIGN KEY (owner_id) REFERENCES users (id)
SELECT u.email, i.title FROM items i JOIN users u ON u.id = i.owner_id;
-- old rows made before login was required (owner_id IS NULL) can be given an owner:
UPDATE items SET owner_id = 1 WHERE owner_id IS NULL;
```

## Chat & notifications – how it is linked in the database
```
users ──< items.owner_id                         (who reported the item)
items ──< conversations.item_id                  (which report the chat is about)
users ──< conversations.owner_id / .starter_id   (reporter / the person who contacted them)
conversations ──< messages.conversation_id
users ──< messages.sender_id
users ──< notifications.user_id  (+ conversation_id, item_id)
```
- One chat per (item, person): `UNIQUE (item_id, starter_id)`.
- Deleting a report deletes its chats, messages and notifications (`ON DELETE CASCADE`).
- Only the two people in a chat can read it (others get 404). Only the **first name** of the other person is ever sent to the browser – never e-mail.
- A new message creates one unread notification for the other person; further messages in the same chat refresh it instead of piling up. Opening the chat marks it read.
- Marking a report **Resolved** notifies everyone who chatted about it. New chats on resolved reports are blocked; existing chats keep working so people can arrange the hand-over.
- Updates use short polling (4 s in an open chat, 15 s for the badges). That works on any host with no extra setup; WebSockets can replace it later.
- SQLite now enforces foreign keys too (`PRAGMA foreign_keys=ON`), matching MySQL.

### Upgrading an existing database
Run the app once – the three new tables are created automatically. The old `users.university` column is no longer used; it is harmless, but you can remove it:
```sql
ALTER TABLE users DROP COLUMN university;
```

## Not built yet (next steps)
- Email / push notifications when you are offline
- WebSockets instead of polling
- Photo attachments in chat, report/block a user
- Matching Lost ↔ Found automatically
- Ownership verification questions before hand-over
- Deployment (set a real `SECRET_KEY`, strong DB password, HTTPS, your real domain in `CORS_ORIGINS`)
