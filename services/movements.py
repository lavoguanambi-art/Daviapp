from sqlalchemy import text
from sqlalchemy.orm import Session

def create_income(db: Session, user_id: int, amount: float, dt: str) -> int:
    row = db.execute(
        text("""INSERT INTO movements (user_id, type, amount, date) 
                VALUES (:u,'IN',:a,:d) RETURNING id"""),
        {"u": user_id, "a": amount, "d": dt}
    ).fetchone()
    return int(row.id)
