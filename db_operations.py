from functools import wraps
import time
from contextlib import contextmanager
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from db_utils import get_db_session
import streamlit as st

def retry_on_exception(retries=3, delay=0.5):
    """Decorator to retry database operations on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, SQLAlchemyError) as e:
                    last_exception = e
                    if i < retries - 1:  # Don't sleep on last attempt
                        time.sleep(delay * (i + 1))  # Exponential backoff
            st.error(f"Erro de banco de dados após {retries} tentativas: {str(last_exception)}")
            return None
        return wrapper
    return decorator

@contextmanager
def safe_db_operation():
    """Context manager for safe database operations with automatic retry"""
    try:
        with get_db_session() as session:
            yield session
    except SQLAlchemyError as e:
        st.error(f"Erro de banco de dados: {str(e)}")
        raise

def batch_delete(session, items):
    """Safely delete multiple items in batch"""
    try:
        for item in items:
            session.delete(item)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Erro ao excluir itens: {str(e)}")
        return False

def batch_update(session, items, updates):
    """Safely update multiple items in batch"""
    try:
        for item, update in zip(items, updates):
            for key, value in update.items():
                setattr(item, key, value)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Erro ao atualizar itens: {str(e)}")
        return False
