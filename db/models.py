from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Request(Base):

    STATUS_PENDING = "PENDING"
    STATUS_QUEUED = "QUEUED"
    STATUS_RUNNING = "RUNNING"
    STATUS_FINISHED = "FINISHED"

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    service = Column(String)
    uuid = Column(String(32), default=lambda: uuid.uuid4().hex, index=True)
    status = Column(String, default=STATUS_PENDING)

    def __repr__(self):
        return ("<Request(id={id}, service={service})>"
                .format(id=self.id, service=self.service))


class Option(Base):

    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    name = Column(String(16))
    type = Column(String(8))
    value = Column(String)
    request_id = Column(Integer, ForeignKey('requests.id'))

    request = relationship("Request", back_populates="options")

    def __repr__(self):
        return ("<Option(name={name}, value={value}>"
                .format(name=self.name, value=self.value))

Request.options = relationship("Option", back_populates="request")


class File(Base):

    __tablename__ = "files"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    title = Column(String(32))
    description = Column(String)
    mimetype = Column(String(32))
    filename = Column(String(32))

    def __repr__(self):
        return ("<File(id={id}, title={title}, filename={filename}"
                .format(id=self.id, title=self.title, filename=self.filename))
