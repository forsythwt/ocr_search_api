from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")

class Page(Base):
    __tablename__ = "pages"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    regular_image_path = Column(String(512), nullable=False)
    zoomed_image_path = Column(String(512), nullable=False)
    ocr_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="pages")

# MySQL FULLTEXT index (ignored on other DBs)
Index("ix_pages_ocr_fulltext", Page.ocr_text, mysql_prefix="FULLTEXT")