from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./fingerprint.db"

engine = SessionLocal = None


def init_db():
    global engine, SessionLocal
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.db.models import Base
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
