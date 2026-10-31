"""
Database connection module.
Reads configuration from config.py and provides a connection.
"""
import os
import socket

import psycopg2
from psycopg2.extras import RealDictCursor
from database_settings import resolve

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


try:
    from config import DB_HOST as CONFIG_DB_HOST
    from config import DB_PORT as CONFIG_DB_PORT
    from config import DB_NAME as CONFIG_DB_NAME
    from config import DB_USER as CONFIG_DB_USER
except ImportError:
    CONFIG_DB_HOST = None
    CONFIG_DB_PORT = None
    CONFIG_DB_NAME = None
    CONFIG_DB_USER = None

_settings = resolve(dict(zip(
    ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"),
    (CONFIG_DB_HOST, CONFIG_DB_PORT, CONFIG_DB_NAME, CONFIG_DB_USER),
)))
DB_HOST = _settings["DB_HOST"]
DB_PORT = _settings["DB_PORT"]
DB_NAME = _settings["DB_NAME"]
DB_USER = _settings["DB_USER"]
DB_EXPECTED_SERVER_MAJOR = _settings["DB_EXPECTED_SERVER_MAJOR"]

if not DB_HOST:
    raise RuntimeError(
        "No database host configured. Set DB_HOST/PGHOST or define DB_HOST in config.py. "
        "On udara, use DB_HOST=raksasa (or an SSH tunnel and explicit local port)."
    )

if (
    socket.gethostname().lower().startswith("udara")
    and DB_HOST in LOCAL_DB_HOSTS
    and os.environ.get("ALLOW_LOCALHOST_DB") != "1"
):
    raise RuntimeError(
        "Localhost PostgreSQL is disabled on udara. "
        "Use DB_HOST=raksasa (or a tunnel), or set ALLOW_LOCALHOST_DB=1 to override intentionally."
    )


def get_connection(dict_cursor=False):
    """Get a PostgreSQL database connection."""
    cursor_factory = RealDictCursor if dict_cursor else None
    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        cursor_factory=cursor_factory
    )
    # libpq exposes these without issuing SQL or starting a transaction.
    if ((connection.info.dbname, connection.info.user, connection.info.port) !=
            (DB_NAME, DB_USER, DB_PORT) or
            (DB_EXPECTED_SERVER_MAJOR and
             connection.server_version // 10000 != DB_EXPECTED_SERVER_MAJOR)):
        connection.close()
        raise RuntimeError("Database endpoint identity does not match configured target")
    return connection
