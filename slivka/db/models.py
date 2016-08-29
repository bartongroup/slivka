import os
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Request(Base):

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    service = Column(String, nullable=False)
    uuid = Column(String(32), default=lambda: uuid.uuid4().hex, index=True)
    pending = Column(Boolean, default=True)

    options = relationship("Option", back_populates="request")
    job = relationship("JobModel", back_populates="request", uselist=False)

    @property
    def is_finished(self):
        return self.status in {
            JobModel.STATUS_COMPLETED, JobModel.STATUS_FAILED,
            JobModel.STATUS_ERROR
        }

    @property
    def status(self):
        if self.job is None:
            return JobModel.STATUS_PENDING
        else:
            return self.job.status

    def __repr__(self):
        return ("<Request(id={id}, service={service})>"
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

    request = relationship("Request", back_populates="options", uselist=False)

    def __repr__(self):
        return ("<Option(name={name}, value={value}>"
                .format(name=self.name, value=self.value))


class JobModel(Base):

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_ERROR = "error"

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    request_id = Column(
        Integer,
        ForeignKey('requests.id', ondelete='CASCADE'),
        nullable=False
    )
    status = Column(String(16), default=STATUS_QUEUED, nullable=False)
    job_ref_id = Column(String(32))
    working_dir = Column(String(256))
    service = Column(String(16), nullable=False)
    configuration = Column(String(16), nullable=False)
    return_code = Column(String(8), nullable=True)

    request = relationship("Request", back_populates="job", uselist=False)
    files = relationship("File", back_populates="job")


def default_title(context):
    return os.path.basename(context.current_parameters['path'])


class File(Base):

    __tablename__ = "files"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    title = Column(String(32), default=default_title)
    path = Column(String(256), nullable=False)
    mimetype = Column(String(32))
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        default=None
    )

    job = relationship("JobModel", back_populates="files", uselist=False)

    def __repr__(self):
        return ("<File(id={id}, title={title}>"
                .format(id=self.id, title=self.title))
