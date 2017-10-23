"""Provide hooks to a database engine and sessions.

This module initializes and manages the database engine and provides a couple
of wrappers and function for session management.
It creates a SQLite engine instance and binds a session factory object to it.
"""


import os

import sqlalchemy.orm.session

from .models import Base

DB_FILENAME = 'sqlite3.db'
engine = sqlalchemy.create_engine(
    'sqlite:///{}'.format(DB_FILENAME), echo=False
)

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
    try:
        os.remove(DB_FILENAME)
    except FileNotFoundError as e:
        print(str(e))


def check_db():
    """Test if database is present."""
    return os.path.exists(DB_FILENAME)


class start_session:
    """Context manager for starting and closing the session.

    This class helps to easily start and close session even if the exception
    occurs while operating on the session.
    On entering, it creates and returns a new session object which can be used
    to communicate database queries. Changes are not committed on exit so
    any uncaught exception raised inside of the context manager or not
    committing changes manually results in rolling back all changes.
    """

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
        self._session.close()
