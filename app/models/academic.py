from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Syllabus(Base):
    __tablename__ = "syllabus"

    syllabus_id = Column(Integer, primary_key=True)
    course = Column(String)
    branch = Column(String)
    semester = Column(Integer)
    year = Column(Integer)
    file_path = Column(Text)

class QuestionPaper(Base):
    __tablename__ = "question_papers"

    paper_id = Column(Integer, primary_key=True)
    subject = Column(String)
    year = Column(Integer)
    semester = Column(Integer)
    exam_type = Column(String)
    file_path = Column(Text)

class AnswerPaper(Base):
    __tablename__ = "answer_papers"

    answer_id = Column(Integer, primary_key=True)
    paper_id = Column(Integer)
    file_path = Column(Text)
