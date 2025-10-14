from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from itsdangerous import URLSafeSerializer
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.hash import argon2
from .db import get_db
from .models import User, Role
from .settings import settings

# Argon2id via passlib (argon2-cffi under the hood)
def hash_password(pw: str) -> str:
    return argon2.using(type="ID").hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return argon2.verify(pw, hashed)
    except Exception:
        return False

AUTH_COOKIE = "s77session"
ser = URLSafeSerializer(settings.SECRET_KEY, salt="s77-auth")

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    raw = request.cookies.get(AUTH_COOKIE)
    if not raw:
        return None
    try:
        data = ser.loads(raw)
        name = data.get("aoe_name")
        if not name:
            return None
        user = db.query(User).filter(User.aoe_name == name).first()
        return user
    except Exception:
        return None

def require_login(user: User | None):
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

def require_admin(user: User | None):
    if not user or user.role != Role.admin:
        raise HTTPException(status_code=403, detail="Admin required")
