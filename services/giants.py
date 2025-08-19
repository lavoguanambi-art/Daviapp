from sqlalchemy.orm import Session
from models import Giant

def delete_giant(db: Session, giant_id: int, user_id: int) -> bool:
    q = db.query(Giant).filter(Giant.id == giant_id, Giant.user_id == user_id)
    if not db.query(q.exists()).scalar():
        return False
    q.delete(synchronize_session=False)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
