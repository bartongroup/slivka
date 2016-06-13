from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Request(Base):

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    service = Column(String)

    def __repr__(self):
        return ("<Request(id={id}, service={service})>"
                .format(id=self.id, service=self.service))


class Option(Base):

    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    option_id = Column(String(16))
    type = Column(String(8))
    value = Column(String)
    request_id = Column(Integer, ForeignKey('requests.id'))

    request = relationship("Request", back_populates="options")

    def __repr__(self):
        return ("<Option(type={type}, value={value}>"
                .format(type=self.type, value=self.value))


Request.options = relationship("Option", back_populates="request")
