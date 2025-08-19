from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import streamlit as st
from contextlib import contextmanager
from typing import Optional, Callable

# Configure the database engine with connection pooling
engine = create_engine(
    'sqlite:///sql_app.db',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    connect_args={'check_same_thread': False},  # Required for SQLite
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections every 30 minutes
    pool_pre_ping=True  # Verify connection before use
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db() -> Session:
    """Context manager for database sessions"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        st.error(f"Database error: {str(e)}")
        raise
    finally:
        session.close()

def safe_operation(operation: Callable, *args, error_msg: str = "Operation failed", **kwargs):
    """Execute a database operation safely with error handling"""
    try:
        with get_db() as session:
            result = operation(session, *args, **kwargs)
            return result
    except Exception as e:
        st.error(f"{error_msg}: {str(e)}")
        return None

def batch_operation(session: Session, items: list, operation: str = 'add'):
    """Handle batch database operations"""
    try:
        if operation == 'add':
            session.bulk_save_objects(items)
        elif operation == 'delete':
            for item in items:
                session.delete(item)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Batch operation failed: {str(e)}")
        return False

# Decorator for retrying operations
def retry_operation(retries: int = 3):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        st.error(f"Operation failed after {retries} attempts: {str(e)}")
                        raise
                    continue
            return None
        return wrapper
    return decorator
