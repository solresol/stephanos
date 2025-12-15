"""
Database connection module.
Reads configuration from config.py and provides a connection.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER
except ImportError:
    # Defaults for development
    DB_HOST = "localhost"
    DB_PORT = 5432
    DB_NAME = "stephanos"
    DB_USER = "stephanos"

def get_connection(dict_cursor=False):
    """Get a PostgreSQL database connection."""
    cursor_factory = RealDictCursor if dict_cursor else None
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        cursor_factory=cursor_factory
    )
