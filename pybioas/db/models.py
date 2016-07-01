import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Request(Base):

    STATUS_PENDING = "PENDING"
    STATUS_QUEUED = "QUEUED"
    STATUS_RUNNING = "RUNNING"
    STATUS_FAILED = "FAILED"
    STATUS_COMPLETED = "COMPLETED"

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    service = Column(String, nullable=False)
    uuid = Column(String(32), default=lambda: uuid.uuid4().hex, index=True)
    status = Column(String, default=STATUS_PENDING)

    options = relationship("Option", back_populates="request")
    result = relationship("Result", back_populates="request", uselist=False)

    @property
    def is_finished(self):
        return self.status in [self.STATUS_COMPLETED, self.STATUS_FAILED]

    def __repr__(self):
        return ("<Request(id={id}, service={service})>"
                .format(id=self.id, service=self.service))


class Option(Base):

    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    name = Column(String(16), nullable=False)
    value = Column(String)
    request_id = Column(Integer,
                        ForeignKey('requests.id', ondelete='CASCADE'))

    request = relationship("Request", back_populates="options")

    def __repr__(self):
        return ("<Option(name={name}, value={value}>"
                .format(name=self.name, value=self.value))


class Result(Base):

    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    return_code = Column(Integer)
    stdout = Column(String)
    stderr = Column(String)
    request_id = Column(Integer,
                        ForeignKey("requests.id", ondelete="SET NULL"))

    request = relationship("Request", back_populates="result")
    output_files = relationship("File", back_populates="result")


# TODO store file id, file name and file path
# file id - identification used to access the file
# file name - human readable name when downloaded
# file path - real path in a filesystem
class File(Base):

    __tablename__ = "files"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    title = Column(String(32))
    description = Column(String)
    mimetype = Column(String(32))
    filename = Column(String(32))
    result_id = Column(Integer,
                       ForeignKey("results.id", ondelete="SET NULL"),
                       nullable=True, default=None)

    result = relationship("Result", back_populates="output_files")

    def __repr__(self):
        return ("<File(id={id}, title={title}, filename={filename}"
                .format(id=self.id, title=self.title, filename=self.filename))
