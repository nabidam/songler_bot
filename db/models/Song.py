from sqlalchemy import Column, DateTime, Text, String, Integer
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Song(Base):
    __tablename__ = "song"

    id = Column(Integer, primary_key=True)
    song = Column(String(255))
    artist = Column(String(255))
    link = Column(Text())
    filepath = Column(Text())
    thumbnail = Column(Text())
    created_at = Column(DateTime())

    def __repr__(self):
        return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"
