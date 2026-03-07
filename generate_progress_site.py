#!/usr/bin/env python3
"""
Generate the public root progress page.

This remains as a backwards-compatible wrapper around the richer
pipeline progress report so `/progress.html` and `/pipeline.html`
show the same current workflow.
"""
from pathlib import Path

import db
from generate_pipeline_progress import generate_html, get_progress_stats

OUTPUT_FILE = Path("progress.html")


def main():
    conn = db.get_connection()
    stats = get_progress_stats(conn)
    conn.close()

    html = generate_html(stats)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    print(f"Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
