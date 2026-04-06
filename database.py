from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./mindlens.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class AnalysisModel(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String)
    score = Column(Integer)
    summary = Column(String)
    bias_count = Column(Integer)


class BiasRecordModel(Base):
    __tablename__ = "bias_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bias_name = Column(String)
    explanation = Column(String)
    analysis_id = Column(Integer)


Base.metadata.create_all(bind=engine)