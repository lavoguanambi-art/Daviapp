from contextlib import contextmanager
import math
import streamlit as st
from sqlalchemy import delete
from models import Giant, GiantPayment, Movement, Bucket

@contextmanager
def tx(db):
    """Gerenciador de contexto para transações seguras."""
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise

def init_db_pragmas(engine):
    """Configura pragmas do SQLite para melhor performance."""
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")       # escrita concorrente rápida
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")     # latência menor
        conn.exec_driver_sql("PRAGMA foreign_keys=ON;")        # integridade referencial

def delete_giant(db, user_id: int, giant_id: int):
    """Exclui um gigante e seus pagamentos de forma segura."""
    stmt_pay = delete(GiantPayment).where(GiantPayment.giant_id == giant_id)
    stmt_g = delete(Giant).where(Giant.id == giant_id, Giant.user_id == user_id)
    try:
        with db.begin():  # transação segura
            db.execute(stmt_pay)
            res = db.execute(stmt_g)
            db.commit()  # commit explícito após as deleções
        if res.rowcount == 0:
            st.info("Nada foi excluído (já não existia).")
            return False
        st.toast("Gigante excluído com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
        return False

def distribuir_por_baldes(db, user_id: int, valor: float, descricao: str, data_mov, tipo: str):
    """Distribui um valor entre os baldes conforme seus percentuais."""
    buckets = db.query(Bucket).filter_by(user_id=user_id).all()
    total = sum(b.percent for b in buckets) or 0.0
    if total <= 0:
        st.error("Defina percentuais nos Baldes.")
        return False
    
    try:
        with tx(db):
            for b in buckets:
                quota = valor * (b.percent / total)
                mov = Movement(
                    user_id=user_id,
                    bucket_id=b.id,
                    kind="Receita" if tipo == "Entrada" else "Despesa",
                    amount=quota,
                    description=f"{descricao} (rateio {b.percent:.1f}%)",
                    date=data_mov,
                )
                db.add(mov)
                if tipo == "Entrada":
                    b.balance += quota
                else:
                    b.balance -= quota
        return True
    except Exception as e:
        st.error(f"Erro ao distribuir valor: {e}")
        return False

def giant_forecast(giant, db):
    """Calcula previsões para um gigante."""
    try:
        pago = sum(p.amount for p in db.query(GiantPayment).where(GiantPayment.giant_id==giant.id))
        restante = max(giant.total_to_pay - pago, 0.0)
        diaria = (giant.weekly_goal or 0.0)/7.0
        dias = (restante/diaria) if diaria>0 else None
        return restante, diaria, dias
    except Exception as e:
        st.error(f"Erro ao calcular previsão: {e}")
        return 0.0, 0.0, None

def check_giant_victory(db, giant, valor_aporte):
    """Verifica se um gigante foi derrotado após um aporte."""
    try:
        total_pago = sum(p.amount for p in db.query(GiantPayment).filter_by(giant_id=giant.id))
        if giant.total_to_pay > 0 and (total_pago + valor_aporte) >= giant.total_to_pay:
            giant.status = "defeated"
            giant.progress = 1.0
            st.balloons()
            st.success(f"🏅 Vitória! {giant.name} foi derrotado!")
            st.toast("Meta alcançada!", icon="🎯")
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao verificar vitória: {e}")
        return False
    try:
        with db_transaction() as session:
            result = operation(session, *args, **kwargs)
            return result
    except Exception as e:
        st.error(f"Operation failed: {str(e)}")
        return None

def batch_save(session: Session, items: list):
    """Save multiple items in a batch"""
    try:
        session.bulk_save_objects(items)
        return True
    except Exception as e:
        st.error(f"Batch save failed: {str(e)}")
        return False

def safe_delete(session: Session, item):
    """Safely delete an item with proper error handling"""
    try:
        session.delete(item)
        return True
    except Exception as e:
        st.error(f"Delete failed: {str(e)}")
        return False

def safe_commit(session: Session):
    """Safely commit changes with proper error handling"""
    try:
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Commit failed: {str(e)}")
        return False
