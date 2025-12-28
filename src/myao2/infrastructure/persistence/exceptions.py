"""Persistence-related exceptions."""


class PersistenceError(Exception):
    """Base exception for persistence-related errors."""


class DatabaseError(PersistenceError):
    """Database operation error."""
