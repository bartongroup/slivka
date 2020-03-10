import pymongo.database
from pymongo import ReplaceOne
from typing import List

from .documents import MongoDocument


def insert_one(database: pymongo.database.Database, item: MongoDocument):
    database[item.__collection__].insert_one(item)


def insert_many(database: pymongo.database.Database, items: List[MongoDocument]):
    if not items:
        return
    database[items[0].__collection__].insert_many(items)


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


def pull_many(database: pymongo.database.Database, items: List[MongoDocument]):
    items = sorted(items, key=lambda it: it.id)
    cursor = (database[items[0].__collection__]
              .find({'_id': {'$in': [it.id for it in items]}})
              .sort('_id', pymongo.ASCENDING))
    for item, data in zip(items, cursor):
        item.update(data)


def push_many(database: pymongo.database.Database, items: List[MongoDocument]):
    operations = [ReplaceOne({'_id': it.id}, it) for it in items]
    database[items[0].__collection__].bulk_write(operations, ordered=False)
