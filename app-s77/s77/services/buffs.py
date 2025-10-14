from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..models import Buff
from .discord_sync import conflicts as discord_conflicts, write_request

VALID_TITLES = ["Research","Training","Building","Combat","PvP"]
VALID_REGIONS = ["Imperial City","Gaul","Olympia","Neilos","Tinir","East Kingsland","Eastland","Kyuno","North Kingsland","West Kingsland","NA"]

def normalized_hour(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

def check_conflict(db: Session, title: str, start_utc: datetime) -> bool:
    # DB conflict
    exists = db.query(Buff).filter(and_(Buff.title==title, Buff.start_utc==start_utc)).first()
    if exists:
        return True
    # Discord JSON conflict
    return discord_conflicts(title, start_utc)

def create_buff(db: Session, aoe_name: str, title: str, region: str, start_utc: datetime, source="web"):
    start_utc = normalized_hour(start_utc)
    if title not in VALID_TITLES:
        raise ValueError("Invalid title")
    if region not in VALID_REGIONS:
        raise ValueError("Invalid region")
    if check_conflict(db, title, start_utc):
        raise ValueError("Conflict")
    b = Buff(aoe_name=aoe_name, title=title, region=region, start_utc=start_utc, source=source)
    db.add(b); db.commit()
    # write to shared JSON so bot can announce & see parity
    write_request(aoe_name, title, region, start_utc)
    return b
