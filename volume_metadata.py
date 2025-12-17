"""
Helpers for inferring Billerbeck volume metadata from filenames/paths.
"""
from pathlib import Path
from typing import Optional

VOLUMES = [
    {
        "volume_number": 1,
        "volume_label": "Billerbeck vol 1",
        "letter_range": "alpha-gamma",
        "keywords": ["vol 1", "alpha - gamma", "alpha-gamma", "alphagamma", "vol1_"],
    },
    {
        "volume_number": 2,
        "volume_label": "Billerbeck vol 2",
        "letter_range": "delta-iota",
        "keywords": ["vol 2", "delta - iota", "delta-iota", "deltaiota", "vol2_"],
    },
    {
        "volume_number": 3,
        "volume_label": "Billerbeck vol 3",
        "letter_range": "kappa-omicron",
        "keywords": [
            "vol 3",
            "kappa - omicron",
            "kappa-omicron",
            "kappaomicron",
            "vol3_",
            "9783110219647",
            "10.1515_9783110219647",
        ],
    },
    {
        "volume_number": 4,
        "volume_label": "Billerbeck vol 4",
        "letter_range": "pi-upsilon",
        "keywords": ["vol 4", "pi - upsilon", "pi-upsilon", "piupsilon", "vol4_"],
    },
    {
        "volume_number": 5,
        "volume_label": "Billerbeck vol 5",
        "letter_range": "phi-omega",
        "keywords": ["vol 5", "phi - omega", "phi-omega", "phiomega", "vol5_"],
    },
]


def infer_volume_metadata(path_or_name: Optional[Path | str], fallback_name: Optional[str] = None):
    """
    Infer volume metadata from a path or name (and optional fallback like image filename).
    Returns dict with volume_number, volume_label, letter_range or None if unknown.
    """
    candidates = []
    if path_or_name:
        candidates.append(str(path_or_name))
    if fallback_name:
        candidates.append(fallback_name)

    lowered = " ".join(candidates).lower()
    if not lowered:
        return None

    for volume in VOLUMES:
        for keyword in volume["keywords"]:
            if keyword in lowered:
                return volume
    return None


def ensure_volume_columns(cur):
    """Ensure volume metadata columns exist on images/epubs/pdf_files tables."""
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS volume_number INTEGER")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS volume_label TEXT")
    cur.execute("ALTER TABLE images ADD COLUMN IF NOT EXISTS letter_range TEXT")

    cur.execute("ALTER TABLE IF EXISTS epubs ADD COLUMN IF NOT EXISTS volume_number INTEGER")
    cur.execute("ALTER TABLE IF EXISTS epubs ADD COLUMN IF NOT EXISTS volume_label TEXT")
    cur.execute("ALTER TABLE IF EXISTS epubs ADD COLUMN IF NOT EXISTS letter_range TEXT")

    cur.execute("ALTER TABLE IF EXISTS pdf_files ADD COLUMN IF NOT EXISTS volume_number INTEGER")
    cur.execute("ALTER TABLE IF EXISTS pdf_files ADD COLUMN IF NOT EXISTS volume_label TEXT")
    cur.execute("ALTER TABLE IF EXISTS pdf_files ADD COLUMN IF NOT EXISTS letter_range TEXT")

    cur.execute("ALTER TABLE IF EXISTS assembled_lemmas ADD COLUMN IF NOT EXISTS volume_number INTEGER")
    cur.execute("ALTER TABLE IF EXISTS assembled_lemmas ADD COLUMN IF NOT EXISTS volume_label TEXT")
    cur.execute("ALTER TABLE IF EXISTS assembled_lemmas ADD COLUMN IF NOT EXISTS letter_range TEXT")
