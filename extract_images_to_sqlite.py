import sqlite3
import sys
from pathlib import Path
from bs4 import BeautifulSoup

DB_PATH = "stephanos.db"

def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_filename TEXT UNIQUE NOT NULL,
        processed INTEGER NOT NULL DEFAULT 0,
        lemma_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        processed_at DATETIME
    )
    """)
    conn.commit()

def extract_images(html_path: Path):
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    images = []

    for div in soup.select("div.illustype_image_text img"):
        src = div.get("src")
        if src:
            images.append(src)

    return images

def main():
    if len(sys.argv) != 2:
        print("Usage: python extract_images_to_sqlite.py <html_file>")
        sys.exit(1)

    html_file = Path(sys.argv[1])
    if not html_file.exists():
        raise FileNotFoundError(html_file)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    images = extract_images(html_file)

    for img in images:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO images (image_filename) VALUES (?)",
                (img,)
            )
        except Exception as e:
            print(f"Error inserting {img}: {e}")

    conn.commit()
    conn.close()

    print(f"Inserted {len(images)} image references.")

if __name__ == "__main__":
    main()
