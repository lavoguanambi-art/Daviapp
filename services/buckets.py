from sqlalchemy import text
from sqlalchemy.orm import Session

def split_income_by_buckets(db: Session, user_id: int, movement_id: int, amount: float):
    rows = db.execute(text("SELECT id, percentage FROM buckets WHERE user_id=:u"), {"u": user_id}).fetchall()
    total = sum(r.percentage for r in rows) if rows else 0
    if total <= 0: 
        return
    for r in rows:
        part = amount * (r.percentage/100.0)
        db.execute(
            text("INSERT INTO movement_allocations (movement_id, bucket_id, value) VALUES (:m,:b,:v)"),
            {"m": movement_id, "b": r.id, "v": part}
        )
