import json, os
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from ..settings import settings

def _ensure_file():
    if not os.path.exists(settings.SHARED_JSON):
        with open(settings.SHARED_JSON, "w", encoding="utf-8") as f:
            f.write("{}")

def read_all() -> Dict[str, dict]:
    _ensure_file()
    with open(settings.SHARED_JSON, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def write_request(aoe_name: str, title: str, region: str, start_utc: datetime):
    d = read_all()
    req_id = str(datetime.now(timezone.utc).timestamp())
    d[req_id] = {
        "user_id": 0,
        "user_name": aoe_name,
        "title": title,
        "time_slot": start_utc.isoformat(),          # ISO8601 UTC
        "region": region,
        "request_time": datetime.now(timezone.utc).isoformat()
    }
    with open(settings.SHARED_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=4)

def conflicts(title: str, start_utc: datetime) -> bool:
    for req in read_all().values():
        t = req.get("title")
        ts = req.get("time_slot")
        if not (t and ts):
            continue
        try:
            when = datetime.fromisoformat(ts)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if t == title and when == start_utc:
                return True
        except Exception:
            continue
    return False

def list_upcoming_two_days(now_utc: datetime) -> List[dict]:
    end = now_utc + timedelta(days=2)
    out: List[dict] = []
    for _, v in read_all().items():
        ts = v.get("time_slot")
        if not ts:
            continue
        try:
            when = datetime.fromisoformat(ts)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if now_utc <= when < end:
            out.append({
                "id": f"discord:{v.get('request_time','')}",
                "aoe_name": v.get("user_name", "unknown"),
                "title": v.get("title", "Unknown"),
                "region": v.get("region", "NA"),
                "start_utc": when,
                "source": "discord"
            })
    # dedupe by (title, start)
    dedup = {}
    for e in out:
        k = (e["title"], e["start_utc"].isoformat())
        dedup[k] = e
    return list(dedup.values())

def delete_request(title: str, start_utc: datetime) -> bool:
    """Remove the Discord JSON entry that matches (title, exact UTC hour)."""
    d = read_all()
    keys = []
    for k, v in d.items():
        ts = v.get("time_slot")
        if not ts:
            continue
        try:
            when = datetime.fromisoformat(ts)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if v.get("title") == title and when == start_utc:
            keys.append(k)
    for k in keys:
        d.pop(k, None)
    if keys:
        with open(settings.SHARED_JSON, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=4)
        return True
    return False

def clear_all():
    """Clear the entire shared JSON (admin use)."""
    with open(settings.SHARED_JSON, "w", encoding="utf-8") as f:
        f.write("{}")
