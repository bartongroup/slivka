import os

import sqlalchemy.orm

from .models import Base

engine = sqlalchemy.create_engine('sqlite:///sqlite3.db', echo=False)
Session = sqlalchemy.orm.sessionmaker(bind=engine)


def create_db():
    Base.metadata.create_all(engine)


def drop_db():
    try:
        os.remove('sqlite3.db')
    except FileNotFoundError as e:
        print(str(e))


class start_session:

    def __enter__(self):
        self._session = Session()
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        self._session.close()
