"""Provide hooks to a database engine and sessions.

This module initializes and manages the database engine and provides a couple
of wrappers and function for session management.
It creates a SQLite engine instance and binds a session factory object to it.
"""

from pymongo import MongoClient

mongo = MongoClient()
