from sqlalchemy import Column, Integer, String, Text, Float
from app.database import Base

class Fee(Base):
    __tablename__ = "fees"

    fee_id = Column(Integer, primary_key=True)
    course = Column(String)
    semester = Column(Integer)
    amount = Column(Float)

class Scholarship(Base):
    __tablename__ = "scholarships"

    scholarship_id = Column(Integer, primary_key=True)
    name = Column(String)
    eligibility = Column(Text)
    deadline = Column(String)

class Faculty(Base):
    __tablename__ = "faculty"

    faculty_id = Column(Integer, primary_key=True)
    name = Column(String)
    department = Column(String)
    designation = Column(String)
    email = Column(String)
