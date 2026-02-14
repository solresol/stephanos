"""
Database connection module.
Reads configuration from config.py and provides a connection.
"""
import os
import socket

import psycopg2
from psycopg2.extras import RealDictCursor

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _load_setting(config_value, env_names, default=None):
    """Use config value first, then environment variables, then default."""
    if config_value not in (None, ""):
        return config_value
    for env_name in env_names:
        env_value = os.environ.get(env_name)
        if env_value not in (None, ""):
            return env_value
    return default


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

DB_HOST = _load_setting(CONFIG_DB_HOST, ("DB_HOST", "PGHOST"))
DB_PORT = int(_load_setting(CONFIG_DB_PORT, ("DB_PORT", "PGPORT"), default=5432))
DB_NAME = _load_setting(CONFIG_DB_NAME, ("DB_NAME", "PGDATABASE"), default="stephanos")
DB_USER = _load_setting(CONFIG_DB_USER, ("DB_USER", "PGUSER"), default="stephanos")

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
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        cursor_factory=cursor_factory
    )
