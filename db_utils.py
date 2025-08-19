from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Configure engine with connection pooling
engine = create_engine(
    'sqlite:///sql_app.db', 
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections every 30 minutes
    pool_pre_ping=True  # Verify connection before use
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db_session():
    """Context manager for database sessions with automatic cleanup."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def batch_operation(session: Session, items, operation='add'):
    """Handle batch operations efficiently."""
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
        raise e
