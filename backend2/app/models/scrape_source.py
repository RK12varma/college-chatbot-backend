from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base

class ScrapeSource(Base):
    __tablename__ = "scrape_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
