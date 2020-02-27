import pymongo.database

from .documents import MongoDocument


def insert_one(database: pymongo.database.Database, item: MongoDocument):
    database[item.__collection__].insert_one(item)


def push_one(database: pymongo.database.Database, item: MongoDocument):
    """Updates the database from the object's keys."""
    database[item.__collection__].update_one(
        {'_id': item.id}, {'$set': item}
    )


def pull_one(database: pymongo.database.Database, item: MongoDocument):
    """Updates the object from the database."""
    data = database[item.__collection__].find_one({'_id': item.id})
    if data is None:
        raise TypeError("Document not found in the collection")
    del data['_id']
    item.update(data)
