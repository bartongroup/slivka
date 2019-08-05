"""Provide hooks to a database engine and sessions.

This module initializes and manages the database engine and provides a couple
of wrappers and function for session management.
It creates a SQLite engine instance and binds a session factory object to it.
"""

import sqlalchemy.orm

import slivka
from .models import Base

engine = sqlalchemy.create_engine(slivka.settings.DATABASE_URL, echo=False)
Session = sqlalchemy.orm.sessionmaker(bind=engine)


def create_db():
    """Create the database schema."""
    Base.metadata.create_all(engine)


def drop_db():
    """Delete the database content."""
    Base.metadata.drop_all(engine)


class start_session:
    """Context manager for convenient session scope."""
    def __init__(self, commit_on_exit=False, **kwargs):
        self._commit = commit_on_exit
        self._session = Session(**kwargs)

    def __enter__(self) -> sqlalchemy.orm.Session:
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        if self._commit:
            self._session.commit()
        self._session.close()
