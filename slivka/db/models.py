import os
import uuid
from datetime import datetime

from slivka.utils import JobStatus
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Request(Base):

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    service = Column(String, nullable=False)
    uuid = Column(String(32), default=lambda: uuid.uuid4().hex, index=True)
    status_string = Column(
        String(16), default=JobStatus.PENDING.value, nullable=False
    )
    working_dir = Column(String(128), default=None, nullable=True)
    serial_job_handler = Column(String(128), nullable=True, default=None)
    run_configuration = Column(String(16), nullable=True, default=None)

    options = relationship('Option', back_populates='request')
    files = relationship('File', back_populates='request')

    @property
    def status(self):
        return JobStatus(self.status_string)

    @status.setter
    def status(self, job_status):
        self.status_string = job_status.value

    def is_finished(self):
        return self.status not in {
            JobStatus.PENDING,
            JobStatus.ACCEPTED,
            JobStatus.QUEUED,
            JobStatus.RUNNING
        }

    def __repr__(self):
        return ('<Request(id={id}, service={service})>'
                .format(id=self.id, service=self.service))


class Option(Base):

    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    name = Column(String(16), nullable=False)
    value = Column(String)
    request_id = Column(
        Integer,
        ForeignKey('requests.id', ondelete='CASCADE')
    )

    request = relationship('Request', back_populates='options', uselist=False)

    def __repr__(self):
        return ("<Option(name={name}, value={value}>"
                .format(name=self.name, value=self.value))


def default_title(context):
    return os.path.basename(context.current_parameters['path'])


class File(Base):

    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(32), default=lambda: uuid.uuid4().hex, index=True)
    title = Column(String(32), default=default_title)
    path = Column(String(256), nullable=False)
    url_path = Column(String(256), nullable=False)
    mimetype = Column(String(32))
    request_id = Column(
        Integer,
        ForeignKey('requests.id', ondelete='SET NULL'),
        nullable=True,
        default=None
    )

    request = relationship('Request', back_populates='files', uselist=False)

    def __repr__(self):
        return ("<File(id={id}, title={title}>"
                .format(id=self.id, title=self.title))
