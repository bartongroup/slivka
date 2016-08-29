import os

import sqlalchemy.orm.session

from .models import Base

DB_FILENAME = 'sqlite3.db'
engine = sqlalchemy.create_engine(
    'sqlite:///{}'.format(DB_FILENAME), echo=False
)

Session = sqlalchemy.orm.sessionmaker(bind=engine)


def create_db():
    Base.metadata.create_all(engine)


def drop_db():
    try:
        os.remove(DB_FILENAME)
    except FileNotFoundError as e:
        print(str(e))


def check_db():
    return os.path.exists(DB_FILENAME)


class start_session:

    def __enter__(self):
        """
        :return: active session object
        :rtype sqlalchemy.orm.session.Session:
        """
        self._session = Session()
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        self._session.close()
