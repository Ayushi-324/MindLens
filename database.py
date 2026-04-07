import os
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Get the database URL from the internet (if we are live)
# If it doesn't exist, fall back to our local SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mindlens.db")

# Cloud databases sometimes use 'postgres://', but SQLAlchemy requires 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs a special rule, PostgreSQL doesn't
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class AnalysisModel(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, index=True)
    text = Column(String)
    score = Column(Integer)
    summary = Column(String)
    bias_count = Column(Integer)


class BiasRecordModel(Base):
    __tablename__ = "bias_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, index=True)
    bias_name = Column(String)
    explanation = Column(String)
    analysis_id = Column(Integer)

Base.metadata.create_all(bind=engine)