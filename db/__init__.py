import sqlalchemy
import sqlalchemy.orm

from .models import Base, Request, Option

engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=True)
Session = sqlalchemy.orm.sessionmaker(bind=engine)
Base.metadata.create_all(engine)
