from sqlalchemy.orm import Session
from sqlalchemy import select
from models import Giant

def delete_giant(db: Session, giant_id: int, user_id: int) -> bool:
    try:
        gid = int(giant_id)
    except Exception:
        return False
    exists = db.execute(select(Giant.id).where(Giant.id==gid, Giant.user_id==user_id)).first()
    if not exists:
        return False
    db.query(Giant).filter(Giant.id==gid, Giant.user_id==user_id).delete(synchronize_session=False)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
