# S77 Discord Requests

Web app for Server 77 players to request Capital Buffs (via web + Discord). Built with FastAPI + Uvicorn, UTC-only time, Argon2id passwords, role-based Admin/User, iCal export, Discord sync, multilingual UI, gold-on-black theme.

## Features
- Login/Registration (`/login`, `/register`) — first user becomes Admin
- Roles: **Admin** / **User**; Admin approval required for new users
- Modern UTC date/time pickers, conflict checks, 1-hour slots
- View 2 days of Buffs; source shows **Web** or **Discord**
- iCal export: `/ical/two-days.ics`
- Edit future buffs (title/time) if not taken
- Auto-expire past buffs from the view (kept in audit logs)
- Admin Panel: approve/disable users, change roles, force password reset
- Discord bot syncing (bi-directional; conflict detection)
- Audit log (IP masked in Admin view)
- Translations: en, tr, ko, pt, zh-Hans, ja, es, de, fr, hi, **id**, **it**
- Hard-coded UTC (AoE Mobile uses UTC only)
- All new users land on `/login`
- App binds to `192.168.15.71:8000` by default

## Prereqs
- Ubuntu 24.04 LTS
- Python 3.12 (system), `python3-venv`
- PostgreSQL 14+ (recommended) or SQLite (dev)
- Nginx Proxy Manager + Cloudflare SSL (existing)
- Systemd

## Install (fresh)
```bash
sudo mkdir -p /opt/s77 && cd /opt/s77
python3 -m venv venv
source venv/bin/activate

# your code should be under /opt/s77/app
# install deps
pip install -U pip wheel
pip install fastapi uvicorn[standard] jinja2 sqlalchemy psycopg2-binary passlib[bcrypt,argon2] python-dateutil pydantic

# (Optional) Set DB env if not in settings.py
# export DATABASE_URL="postgresql+psycopg2://user:pass@127.0.0.1:5432/s77"

# first run (dev):
uvicorn s77.main:app --host 192.168.15.71 --port 8000