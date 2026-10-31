"""Stream a consistent, read-only-source SQLite online backup over existing SSH."""

from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


def snapshot(source, output):
    with tempfile.TemporaryDirectory(prefix="stephanos-review-snapshot-") as directory:
        destination = Path(directory) / "snapshot.sqlite"
        with sqlite3.connect(Path(source).resolve().as_uri() + "?mode=ro", uri=True,
                             timeout=10) as incoming:
            incoming.execute("PRAGMA query_only=ON")
            with sqlite3.connect(destination) as outgoing:
                incoming.backup(outgoing, pages=256, sleep=0.1)
                if outgoing.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise RuntimeError("Review SQLite snapshot failed quick_check")
        with destination.open("rb") as stream:
            shutil.copyfileobj(stream, output)


if __name__ == "__main__":
    snapshot(sys.argv[1], sys.stdout.buffer)
