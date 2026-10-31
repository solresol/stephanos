"""Check the resolved endpoint or export its nonsecret shell defaults."""

import argparse
import json
import os
import shlex

import db
from database_settings import ALIASES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()
    expected = {key: getattr(db, key) for key in ALIASES}
    if args.shell:
        for key, value in expected.items():
            schema_key = key.replace("DB_", "SCHEMA_DB_", 1)
            if os.environ.get(schema_key) and str(value) != os.environ[schema_key]:
                raise RuntimeError(f"{schema_key} differs from the application endpoint")
            for alias in (key, ALIASES[key], schema_key):
                print(f"export {alias}={shlex.quote(str(value))}")
        return
    with db.get_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_user,current_setting('port'),"
                       "current_setting('server_version_num')::integer / 10000")
        identity = cursor.fetchone()
        if identity[:3] != (db.DB_NAME, db.DB_USER, str(db.DB_PORT)):
            raise RuntimeError("Resolved connection does not match the server identity")
        if db.DB_EXPECTED_SERVER_MAJOR and identity[3] != db.DB_EXPECTED_SERVER_MAJOR:
            raise RuntimeError("Wrong PostgreSQL server version")
    print(json.dumps(dict(zip(("database", "user", "port", "major"), identity))))


if __name__ == "__main__":
    main()
