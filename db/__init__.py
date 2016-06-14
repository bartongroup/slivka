import sqlalchemy.orm

from .models import Base

engine = sqlalchemy.create_engine('sqlite:///sqlite3.db', echo=True)
Session = sqlalchemy.orm.sessionmaker(bind=engine)


def create_db():
    Base.metadata.create_all(engine)
