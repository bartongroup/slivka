"""Provide hooks to a database engine and sessions.

This module initializes and manages the database engine and provides a couple
of wrappers and function for session management.
It creates a SQLite engine instance and binds a session factory object to it.
"""


import sqlalchemy.orm.session

import slivka
from .models import Base

engine = sqlalchemy.create_engine(slivka.settings.DATABASE_URL, echo=False)

Session = sqlalchemy.orm.sessionmaker(bind=engine)


def create_db():
    """Create a database.

    Fetch all database models which inherit from a common ``db.models.Base``
    class and populate the database with empty tables using a current engine.
    """
    Base.metadata.create_all(engine)


def drop_db():
    """Delete the entire database.

    Since the SQLite backend is used, delete the database file.
    """
    Base.metadata.drop_all(engine)


class start_session:
    """Context manager for starting and closing the session.

    This class helps to easily start and close session even if the exception
    occurs while operating on the session.
    On entering, it creates and returns a new session object which can be used
    to communicate database queries. By default, changes are not committed on
    exit so any uncaught exception raised inside of the context manager or not
    committing changes manually results in rolling back all changes.
    """

    def __init__(self, commit_on_exit=False):
        self._commit = commit_on_exit

    def __enter__(self):
        """Create a new database session.

        :return: active session object
        :rtype sqlalchemy.orm.session.Session:
        """
        self._session = Session()
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """Close a database session."""
        if self._commit:
            self._session.commit()
        self._session.close()
