from sqlalchemy.orm import Session
from ..models import AuditLog

def log(db: Session, action: str, ip: str | None = None, actor: str | None = None, details: str | None = None):
    db.add(AuditLog(action=action, ip=ip, actor=actor, details=details))
    db.commit()
