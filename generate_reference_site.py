#!/usr/bin/env python3
"""
Generate a reference website showing all lemmas and their translations, grouped by Greek letter.
"""
import json
import re
import html as html_module
import hashlib
import unicodedata
import os
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from db import get_connection
from db import DB_HOST as STEPHANOS_DB_HOST
from db import DB_PORT as STEPHANOS_DB_PORT
from db import DB_USER as STEPHANOS_DB_USER
import canonical_variants
import citation_format

OUTPUT_DIR = "reference_site"

# Greek letters and filenames for per-letter pages
GREEK_LETTERS = [
    ("Α", "Alpha", "alpha"),
    ("Β", "Beta", "beta"),
    ("Γ", "Gamma", "gamma"),
    ("Δ", "Delta", "delta"),
    ("Ε", "Epsilon", "epsilon"),
    ("Ζ", "Zeta", "zeta"),
    ("Η", "Eta", "eta"),
    ("Θ", "Theta", "theta"),
    ("Ι", "Iota", "iota"),
    ("Κ", "Kappa", "kappa"),
    ("Λ", "Lambda", "lambda"),
    ("Μ", "Mu", "mu"),
    ("Ν", "Nu", "nu"),
    ("Ξ", "Xi", "xi"),
    ("Ο", "Omicron", "omicron"),
    ("Π", "Pi", "pi"),
    ("Ρ", "Rho", "rho"),
    ("Σ", "Sigma", "sigma"),
    ("Τ", "Tau", "tau"),
    ("Υ", "Upsilon", "upsilon"),
    ("Φ", "Phi", "phi"),
    ("Χ", "Chi", "chi"),
    ("Ψ", "Psi", "psi"),
    ("Ω", "Omega", "omega"),
]

LETTER_BY_CHAR = {char: slug for char, _, slug in GREEK_LETTERS}
LETTER_META_BY_SLUG = {slug: (char, name) for char, name, slug in GREEK_LETTERS}

_WS_RE = re.compile(r"\s+")
_MEINEKE_OBJECT_TAG_RE = re.compile(r"\[/?object[^\]]*\]")
_PAREN_SPAN_RE = re.compile(r"\(([^()]*)\)")
_BRACKET_SPAN_RE = re.compile(r"\[([^\[\]]*)\]")
_CITE_KEYWORD_RE = re.compile(r"(?i)\b(?:FGrHist|fr\.?|fragment(?:um)?|frag\.?)\b")
_CITE_CREF_RE = re.compile(r"\bC\s*\d")
_GREEK_CHAR_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"\d")
_SAFE_REF_RE = re.compile(r"[^0-9A-Za-z._-]+")

OVERLAP_COLOR_CLASSES = ["c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9"]


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for robust string comparison (collapse runs, trim)."""
    if not text:
        return ""
    # Also normalize non-breaking spaces to regular spaces.
    text = text.replace("\u00a0", " ")
    return _WS_RE.sub(" ", text).strip()


def strip_diacritics(text: str) -> str:
    """Remove Greek tone-marks/diacritics (combining marks) for comparison."""
    if not text:
        return ""
    # Normalize first so tonos/oxia etc compare consistently.
    text = unicodedata.normalize("NFC", text)
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", without_marks)


def is_citation_span(span_text: str) -> bool:
    """Heuristic for parenthetical/bracket content that's citation metadata, not lemma text."""
    text = normalize_whitespace(span_text or "")
    if not text:
        return False

    if _CITE_KEYWORD_RE.search(text) or _CITE_CREF_RE.search(text):
        return True

    has_greek = bool(_GREEK_CHAR_RE.search(text))
    has_latin = bool(_LATIN_CHAR_RE.search(text))
    has_digit = bool(_DIGIT_RE.search(text))

    # Purely Latin/digit spans are citation-like in this corpus.
    if not has_greek and (has_latin or has_digit):
        return True

    # Also treat short digit-bearing Greek spans like "(Ν 363)" as references.
    if has_digit:
        greek_words = re.findall(r"[\u0370-\u03FF\u1F00-\u1FFF]{2,}", text)
        if len(greek_words) <= 1:
            return True

    return False


def strip_citation_markers(text: str) -> str:
    """Remove citation-only parenthetical/bracket spans for fair text comparison."""
    if not text:
        return ""

    current = text
    # Re-run a few times in case removal exposes another non-nested span.
    for _ in range(4):
        previous = current

        def paren_repl(match: re.Match) -> str:
            inner = match.group(1)
            return "" if is_citation_span(inner) else match.group(0)

        def bracket_repl(match: re.Match) -> str:
            inner = match.group(1)
            return "" if is_citation_span(inner) else match.group(0)

        current = _PAREN_SPAN_RE.sub(paren_repl, current)
        current = _BRACKET_SPAN_RE.sub(bracket_repl, current)
        if current == previous:
            break

    return current


def classify_text_difference(a: str, b: str) -> str:
    """
    Classify differences between two Greek strings.

    Returns:
        - "same": equal after normalization (strip Meineke [object] tags, strip citation-only markers,
          NFC, collapse whitespace, ignore punctuation/symbols)
        - "tone_marks_only": not equal under that normalization, but equal after removing combining marks
        - "different": base letters differ (or other non-diacritic differences)
    """
    # Strip nodegoat markup present in some Meineke paragraphs.
    a = _MEINEKE_OBJECT_TAG_RE.sub("", a or "")
    b = _MEINEKE_OBJECT_TAG_RE.sub("", b or "")
    a = strip_citation_markers(a)
    b = strip_citation_markers(b)

    def normalize_for_compare(text: str, remove_diacritics: bool) -> str:
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = text.replace("\u00a0", " ")

        if remove_diacritics:
            text = strip_diacritics(text)

        # Ignore punctuation/symbols for comparison.
        chars = []
        for ch in text:
            cat = unicodedata.category(ch)
            if cat.startswith("P") or cat.startswith("S"):
                continue
            chars.append(ch if not ch.isspace() else " ")
        return normalize_whitespace("".join(chars))

    a_exact = normalize_for_compare(a, remove_diacritics=False)
    b_exact = normalize_for_compare(b, remove_diacritics=False)
    if a_exact == b_exact:
        return "same"
    if normalize_for_compare(a, remove_diacritics=True) == normalize_for_compare(b, remove_diacritics=True):
        return "tone_marks_only"
    return "different"


def strip_combining(char: str) -> str:
    """Return base character without combining marks."""
    decomposed = unicodedata.normalize("NFD", char)
    for c in decomposed:
        if not unicodedata.combining(c):
            return c
    return char


def get_initial_slug(text: str) -> str:
    """Find the slug for the first Greek letter in the text."""
    if not text:
        return "other"
    for ch in text:
        base = strip_combining(ch).upper()
        if base in LETTER_BY_CHAR:
            return LETTER_BY_CHAR[base]
    return "other"


def headword_page_filename(lemma_id: int) -> str:
    """Canonical public URL path for a lemma headword page."""
    try:
        lemma_num = int(lemma_id)
    except Exception:
        lemma_num = 0
    return f"headword_{lemma_num}.html"


def ref_to_slug(ref: str) -> str:
    """Convert a textual reference (for example '1.17') into a safe filename slug."""
    slug = (ref or "").strip()
    slug = slug.replace("/", "_").replace(" ", "_")
    slug = _SAFE_REF_RE.sub("_", slug)
    return slug or "ref"


def _config_attr(name: str):
    try:
        import config as _config
    except ImportError:
        _config = None
    return getattr(_config, name, None) if _config else None


def _setting(config_name: str, env_names: tuple[str, ...], default=None):
    cfg = _config_attr(config_name)
    if cfg not in (None, ""):
        return cfg
    for env_name in env_names:
        env_value = os.getenv(env_name)
        if env_value not in (None, ""):
            return env_value
    return default


def _prosodia_base_url(default: str) -> str:
    return str(
        _setting(
            "PROSODIA_CATHOLICA_SITE_BASE_URL",
            ("PROSODIA_CATHOLICA_SITE_BASE_URL",),
            default,
        )
    ).rstrip("/")


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def highlight_snippet_html(text: str, *, start, end, cls: str, context: int = 200) -> str:
    start_i = _to_int(start)
    end_i = _to_int(end)
    raw = text or ""
    if start_i is None or end_i is None:
        return html_module.escape(raw)
    if start_i < 0 or end_i <= start_i or end_i > len(raw):
        return html_module.escape(raw)
    left = max(0, start_i - int(context))
    right = min(len(raw), end_i + int(context))
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(raw) else ""
    return (
        html_module.escape(prefix)
        + html_module.escape(raw[left:start_i])
        + f'<span class="hl {html_module.escape(cls)}">'
        + html_module.escape(raw[start_i:end_i])
        + "</span>"
        + html_module.escape(raw[end_i:right])
        + html_module.escape(suffix)
    )


def get_herodian_connection():
    """Open a connection to the Herodian overlap database."""
    host = _setting("HERODIAN_DB_HOST", ("HERODIAN_DB_HOST",), STEPHANOS_DB_HOST)
    if host in (None, ""):
        return None

    port_raw = _setting("HERODIAN_DB_PORT", ("HERODIAN_DB_PORT",), STEPHANOS_DB_PORT or 5432)
    try:
        port = int(port_raw)
    except Exception:
        port = int(STEPHANOS_DB_PORT or 5432)

    db_name = str(_setting("HERODIAN_DB_NAME", ("HERODIAN_DB_NAME",), "herodian"))
    user = str(_setting("HERODIAN_DB_USER", ("HERODIAN_DB_USER",), STEPHANOS_DB_USER or "stephanos"))
    password = _setting("HERODIAN_DB_PASSWORD", ("HERODIAN_DB_PASSWORD",), None)

    kwargs = {
        "host": host,
        "port": port,
        "database": db_name,
        "user": user,
    }
    if password not in (None, ""):
        kwargs["password"] = password

    return psycopg2.connect(**kwargs)


def fetch_herodian_overlaps_by_lemma(
    lemma_ids: list[int], *, metric_version: str = "v1", per_lemma_limit: int = 12
) -> tuple[dict[int, list[dict]], int | None]:
    """
    Fetch overlap rows from the Herodian DB keyed by Stephanos lemma id.

    Returns (overlaps_by_lemma, run_id). If the overlap DB is unavailable,
    returns ({}, None) without failing site generation.
    """
    cleaned_ids = sorted({int(i) for i in lemma_ids if i is not None and int(i) > 0})
    if not cleaned_ids:
        return {}, None

    try:
        conn = get_herodian_connection()
    except Exception:
        return {}, None
    if conn is None:
        return {}, None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM stephanos_overlap_runs
                WHERE metric_version = %s
                  AND finished_at IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (metric_version,),
            )
            run_row = cur.fetchone()
            if not run_row:
                return {}, None
            run_id = int(run_row[0])

            cur.execute(
                """
                SELECT
                  m.stephanos_lemma_id,
                  m.stephanos_meineke_id,
                  m.stephanos_headword,
                  m.char_lcs_len,
                  m.char_lcs_ratio,
                  m.word_lcs_len,
                  m.word_lcs_ratio,
                  m.herodian_char_start,
                  m.herodian_char_end,
                  m.stephanos_char_start,
                  m.stephanos_char_end,
                  l.id AS herodian_line_id,
                  l.ref AS herodian_ref,
                  l.greek_text AS herodian_greek_text
                FROM stephanos_overlap_matches m
                JOIN cathpros_lines l ON l.id = m.herodian_line_id
                WHERE m.run_id = %s
                  AND m.stephanos_lemma_id = ANY(%s)
                ORDER BY
                  m.stephanos_lemma_id,
                  m.char_lcs_ratio DESC,
                  m.word_lcs_ratio DESC,
                  m.char_lcs_len DESC
                """,
                (run_id, cleaned_ids),
            )
            rows = cur.fetchall()
    except Exception:
        return {}, None
    finally:
        conn.close()

    by_lemma: dict[int, list[dict]] = {}
    for (
        stephanos_lemma_id,
        stephanos_meineke_id,
        stephanos_headword,
        char_lcs_len,
        char_lcs_ratio,
        word_lcs_len,
        word_lcs_ratio,
        herodian_char_start,
        herodian_char_end,
        stephanos_char_start,
        stephanos_char_end,
        herodian_line_id,
        herodian_ref,
        herodian_greek_text,
    ) in rows:
        lemma_id = int(stephanos_lemma_id)
        lemma_rows = by_lemma.setdefault(lemma_id, [])
        if len(lemma_rows) >= int(per_lemma_limit):
            continue
        lemma_rows.append(
            {
                "stephanos_lemma_id": lemma_id,
                "stephanos_meineke_id": stephanos_meineke_id or "",
                "stephanos_headword": stephanos_headword or "",
                "char_lcs_len": int(char_lcs_len or 0),
                "char_lcs_ratio": float(char_lcs_ratio or 0.0),
                "word_lcs_len": int(word_lcs_len or 0),
                "word_lcs_ratio": float(word_lcs_ratio or 0.0),
                "herodian_char_start": herodian_char_start,
                "herodian_char_end": herodian_char_end,
                "stephanos_char_start": stephanos_char_start,
                "stephanos_char_end": stephanos_char_end,
                "herodian_line_id": int(herodian_line_id or 0),
                "herodian_ref": herodian_ref or "",
                "herodian_greek_text": herodian_greek_text or "",
            }
        )

    return by_lemma, run_id


def normalize_headword_for_display(headword: str) -> str:
    """Normalize OCR headword display by removing outer angle brackets.

    This is a display-layer fallback; the database should ideally already store
    normalized headwords via `assemble_lemmas.py`, but malformed OCR output can
    leak through (e.g., leading `<` with no closing `>`), which would otherwise
    break HTML rendering.
    """
    if not headword:
        return ""
    text = headword.strip()

    for open_bracket, close_bracket in (("<", ">"), ("〈", "〉"), ("《", "》"), ("«", "»")):
        match = re.fullmatch(
            rf"{re.escape(open_bracket)}\s*(.*?)\s*{re.escape(close_bracket)}",
            text,
        )
        if match:
            inner = match.group(1).strip()
            text = inner if inner else text
            break

    return text.lstrip("<〈《«").rstrip(">〉》»").strip()


def get_all_lemmas(cur):
    """Get all lemmas (translated and untranslated) from assembled_lemmas"""
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantine_reason TEXT")
    cur.execute("ALTER TABLE assembled_lemmas ADD COLUMN IF NOT EXISTS quarantined_at TIMESTAMPTZ")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_risk_flags (
            id SERIAL PRIMARY KEY,
            lemma_id INTEGER NOT NULL REFERENCES assembled_lemmas(id) ON DELETE CASCADE,
            variant_kind TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            source_document TEXT NOT NULL,
            risk_code TEXT NOT NULL,
            is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
            evidence_difference_id INTEGER,
            details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        """
        SELECT a.id, a.lemma, a.entry_number, a.type, a.greek_text, a.human_greek_text, a.confidence,
               a.translation, a.translation_json, a.translated, a.ocr_processed_at, g.name as ocr_generation_name,
               (SELECT i.ocr_model FROM images i
                JOIN lemma_images li ON li.image_id = i.id
                WHERE li.lemma_id = a.id
                ORDER BY li.position LIMIT 1) as ocr_model,
               a.meineke_id, a.billerbeck_id,
               COALESCE(
                   (SELECT json_agg(i.image_filename ORDER BY li.position)
                    FROM images i
                    JOIN lemma_images li ON li.image_id = i.id
                    WHERE li.lemma_id = a.id),
                   '[]'::json
               ) as image_filenames,
               a.word_count, a.version,
               a.corrected_greek_scan, a.corrected_english_translation,
               a.review_status, a.reviewed_by, a.reviewed_at,
               a.wikidata_place_qid, a.wikidata_place_label, a.latitude, a.longitude, a.pleiades_id,
               a.translation_prompt_version,
               COALESCE(risk_match.translation_blocked, FALSE) AS translation_blocked,
               COALESCE(risk_match.translation_block_reason, '') AS translation_block_reason
        FROM assembled_lemmas a
        LEFT JOIN ocr_generations g ON a.ocr_generation_id = g.id
        LEFT JOIN LATERAL (
            SELECT
                trf.is_blocked AS translation_blocked,
                COALESCE(trf.details_json->>'summary', '') AS translation_block_reason
            FROM translation_risk_flags trf
            WHERE trf.lemma_id = a.id
              AND trf.variant_kind = 'legacy_assembled'
              AND trf.variant_id = 'translation'
              AND trf.risk_code = 'billerbeck_likely_translation_change'
            ORDER BY trf.updated_at DESC
            LIMIT 1
        ) risk_match ON TRUE
        WHERE COALESCE(a.quarantined, FALSE) = FALSE
        ORDER BY a.id
        """
    )
    rows = cur.fetchall()

    cur.execute("SELECT to_regclass('public.translation_runs') IS NOT NULL")
    has_translation_runs = bool(cur.fetchone()[0])
    cur.execute("SELECT to_regclass('public.human_translations') IS NOT NULL")
    has_human_translations = bool(cur.fetchone()[0])
    cur.execute("SELECT to_regclass('public.lemma_source_text_versions') IS NOT NULL")
    has_source_text_versions = bool(cur.fetchone()[0])

    billerbeck_source_text_by_lemma = {}
    billerbeck_source_variant_by_lemma = {}
    if has_source_text_versions:
        cur.execute(
            """
            SELECT lemma_id, text_body, source_variant
            FROM lemma_source_text_versions
            WHERE source_document = 'billerbeck'
              AND is_current = TRUE
              AND is_public_greek = TRUE
            """
        )
        for lemma_id, text_body, source_variant in cur.fetchall():
            billerbeck_source_text_by_lemma[lemma_id] = (text_body or "")
            billerbeck_source_variant_by_lemma[lemma_id] = (source_variant or "")

    # Fetch proper nouns for all lemmas
    cur.execute("""
        SELECT lemma_id,
               json_agg(json_build_object(
                   'text_form', proper_noun,
                   'lemma_form', lemma_form,
                   'english', english_translation,
                   'type', noun_type,
                   'role', role,
                   'citation', citation,
                   'work_title', work_title
               ) ORDER BY id) as nouns
        FROM proper_nouns
        GROUP BY lemma_id
    """)
    proper_nouns_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

    # Fetch etymologies for all lemmas
    cur.execute("""
        SELECT lemma_id,
               json_agg(json_build_object(
                   'greek_text', greek_text,
                   'english', english_translation,
                   'category', category
               ) ORDER BY id) as etyms
        FROM etymologies
        GROUP BY lemma_id
    """)
    etymologies_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

    # Fetch aliases for proper nouns (grouped by proper noun english name)
    cur.execute("""
        SELECT pn.english_translation,
               json_agg(DISTINCT pna.alias ORDER BY pna.alias) as aliases
        FROM proper_nouns pn
        JOIN proper_noun_aliases pna ON pna.proper_noun_id = pn.id
        WHERE pn.english_translation IS NOT NULL
        GROUP BY pn.english_translation
    """)
    aliases_by_name = {row[0]: row[1] for row in cur.fetchall()}

    # Fetch phrase-level commentary entries (optional; table may not exist yet)
    commentary_by_lemma = {}
    cur.execute("SELECT to_regclass('public.lemma_commentary_entries') IS NOT NULL")
    has_commentary_entries = bool(cur.fetchone()[0])
    if has_commentary_entries:
        cur.execute(
            """
            SELECT
                lemma_id,
                json_agg(json_build_object(
                    'id', id,
                    'phrase_text', phrase_text,
                    'commentary_text', commentary_text,
                    'created_by', COALESCE(created_by, ''),
                    'created_at', created_at
                ) ORDER BY id) AS comments
            FROM lemma_commentary_entries
            GROUP BY lemma_id
            """
        )
        commentary_by_lemma = {row[0]: row[1] for row in cur.fetchall()}

    all_lemmas = []
    for lemma_id, lemma, entry_number, lemma_type, greek_text, human_greek_text, confidence, translation_col, translation_json, translated, ocr_processed_at, ocr_generation_name, ocr_model, meineke_id, billerbeck_id, image_filenames, word_count, version, corrected_greek_scan, corrected_english_translation, review_status, reviewed_by, reviewed_at, wikidata_place_qid, wikidata_place_label, latitude, longitude, pleiades_id, translation_prompt_version, translation_blocked, translation_block_reason in rows:
        # Public Greek preference: current public Billerbeck source-text version (if available) -> assembled_lemmas lane.
        greek_source_variant = ""
        greek_source_origin = ""
        billerbeck_candidate = (billerbeck_source_text_by_lemma.get(lemma_id) or "").strip()
        if billerbeck_candidate:
            greek = billerbeck_candidate
            greek_source = "billerbeck"
            greek_source_variant = (billerbeck_source_variant_by_lemma.get(lemma_id) or "").strip()
            greek_source_origin = "lemma_source_text_versions"
        else:
            greek = (corrected_greek_scan or human_greek_text or greek_text or "").strip()
            greek_source = "billerbeck"
            if (corrected_greek_scan or "").strip() or (human_greek_text or "").strip():
                greek_source_variant = "manual"
            elif (greek_text or "").strip():
                greek_source_variant = "ocr"
            else:
                greek_source_variant = ""
            greek_source_origin = "assembled_lemmas"

        # Use normalized translation column, fall back to parsing translation_json for legacy data
        translation = translation_col or ""
        english_translation = translation_col or ""
        if not translation and translation_json:
            try:
                data = json.loads(translation_json)
                if isinstance(data, dict):
                    translation = data.get("translation", "")
                    english_translation = data.get("english_translation", translation)
            except json.JSONDecodeError:
                pass

        # Prefer corrected English translation
        if corrected_english_translation:
            english_translation = corrected_english_translation
            translation = corrected_english_translation

        selected_translation_blocked = bool(translation_blocked)
        selected_translation_block_reason = (translation_block_reason or "").strip()

        presented = canonical_variants.select_presented_variants(cur, lemma_id=lemma_id, ux_mode="multi")
        presented_translations = []
        for v in presented:
            presented_translations.append(
                {
                    "kind": v.get("kind", ""),
                    "id": str(v.get("id", "") or ""),
                    "is_primary": bool(v.get("is_primary", False)),
                    "status": v.get("status", ""),
                    "source_text_version_id": str(v.get("source_text_version_id", "") or ""),
                    "translation_text": (v.get("translation_text", "") or "").strip(),
                }
            )

        selected_kind = ""
        selected_id = ""
        selected_translation_text = ""
        if presented_translations:
            selected_translation_text = presented_translations[0].get("translation_text", "")
            selected_kind = presented_translations[0].get("kind", "")
            selected_id = presented_translations[0].get("id", "")
            selected_translation_blocked = False
            selected_translation_block_reason = ""
        else:
            selected_translation_text = ""
            selected_translation_blocked = bool(translation_blocked)
            selected_translation_block_reason = (translation_block_reason or "").strip()

        translation = selected_translation_text
        english_translation = selected_translation_text

        # Parse image filenames (psycopg2 auto-deserializes JSON)
        if isinstance(image_filenames, list):
            images = image_filenames
        elif image_filenames:
            try:
                images = json.loads(image_filenames)
            except (json.JSONDecodeError, TypeError):
                images = []
        else:
            images = []

        lemma_data = {
            "lemma_id": lemma_id,
            "entry_number": entry_number or "",
            "lemma": normalize_headword_for_display(lemma or ""),
            "type": lemma_type or "",
            "greek_text": greek,
            "english_translation": english_translation,
            "translation": translation,
            "presented_translations": presented_translations,
            "selected_translation_variant_kind": selected_kind,
            "selected_translation_variant_id": selected_id,
            "confidence": confidence or "normal",
            "ocr_processed_at": ocr_processed_at,
            "ocr_generation_name": ocr_generation_name or "unknown",
            "ocr_model": ocr_model,
            "meineke_id": meineke_id or "",
            "billerbeck_id": billerbeck_id or "",
            "translated": bool(translated),
            "image_filenames": images,
            "word_count": word_count,
            "proper_nouns": proper_nouns_by_lemma.get(lemma_id, []),
            "etymologies": etymologies_by_lemma.get(lemma_id, []),
            "aliases_by_name": aliases_by_name,
            "commentary_entries": commentary_by_lemma.get(lemma_id, []),
            "version": version or "epitome",
            "review_status": review_status or "not_reviewed",
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "has_corrections": bool(corrected_greek_scan or corrected_english_translation),
            "wikidata_place_qid": wikidata_place_qid,
            "wikidata_place_label": wikidata_place_label,
            "latitude": latitude,
            "longitude": longitude,
            "pleiades_id": pleiades_id,
            "translation_prompt_version": translation_prompt_version,
            "translation_blocked": bool(selected_translation_blocked),
            "translation_block_reason": selected_translation_block_reason or "",
            "greek_source": greek_source,
            "greek_source_variant": greek_source_variant,
            "greek_source_origin": greek_source_origin,
        }
        lemma_data["letter_slug"] = get_initial_slug(lemma_data["lemma"])
        all_lemmas.append(lemma_data)

    return all_lemmas


def highlight_proper_nouns_in_translation(translation, proper_nouns, aliases_by_name):
    """
    Wrap proper noun names in the translation with spans that show aliases on hover.

    Args:
        translation: The English translation text
        proper_nouns: List of proper noun dicts with 'english' key
        aliases_by_name: Dict mapping english names to list of aliases

    Returns:
        HTML string with proper nouns wrapped in tooltip spans
    """
    if not translation or not proper_nouns:
        return translation

    # Build a list of (name, aliases) to find in the text
    names_to_find = []
    for noun in proper_nouns:
        english = noun.get('english', '')
        if english and english in aliases_by_name:
            aliases = aliases_by_name[english]
            if aliases:
                names_to_find.append((english, aliases))

    if not names_to_find:
        return translation

    # Sort by length (longest first) to avoid partial matches
    names_to_find.sort(key=lambda x: len(x[0]), reverse=True)

    # Track which positions have been replaced to avoid overlaps
    result = translation
    for name, aliases in names_to_find:
        # Escape for regex
        pattern = r'\b' + re.escape(name) + r'\b'
        # Limit aliases shown to first 5
        alias_list = aliases[:5]
        if len(aliases) > 5:
            alias_list.append(f"...+{len(aliases)-5} more")
        aliases_str = html_module.escape(', '.join(alias_list))
        replacement = f'<span class="proper-noun-highlight" data-aliases="{aliases_str}">{name}</span>'
        result = re.sub(pattern, replacement, result, count=1)

    return result


def render_lemma_cards(lemmas):
    """Render HTML cards for a list of lemmas"""
    cards_html = []
    for lemma in lemmas:
        confidence_class = "low-confidence" if lemma.get('confidence') == 'low' else ""
        confidence_badge = '<span class="confidence-badge">Low Confidence</span>' if lemma.get('confidence') == 'low' else ""
        version = lemma.get('version', 'epitome')
        if version == 'parisinus':
            version_class = "parisinus-version"
            version_badge = '<span class="version-badge">Parisinus</span>'
        elif version == 'synthetic':
            version_class = "synthetic-version"
            version_badge = '<span class="version-badge synthetic-badge">Synthetic</span>'
        else:
            version_class = ""
            version_badge = ""

        is_blocked = bool(lemma.get("translation_blocked"))
        presented = lemma.get("presented_translations") or []
        if not isinstance(presented, list):
            presented = []

        def render_translation_text(text: str) -> str:
            return highlight_proper_nouns_in_translation(
                text or "",
                lemma.get("proper_nouns", []),
                lemma.get("aliases_by_name", {}),
            )

        if is_blocked:
            translation = '<span class="pending-translation">Translation pending</span>'
        elif not presented:
            translation = '<span class="pending-translation">Translation pending</span>'
        else:
            primary_text = (presented[0].get("translation_text") if isinstance(presented[0], dict) else "") or ""
            translation = render_translation_text(primary_text)

            if len(presented) > 1:
                extra_rows = []
                for v in presented[1:]:
                    if not isinstance(v, dict):
                        continue
                    label = f"{v.get('kind', '')} {v.get('id', '')}".strip()
                    if v.get("is_primary"):
                        label = (label + " (primary)").strip()
                    text = (v.get("translation_text") or "").strip()
                    if not text:
                        continue
                    extra_rows.append(
                        f"<div class='translation-variant'>"
                        f"<div class='translation-variant-label'>{html_module.escape(label)}</div>"
                        f"<div class='translation-variant-text'>{render_translation_text(text)}</div>"
                        f"</div>"
                    )

                if extra_rows:
                    translation += (
                        f"<details class='translation-variants'>"
                        f"<summary>Other canonical translations ({len(extra_rows)})</summary>"
                        f"{''.join(extra_rows)}"
                        f"</details>"
                    )

        # Phrase-level commentary (optional)
        commentary_html = ""
        commentary_entries = lemma.get("commentary_entries") or []
        if isinstance(commentary_entries, str):
            try:
                commentary_entries = json.loads(commentary_entries)
            except (json.JSONDecodeError, TypeError):
                commentary_entries = []
        if isinstance(commentary_entries, list) and commentary_entries:
            rows = []
            for entry in commentary_entries:
                if not isinstance(entry, dict):
                    continue
                phrase = html_module.escape((entry.get("phrase_text") or "").strip())
                note = html_module.escape((entry.get("commentary_text") or "").strip())
                if not phrase and not note:
                    continue
                if phrase:
                    rows.append(
                        f"<div class='commentary-entry'>"
                        f"<div class='commentary-phrase'>{phrase}</div>"
                        f"<div class='commentary-text'>{note}</div>"
                        f"</div>"
                    )
                else:
                    rows.append(
                        f"<div class='commentary-entry'>"
                        f"<div class='commentary-text'>{note}</div>"
                        f"</div>"
                    )
            if rows:
                commentary_html = (
                    f"<details class='commentary'>"
                    f"<summary>Commentary ({len(rows)})</summary>"
                    f"{''.join(rows)}"
                    f"</details>"
                )
        meta_lines = []
        if lemma.get("entry_number"):
            meta_lines.append(f"Entry #{lemma['entry_number']}")
        if lemma.get("greek_source"):
            greek_meta = f"{lemma.get('greek_source')}"
            if lemma.get("greek_source_origin") == "lemma_source_text_versions":
                greek_meta += " (current)"
            if lemma.get("greek_source_variant"):
                greek_meta += f" · {lemma.get('greek_source_variant')}"
            meta_lines.append(f"Greek: {greek_meta}")
        if lemma.get("meineke_id") or lemma.get("billerbeck_id"):
            meta_lines.append(
                f"Meineke: {lemma.get('meineke_id') or '-'} | Billerbeck: {lemma.get('billerbeck_id') or '-'}"
            )
        if lemma.get("ocr_generation_name") or lemma.get("ocr_processed_at"):
            when = ""
            if lemma.get("ocr_processed_at"):
                ts = lemma["ocr_processed_at"]
                if isinstance(ts, str):
                    when = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
                else:
                    when = ts.strftime("%Y-%m-%d")
            ocr_info = f"{lemma.get('ocr_generation_name', 'unknown')}"
            if lemma.get('ocr_model'):
                ocr_info += f" ({lemma['ocr_model']})"
            if when:
                ocr_info += f" on {when}"
            meta_lines.append(f"OCR: {ocr_info}")
        # Add word count
        if lemma.get("word_count") is not None:
            meta_lines.append(f"Word count: {lemma['word_count']}")

        # Add translation prompt version (only for AI translations, not human)
        if (
            lemma.get("translation_prompt_version")
            and lemma.get("translated")
            and lemma.get("selected_translation_variant_kind") == "legacy_assembled"
        ):
            meta_lines.append(f"AI prompt: v{lemma['translation_prompt_version']}")
        if is_blocked:
            block_reason = lemma.get("translation_block_reason") or "Likely translation-affecting Meineke/Billerbeck difference"
            meta_lines.append(f"Translation blocked: {block_reason}")

        # Add proper nouns (separated by role)
        if lemma.get("proper_nouns"):
            sources = [n for n in lemma["proper_nouns"] if n.get('role') == 'source']
            entities = [n for n in lemma["proper_nouns"] if n.get('role') == 'entity']

            # Display sources (authors/citations)
            if sources:
                source_list = []
                for noun in sources:
                    noun_str = citation_format.format_source_reference(
                        lemma_form=noun.get("lemma_form"),
                        english=noun.get("english"),
                        work_title=noun.get("work_title"),
                        citation=noun.get("citation"),
                    )
                    source_list.append(noun_str)
                meta_lines.append(f"Sources: {', '.join(source_list)}")

            # Display entities (people/places in the story)
            if entities:
                entity_list = []
                for noun in entities:
                    noun_str = f"{noun['lemma_form']}"
                    if noun.get('english'):
                        noun_str += f" ({noun['english']})"
                    if noun.get('type'):
                        noun_str += f" [{noun['type']}]"
                    entity_list.append(noun_str)
                meta_lines.append(f"Entities: {', '.join(entity_list)}")

        # Add etymologies
        if lemma.get("etymologies"):
            etym_list = []
            for etym in lemma["etymologies"]:
                cat = etym.get('category', '').replace('_', ' ').title()
                etym_str = cat
                if etym.get('english'):
                    etym_str += f": {etym['english']}"
                etym_list.append(etym_str)
            if etym_list:
                meta_lines.append(f"Etymologies: {'; '.join(etym_list)}")

        # Add Wikidata place link and coordinates
        if lemma.get("wikidata_place_qid"):
            place_parts = []
            qid = lemma["wikidata_place_qid"]
            label = lemma.get("wikidata_place_label", "")
            place_parts.append(f'<a href="https://www.wikidata.org/wiki/{qid}" target="_blank">{label or qid}</a>')
            if lemma.get("latitude") and lemma.get("longitude"):
                lat, lon = lemma["latitude"], lemma["longitude"]
                place_parts.append(f'📍 <a href="map.html" title="{lat:.4f}, {lon:.4f}">Map</a>')
            if lemma.get("pleiades_id"):
                place_parts.append(f'<a href="https://pleiades.stoa.org/places/{lemma["pleiades_id"]}" target="_blank">Pleiades</a>')
            meta_lines.append(f"Place: {' | '.join(place_parts)}")

        # Add page image links (to HTML wrappers)
        if lemma.get("image_filenames"):
            image_links = []
            for img in lemma["image_filenames"]:
                # Link to HTML wrapper page instead of raw image
                html_page = img.replace('.jpg', '.html').replace('.png', '.html')
                image_links.append(f'<a href="protected/{html_page}" target="_blank">{img}</a>')
            meta_lines.append(f"Source: {', '.join(image_links)}")
        # Add edit link to review system
        meta_lines.append(f'<a href="/cgi-bin/review.cgi?id={lemma["lemma_id"]}">Edit</a>')
        meta_html = "<br>".join(meta_lines)
        # Status badges (populated by JavaScript)
        status_badges = f'''<span class="status-badges" data-lemma-id="{lemma['lemma_id']}">
            <span class="status-badge status-ocr" title="OCR Checked">OCR ✓</span>
            <span class="status-badge status-initial" title="Initial Translation">Trans ✓</span>
            <span class="status-badge status-confirmed" title="Translation Confirmed">Confirmed ✓</span>
        </span>'''

        cards_html.append(
            f"""
            <div class="lemma-card {version_class}" id="lemma-{lemma['lemma_id']}" data-lemma-id="{lemma['lemma_id']}">
                <div class="lemma-header">
                    <div>
                        <div class="lemma-title">{lemma['lemma']}{confidence_badge}{version_badge}{status_badges}</div>
                        {f'<span class="lemma-type">{lemma["type"]}</span>' if lemma['type'] else ''}
                    </div>
                    <div class="lemma-meta">
                        {meta_html}
                    </div>
                </div>
                {f'<div class="greek-text {confidence_class}">{lemma["greek_text"]}</div>' if lemma['greek_text'] else ''}
                <div class="translation">{translation}</div>
                {commentary_html}
            </div>
            """
        )
    return "\n".join(cards_html)


def render_letter_headword_list(lemmas):
    """Render compact headword links for a letter page."""
    if not lemmas:
        return '<div class="no-results">No lemmas processed for this letter yet.</div>'

    items = []
    for lemma in lemmas:
        lemma_id = int(lemma.get("lemma_id") or 0)
        title = html_module.escape(lemma.get("lemma") or f"Lemma {lemma_id}")
        headword_href = headword_page_filename(lemma_id)
        meta_parts = []
        if lemma.get("entry_number"):
            meta_parts.append(f"Entry {html_module.escape(str(lemma.get('entry_number')))}")
        if lemma.get("type"):
            meta_parts.append(html_module.escape(str(lemma.get("type"))))
        if lemma.get("meineke_id"):
            meta_parts.append(f"Meineke {html_module.escape(str(lemma.get('meineke_id')))}")
        meta_line = " · ".join(meta_parts)
        meta_html = f'<div class="headword-meta">{meta_line}</div>' if meta_line else ""
        items.append(
            f"""
            <li class="headword-item">
                <a class="headword-link" href="{headword_href}">{title}</a>
                {meta_html}
            </li>
            """.strip()
        )

    return f'<ol class="headword-list">{"".join(items)}</ol>'


def render_herodian_overlap_rows(lemma: dict, overlaps: list[dict], overlap_run_id: int | None) -> str:
    """Render Herodian overlap rows for a single lemma page."""
    if not overlaps:
        if overlap_run_id:
            return "<div class='overlap-empty'>No significant Herodian overlaps were found for this headword in the latest run.</div>"
        return "<div class='overlap-empty'>Herodian overlap data is not available in this environment.</div>"

    stephanos_text = lemma.get("greek_text") or ""
    prosodia_base = _prosodia_base_url("https://prosodia-catholica.symmachus.org")
    rows = []
    for idx, ov in enumerate(overlaps):
        color_cls = OVERLAP_COLOR_CLASSES[idx % len(OVERLAP_COLOR_CLASSES)]
        ref = (ov.get("herodian_ref") or "").strip()
        ref_slug = ref_to_slug(ref)
        ref_url = f"{prosodia_base}/passages/{ref_slug}.html" if ref else prosodia_base
        char_pct = f"{float(ov.get('char_lcs_ratio') or 0.0) * 100.0:.1f}%"
        word_pct = f"{float(ov.get('word_lcs_ratio') or 0.0) * 100.0:.1f}%"
        herodian_snippet = highlight_snippet_html(
            ov.get("herodian_greek_text") or "",
            start=ov.get("herodian_char_start"),
            end=ov.get("herodian_char_end"),
            cls=color_cls,
            context=220,
        )
        stephanos_snippet = highlight_snippet_html(
            stephanos_text,
            start=ov.get("stephanos_char_start"),
            end=ov.get("stephanos_char_end"),
            cls=color_cls,
            context=220,
        )
        rows.append(
            f"""
            <div class="overlap-row">
                <div class="overlap-row-head">
                    <div>
                        <span class="swatch {color_cls}"></span>
                        <a href="{html_module.escape(ref_url)}" target="_blank" rel="noopener">Herodian {html_module.escape(ref or str(ov.get("herodian_line_id") or ""))}</a>
                    </div>
                    <div class="overlap-metrics">char LCS {int(ov.get('char_lcs_len') or 0)} ({char_pct}) · word LCS {int(ov.get('word_lcs_len') or 0)} ({word_pct})</div>
                </div>
                <div class="overlap-grid">
                    <div>
                        <div class="overlap-col-title">Stephanos</div>
                        <pre class="greek overlap-snippet" lang="el">{stephanos_snippet}</pre>
                    </div>
                    <div>
                        <div class="overlap-col-title">Herodian</div>
                        <pre class="greek overlap-snippet" lang="el">{herodian_snippet}</pre>
                    </div>
                </div>
            </div>
            """.strip()
        )
    return "\n".join(rows)


def generate_legacy_anchor_redirect_script():
    """Redirect old #lemma-ID anchor links to canonical headword pages."""
    return """
<script>
(function() {
    const hash = window.location.hash || '';
    const m = hash.match(/^#lemma-(\\d+)$/);
    if (!m) return;
    window.location.replace(`headword_${m[1]}.html`);
})();
</script>
"""


def common_styles():
    """Shared CSS for index and letter pages."""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #3f51b5 0%, #0d47a1 100%);
            color: white;
            padding: 32px 20px;
            text-align: center;
        }
        .header h1 {
            font-size: 2.2em;
            margin-bottom: 8px;
        }
        .header p {
            font-size: 1.05em;
            opacity: 0.9;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .nav-links {
            text-align: right;
            margin: 12px 0;
        }
        .nav-links a {
            color: #0d47a1;
            text-decoration: none;
            font-weight: 600;
            margin-left: 12px;
            white-space: nowrap;
        }
        .nav-links a:hover {
            text-decoration: underline;
        }
        .letter-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin: 24px 0;
        }
        .letter-card {
            background: white;
            padding: 16px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
            text-decoration: none;
            color: #1a237e;
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .letter-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }
        .letter-char {
            font-size: 1.8em;
            font-weight: 700;
        }
        .letter-name {
            font-size: 0.95em;
            color: #555;
            margin-top: 4px;
        }
        .letter-count {
            margin-top: 6px;
            font-weight: 600;
            color: #0d47a1;
        }
        .headword-list {
            margin-top: 18px;
            padding-left: 18px;
        }
        .headword-item {
            background: #fff;
            border: 1px solid #e8e8e8;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            margin: 8px 0;
            padding: 10px 14px;
        }
        .headword-link {
            color: #1a237e;
            font-weight: 700;
            text-decoration: none;
        }
        .headword-link:hover {
            text-decoration: underline;
        }
        .headword-meta {
            color: #666;
            font-size: 0.9em;
            margin-top: 4px;
        }
        .lemma-grid {
            display: grid;
            gap: 16px;
            margin-top: 20px;
        }
        .lemma-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .lemma-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }
        .lemma-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 12px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 8px;
        }
        .lemma-title {
            font-size: 1.6em;
            font-weight: 700;
            color: #1a237e;
        }
        .lemma-type {
            display: inline-block;
            padding: 4px 10px;
            background: #3949ab;
            color: white;
            border-radius: 4px;
            font-size: 0.85em;
            margin-top: 4px;
        }
        .lemma-meta {
            text-align: right;
            font-size: 0.9em;
            color: #666;
        }
        .greek-text {
            font-family: 'Times New Roman', serif;
            font-size: 1.05em;
            line-height: 1.8;
            color: #3a3a3a;
            margin: 12px 0;
            padding: 12px;
            background: #fafafa;
            border-left: 4px solid #3949ab;
            border-radius: 4px;
            /* Preserve line breaks for quoted verse/poetry (and any manual lineation). */
            white-space: pre-wrap;
        }
        .low-confidence {
            border-left-color: #ff9800;
        }
        .confidence-badge {
            display: inline-block;
            padding: 3px 8px;
            background: #ff9800;
            color: white;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 10px;
        }
        .version-badge {
            display: inline-block;
            padding: 3px 8px;
            background: #7b1fa2;
            color: white;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 10px;
        }
        .parisinus-version {
            background: #f3e5f5;
            border: 2px solid #9c27b0;
        }
        .parisinus-version:hover {
            box-shadow: 0 4px 16px rgba(156, 39, 176, 0.2);
        }
        .synthetic-version {
            background: #fff8e1;
            border: 2px solid #ff8f00;
        }
        .synthetic-version:hover {
            box-shadow: 0 4px 16px rgba(255, 143, 0, 0.2);
        }
        .synthetic-badge {
            background: #ff8f00 !important;
        }
        /* Live status badges (updated via JavaScript) */
        .status-badges {
            display: inline-flex;
            gap: 6px;
            margin-left: 10px;
        }
        .status-badge {
            display: none;  /* Hidden by default, shown when status is true */
            padding: 3px 8px;
            color: white;
            border-radius: 3px;
            font-size: 0.7em;
            font-weight: 600;
        }
        .status-badge.visible {
            display: inline-block;
        }
        .status-ocr {
            background: #8e44ad;
        }
        .status-initial {
            background: #e67e22;
        }
        .status-confirmed {
            background: #27ae60;
        }
        .status-loading {
            color: #999;
            font-size: 0.75em;
            margin-left: 10px;
        }
	        .translation {
	            font-size: 1em;
	            color: #2c2c2c;
	            line-height: 1.6;
	            margin: 10px 0;
                /* Preserve line breaks for verse translations. */
                white-space: pre-wrap;
	        }
	        .translation-variants {
	            margin-top: 10px;
	            padding: 10px 12px;
	            background: #f7f9ff;
	            border: 1px solid #e0e4ff;
	            border-radius: 6px;
	        }
	        .translation-variants summary {
	            cursor: pointer;
	            font-weight: 600;
	            color: #1a237e;
	            outline: none;
	        }
	        .translation-variants summary::-webkit-details-marker {
	            color: #1a237e;
	        }
	        .translation-variant {
	            margin-top: 10px;
	            padding-top: 10px;
	            border-top: 1px solid rgba(26, 35, 126, 0.12);
	        }
	        .translation-variant-label {
	            font-size: 0.85em;
	            color: #555;
	            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
	        }
        .translation-variant-text {
            margin-top: 6px;
        }
        .commentary {
            margin-top: 10px;
            padding: 10px 12px;
            background: #fffdf5;
            border: 1px solid #f0e6c8;
            border-radius: 6px;
        }
        .commentary summary {
            cursor: pointer;
            font-weight: 600;
            color: #6d4c00;
            outline: none;
        }
        .commentary-entry {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid rgba(109, 76, 0, 0.12);
        }
        .commentary-phrase {
            font-family: 'Times New Roman', serif;
            color: #3a3a3a;
            margin-bottom: 4px;
        }
        .commentary-text {
            color: #2c2c2c;
            line-height: 1.55;
        }
        .overlap-section {
            margin-top: 26px;
        }
        .overlap-row {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            margin-top: 12px;
            padding: 12px;
        }
        .overlap-row-head {
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: space-between;
        }
        .overlap-metrics {
            color: #555;
            font-size: 0.9em;
        }
        .overlap-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: 1fr;
            margin-top: 10px;
        }
        @media (min-width: 980px) {
            .overlap-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        .overlap-col-title {
            color: #666;
            font-size: 0.85em;
            font-weight: 700;
            margin-bottom: 4px;
            text-transform: uppercase;
        }
        .overlap-snippet {
            border-left: 4px solid #3949ab;
            border-radius: 4px;
            font-size: 1.0em;
            line-height: 1.7;
            margin: 0;
            padding: 10px;
            white-space: pre-wrap;
        }
        .overlap-empty {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            color: #666;
            margin-top: 12px;
            padding: 12px;
        }
        .hl {
            border-radius: 4px;
            padding: 0 2px;
        }
        .swatch {
            border: 1px solid rgba(26,35,126,.12);
            border-radius: 4px;
            display: inline-block;
            height: 12px;
            margin-right: 8px;
            vertical-align: -2px;
            width: 12px;
        }
        .c0 { background: rgba(255,214,10,.24); }
        .c1 { background: rgba(122,162,255,.24); }
        .c2 { background: rgba(100,231,173,.22); }
        .c3 { background: rgba(255,143,171,.22); }
        .c4 { background: rgba(255,170,0,.20); }
        .c5 { background: rgba(0,210,255,.18); }
        .c6 { background: rgba(186,104,200,.20); }
        .c7 { background: rgba(239,83,80,.18); }
        .c8 { background: rgba(149,117,205,.20); }
        .c9 { background: rgba(76,175,80,.18); }
        .proper-noun-highlight {
            border-bottom: 1px dotted #3f51b5;
            cursor: help;
            position: relative;
        }
        .proper-noun-highlight:hover {
            background: #e8eaf6;
        }
        .proper-noun-highlight:hover::after {
            content: "Also: " attr(data-aliases);
            position: absolute;
            bottom: 100%;
            left: 0;
            background: #333;
            color: white;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 0.85em;
            white-space: nowrap;
            z-index: 100;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .footer {
            text-align: center;
            padding: 30px 20px;
            color: #666;
            font-size: 0.9em;
            margin-top: 40px;
            border-top: 1px solid #ddd;
        }
        .no-results {
            text-align: center;
            padding: 40px 20px;
            color: #999;
            font-size: 1.1em;
        }
        .breadcrumb {
            margin: 12px 0 18px;
            font-size: 0.95em;
            color: #0d47a1;
        }
        .breadcrumb a {
            color: #0d47a1;
            text-decoration: none;
        }
        .breadcrumb a:hover {
            text-decoration: underline;
        }
    """


def generate_index_html(letter_counts, stats):
    """Generate main index page with letter selector"""

    letters_html = []
    for char, name, slug in GREEK_LETTERS:
        count = letter_counts.get(slug, 0)
        letters_html.append(
            f"""
            <a class="letter-card" href="letter_{slug}.html">
                <div class="letter-char">{char}</div>
                <div class="letter-name">{name}</div>
                <div class="letter-count">{count} lemmas</div>
            </a>
            """
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos of Byzantium - Ethnika Reference</title>
    <style>
    {common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>Stephanos of Byzantium</h1>
        <p>Ethnika - Geographical Lexicon (Billerbeck 2006 Edition)</p>
    </div>

    <div class="container">
	        <div class="nav-links">
	            <a href="sources.html">Ancient Sources</a>
	            <a href="works.html">Works Cited</a>
	            <a href="fgrhist.html">FGrHist Index</a>
	            <a href="entities.html">People &amp; Deities</a>
	            <a href="peoples.html">Ethnic Groups</a>
	            <a href="aliases.html">Aliases</a>
	            <a href="map.html">Places Map</a>
		            <a href="statistics.html">Statistics</a>
		            <a href="protected/meineke_comparison.html">Meineke vs Billerbeck</a>
		            <a href="protected/meineke_difference_analysis.html">Difference Analysis</a>
		            <a href="protected/clustering.html">Clustering</a>
		            <a href="progress.html">Processing Progress</a>
		            <a href="pipeline.html">Pipeline Status</a>
		            <a href="protected/">Page Scans</a>
		            <a href="cgi-bin/review.cgi">Human Review</a>
            <a href="downloads.html">Downloads</a>
            <a href="stephanos_ethnika_translations.pdf">PDF Book</a>
        </div>
        <div class="stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0;">
            <div class="stat-card">
                <div class="stat-value">{stats['total_lemmas']:,}</div>
                <div class="stat-label">Total Lemmas</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['translated_lemmas']:,}</div>
                <div class="stat-label">Translated Lemmas</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['processed_images']}</div>
                <div class="stat-label">Pages OCR’d</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['total_images']}</div>
                <div class="stat-label">Total Pages</div>
            </div>
        </div>

        <div class="letter-grid">
            {''.join(letters_html)}
        </div>

        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p>Select a letter to browse headwords, then open canonical pages for each entry.</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_status_script(slug):
    """Generate JavaScript for fetching and displaying live review status."""
    return f"""
<script>
(function() {{
    const letter = '{slug}';
    const statusUrl = '/public-cgi/status.cgi?letter=' + letter;

    // Fetch status on page load
    fetch(statusUrl)
        .then(response => response.json())
        .then(data => {{
            if (data.error) {{
                console.warn('Status API error:', data.error);
                return;
            }}

            // Update badges for each lemma
            const statuses = data.statuses || {{}};
            for (const [lemmaId, status] of Object.entries(statuses)) {{
                const badgeContainer = document.querySelector(`.status-badges[data-lemma-id="${{lemmaId}}"]`);
                if (!badgeContainer) continue;

                // Show/hide badges based on status
                const ocrBadge = badgeContainer.querySelector('.status-ocr');
                const initialBadge = badgeContainer.querySelector('.status-initial');
                const confirmedBadge = badgeContainer.querySelector('.status-confirmed');

                if (status.ocr_checked && ocrBadge) {{
                    ocrBadge.classList.add('visible');
                    if (status.ocr_checked_by) {{
                        ocrBadge.title = 'OCR Checked by ' + status.ocr_checked_by;
                    }}
                }}
                if (status.initial_translation && initialBadge) {{
                    initialBadge.classList.add('visible');
                    if (status.initial_translation_by) {{
                        initialBadge.title = 'Initial translation by ' + status.initial_translation_by;
                    }}
                }}
                if (status.translation_confirmed && confirmedBadge) {{
                    confirmedBadge.classList.add('visible');
                    if (status.translation_confirmed_by) {{
                        confirmedBadge.title = 'Translation confirmed by ' + status.translation_confirmed_by;
                    }}
                }}
            }}

            // Log timing for debugging
            console.log(`Status loaded for ${{letter}}: ${{data.review_count}}/${{data.lemma_count}} reviewed in ${{data.timing_ms.toFixed(1)}}ms`);
        }})
        .catch(err => {{
            console.warn('Failed to fetch status:', err);
        }});
}})();
</script>
"""


def generate_letter_page(letter_char, letter_name, slug, lemmas):
    """Generate a per-letter page with just headword links."""
    body = f"""
        <div class="breadcrumb"><a href="index.html">All Letters</a> / {letter_char} {letter_name}</div>
        <h2>{letter_char} {letter_name}</h2>
        <p class="note">Select a headword to open its canonical page.</p>
        {render_letter_headword_list(lemmas)}
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{letter_char} {letter_name} - Stephanos Ethnika</title>
    <style>
    {common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>{letter_char} {letter_name}</h1>
        <p>Stephanos of Byzantium - Ethnika</p>
    </div>
    <div class="container">
	        <div class="nav-links">
	            <a href="index.html">All Letters</a>
	            <a href="sources.html">Ancient Sources</a>
	            <a href="works.html">Works Cited</a>
	            <a href="fgrhist.html">FGrHist Index</a>
	            <a href="entities.html">People &amp; Deities</a>
	            <a href="peoples.html">Ethnic Groups</a>
	            <a href="aliases.html">Aliases</a>
	            <a href="map.html">Places Map</a>
		            <a href="statistics.html">Statistics</a>
		            <a href="protected/meineke_comparison.html">Meineke vs Billerbeck</a>
		            <a href="protected/meineke_difference_analysis.html">Difference Analysis</a>
		            <a href="protected/clustering.html">Clustering</a>
		            <a href="cgi-bin/review.cgi">Human Review</a>
		            <a href="downloads.html">Downloads</a>
		            <a href="stephanos_ethnika_translations.pdf">PDF Book</a>
	        </div>
        {body}
        <div class="footer">
            <p>Legacy links of the form <code>letter_*.html#lemma-ID</code> automatically redirect to canonical headword pages.</p>
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
    {generate_legacy_anchor_redirect_script()}
</body>
    </html>
    """
    return html


def generate_headword_page(lemma: dict, overlaps: list[dict], overlap_run_id: int | None):
    """Generate a canonical per-headword page."""
    letter_slug = lemma.get("letter_slug") or get_initial_slug(lemma.get("lemma") or "")
    letter_char, letter_name = LETTER_META_BY_SLUG.get(letter_slug, ("?", "Other"))
    lemma_title = html_module.escape(lemma.get("lemma") or f"Lemma {lemma.get('lemma_id')}")
    overlaps_html = render_herodian_overlap_rows(lemma, overlaps, overlap_run_id)

    body = f"""
        <div class="breadcrumb">
            <a href="index.html">All Letters</a>
            / <a href="letter_{html_module.escape(letter_slug)}.html">{letter_char} {letter_name}</a>
            / {lemma_title}
        </div>
        <div class="lemma-grid">
            {render_lemma_cards([lemma])}
        </div>
        <div class="overlap-section">
            <h2>Herodian overlaps</h2>
            <p class="note">Stephanos excerpt (left) is aligned with matched Herodian passages (right). Colors indicate corresponding overlap spans.</p>
            {overlaps_html}
        </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lemma_title} - Stephanos Ethnika</title>
    <style>
    {common_styles()}
    </style>
</head>
<body>
    <div class="header">
        <h1>{lemma_title}</h1>
        <p>Stephanos of Byzantium - Ethnika</p>
    </div>
    <div class="container">
	        <div class="nav-links">
	            <a href="index.html">All Letters</a>
	            <a href="letter_{html_module.escape(letter_slug)}.html">{letter_char} {letter_name}</a>
	            <a href="sources.html">Ancient Sources</a>
	            <a href="works.html">Works Cited</a>
	            <a href="fgrhist.html">FGrHist Index</a>
	            <a href="entities.html">People &amp; Deities</a>
	            <a href="peoples.html">Ethnic Groups</a>
	            <a href="aliases.html">Aliases</a>
	            <a href="map.html">Places Map</a>
	            <a href="statistics.html">Statistics</a>
	            <a href="protected/meineke_comparison.html">Meineke vs Billerbeck</a>
	            <a href="protected/meineke_difference_analysis.html">Difference Analysis</a>
	            <a href="protected/clustering.html">Clustering</a>
	            <a href="cgi-bin/review.cgi">Human Review</a>
	            <a href="downloads.html">Downloads</a>
	            <a href="stephanos_ethnika_translations.pdf">PDF Book</a>
	        </div>
        {body}
        <div class="footer">
            <p>Canonical URL: <code>{html_module.escape(headword_page_filename(int(lemma.get("lemma_id") or 0)))}</code></p>
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
    {generate_status_script(letter_slug)}
</body>
</html>
"""
    return html


def compute_meineke_comparison_stats(cur) -> dict:
    """
    Compare our Greek (Billerbeck OCR and human corrections) to Meineke paragraphs.

    Note: This page is intended as a high-level QA/progress view, not a philological judgment
    about editorial differences. "Same/different" is defined by string comparison after
    normalization (see classify_text_difference()).
    """
    cur.execute(
        """
        SELECT
            a.id,
            a.lemma,
            COALESCE(a.greek_text, '') as ocr_greek_text,
            COALESCE(a.corrected_greek_scan, '') as corrected_greek_scan,
            COALESCE(a.human_greek_text, '') as human_greek_text,
            COALESCE(a.review_status, 'not_reviewed') as review_status,
            COALESCE(a.corrected_english_translation, '') as corrected_english_translation,
            COALESCE(a.reviewed_english_translation, '') as reviewed_english_translation,
            COALESCE(mh_match.greek_paragraph, '') as meineke_greek_paragraph
        FROM assembled_lemmas a
        LEFT JOIN LATERAL (
            SELECT mh.greek_paragraph
            FROM meineke_headwords mh
            WHERE (
                (a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id)
                OR (a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id)
                OR (a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id)
            )
            ORDER BY
                CASE
                    WHEN a.nodegoat_id IS NOT NULL AND a.nodegoat_id != '' AND mh.nodegoat_id = a.nodegoat_id THEN 0
                    WHEN a.billerbeck_id IS NOT NULL AND a.billerbeck_id != '' AND mh.billerbeck_id = a.billerbeck_id THEN 1
                    WHEN a.meineke_id IS NOT NULL AND a.meineke_id != '' AND mh.meineke_id = a.meineke_id THEN 2
                    ELSE 3
                END,
                mh.id
            LIMIT 1
        ) mh_match ON TRUE
        WHERE a.version = 'epitome'
          AND COALESCE(a.quarantined, FALSE) = FALSE
          AND a.greek_text IS NOT NULL
          AND a.greek_text != ''
        ORDER BY a.id
        """
    )
    rows = cur.fetchall()

    def init_diff():
        return {"total": 0, "same": 0, "different": 0, "tone_marks_only": 0}

    def update_diff(bucket: dict, diff_class: str):
        bucket["total"] += 1
        if diff_class == "same":
            bucket["same"] += 1
            return
        bucket["different"] += 1
        if diff_class == "tone_marks_only":
            bucket["tone_marks_only"] += 1

    total = len(rows)
    with_meineke = 0
    human_corrected = 0
    human_reviewed = 0

    review_status_counts = {"not_reviewed": 0, "reviewed_ok": 0, "reviewed_corrections": 0, "other": 0}

    diff_corrected_vs_meineke = init_diff()
    diff_uncorrected_vs_meineke = init_diff()
    diff_best_vs_meineke = init_diff()
    diff_reviewed_best_vs_meineke = init_diff()

    for (
        lemma_id,
        lemma,
        ocr_greek_text,
        corrected_greek_scan,
        human_greek_text,
        review_status,
        corrected_english_translation,
        reviewed_english_translation,
        meineke_greek_paragraph,
    ) in rows:
        ocr_greek_text = ocr_greek_text or ""
        corrected_greek_scan = corrected_greek_scan or ""
        human_greek_text = human_greek_text or ""
        meineke_greek_paragraph = meineke_greek_paragraph or ""

        status = (review_status or "").strip() or "not_reviewed"
        if status in review_status_counts:
            review_status_counts[status] += 1
        else:
            review_status_counts["other"] += 1

        has_human_correction = bool(corrected_greek_scan.strip() or human_greek_text.strip())
        if has_human_correction:
            human_corrected += 1

        is_reviewed = (
            status in ("reviewed_ok", "reviewed_corrections")
            or bool((corrected_english_translation or "").strip())
            or bool((reviewed_english_translation or "").strip())
        )
        if is_reviewed:
            human_reviewed += 1

        has_meineke = bool(meineke_greek_paragraph.strip())
        if not has_meineke:
            continue
        with_meineke += 1

        # Choose "best available" Billerbeck: corrected Greek first, else OCR.
        best_greek = (corrected_greek_scan.strip() or human_greek_text.strip() or ocr_greek_text.strip())

        update_diff(diff_best_vs_meineke, classify_text_difference(best_greek, meineke_greek_paragraph))

        if is_reviewed:
            update_diff(diff_reviewed_best_vs_meineke, classify_text_difference(best_greek, meineke_greek_paragraph))

        if has_human_correction:
            corrected_greek = corrected_greek_scan.strip() or human_greek_text.strip()
            update_diff(diff_corrected_vs_meineke, classify_text_difference(corrected_greek, meineke_greek_paragraph))
        else:
            update_diff(diff_uncorrected_vs_meineke, classify_text_difference(ocr_greek_text, meineke_greek_paragraph))

    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "scope": "assembled_lemmas.version = 'epitome' with non-empty greek_text",
        "totals": {
            "total_entries": total,
            "entries_with_meineke": with_meineke,
            "entries_human_corrected": human_corrected,
            "entries_human_reviewed": human_reviewed,
        },
        "review_status_counts": review_status_counts,
        "comparisons": {
            "human_corrected_vs_meineke": diff_corrected_vs_meineke,
            "uncorrected_ocr_vs_meineke": diff_uncorrected_vs_meineke,
            "best_available_vs_meineke": diff_best_vs_meineke,
            "human_reviewed_best_vs_meineke": diff_reviewed_best_vs_meineke,
        },
    }


def generate_meineke_comparison_page(stats: dict) -> str:
    def fmt_pct(n: int, d: int) -> str:
        if not d:
            return "N/A"
        return f"{(100.0 * n / d):.1f}%"

    totals = stats.get("totals", {})
    comparisons = stats.get("comparisons", {})

    total_entries = int(totals.get("total_entries", 0) or 0)
    entries_with_meineke = int(totals.get("entries_with_meineke", 0) or 0)
    entries_human_corrected = int(totals.get("entries_human_corrected", 0) or 0)
    entries_human_reviewed = int(totals.get("entries_human_reviewed", 0) or 0)

    review_counts = stats.get("review_status_counts", {}) or {}
    reviewed_ok = int(review_counts.get("reviewed_ok", 0) or 0)
    reviewed_corr = int(review_counts.get("reviewed_corrections", 0) or 0)
    not_reviewed = int(review_counts.get("not_reviewed", 0) or 0)

    def row(name: str, bucket: dict) -> str:
        total = int(bucket.get("total", 0) or 0)
        same = int(bucket.get("same", 0) or 0)
        different = int(bucket.get("different", 0) or 0)
        tone_only = int(bucket.get("tone_marks_only", 0) or 0)
        substantive = max(0, different - tone_only)
        return f"""
            <tr>
                <td>{html_module.escape(name)}</td>
                <td>{total:,}</td>
                <td>{same:,} ({fmt_pct(same, total)})</td>
                <td>{different:,} ({fmt_pct(different, total)})</td>
                <td>{tone_only:,} ({fmt_pct(tone_only, different)})</td>
                <td>{substantive:,} ({fmt_pct(substantive, different)})</td>
            </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meineke vs Billerbeck - Stephanos Ethnika</title>
    <style>
    {common_styles()}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 18px 0;
        background: #fff;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-radius: 8px;
        overflow: hidden;
    }}
    th, td {{
        padding: 12px 14px;
        border-bottom: 1px solid #eee;
        vertical-align: top;
    }}
    th {{
        background: #0d47a1;
        color: #fff;
        font-weight: 700;
        text-align: left;
    }}
    tr:hover td {{
        background: #fafafa;
    }}
    .note {{
        color: #555;
        font-size: 0.95em;
        line-height: 1.6;
        margin: 10px 0 0;
    }}
    code {{
        background: #f2f4f8;
        padding: 2px 6px;
        border-radius: 4px;
    }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Meineke vs Billerbeck</h1>
        <p>Greek text comparison and human review coverage</p>
    </div>
    <div class="container">
        <div class="nav-links">
            <a href="../index.html">All Letters</a>
            <a href="../sources.html">Ancient Sources</a>
            <a href="../works.html">Works Cited</a>
            <a href="../fgrhist.html">FGrHist Index</a>
            <a href="../entities.html">People &amp; Deities</a>
            <a href="../peoples.html">Ethnic Groups</a>
            <a href="../aliases.html">Aliases</a>
	            <a href="../map.html">Places Map</a>
	            <a href="../statistics.html">Statistics</a>
	            <a href="meineke_difference_analysis.html">Difference Analysis</a>
	            <a href="clustering.html">Clustering</a>
	            <a href="../progress.html">Processing Progress</a>
	            <a href="../pipeline.html">Pipeline Status</a>
	            <a href="../protected/">Page Scans</a>
	            <a href="../cgi-bin/review.cgi">Human Review</a>
            <a href="../downloads.html">Downloads</a>
        </div>

        <div class="breadcrumb"><a href="../index.html">All Letters</a> / Meineke vs Billerbeck</div>

        <h2>Coverage</h2>
        <div class="stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0;">
            <div class="stat-card">
                <div class="stat-value">{total_entries:,}</div>
                <div class="stat-label">Billerbeck OCR entries</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{entries_with_meineke:,}</div>
                <div class="stat-label">With Meineke paragraph</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{entries_human_corrected:,}</div>
                <div class="stat-label">Human-corrected Greek</div>
                <div class="stat-meta">{fmt_pct(entries_human_corrected, total_entries)} of OCR entries</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{entries_human_reviewed:,}</div>
                <div class="stat-label">Human-reviewed (any)</div>
                <div class="stat-meta">{fmt_pct(entries_human_reviewed, total_entries)} of OCR entries</div>
            </div>
        </div>

        <p class="note">
            Scope: <code>{html_module.escape(stats.get('scope', ''))}</code><br>
            Generated: {html_module.escape(stats.get('generated_at_utc', ''))}<br>
            Human-reviewed (any): <code>review_status</code> is <code>reviewed_ok</code>/<code>reviewed_corrections</code>, or a human translation field is present
        </p>

        <h2>Human Review Status</h2>
        <table>
            <tr>
                <th>Status</th>
                <th>Count</th>
                <th>Share of OCR entries</th>
            </tr>
            <tr>
                <td>not_reviewed</td>
                <td>{not_reviewed:,}</td>
                <td>{fmt_pct(not_reviewed, total_entries)}</td>
            </tr>
            <tr>
                <td>reviewed_ok</td>
                <td>{reviewed_ok:,}</td>
                <td>{fmt_pct(reviewed_ok, total_entries)}</td>
            </tr>
            <tr>
                <td>reviewed_corrections</td>
                <td>{reviewed_corr:,}</td>
                <td>{fmt_pct(reviewed_corr, total_entries)}</td>
            </tr>
        </table>

        <h2>Differences vs Meineke</h2>
        <p class="note">
            For comparison, we normalize text by: stripping any Meineke nodegoat <code>[object=...]</code> tags,
            stripping citation-only parenthetical/bracketed markers (e.g. <code>(FGrHist ...)</code>,
            <code>(fr. ...)</code>), NFC-normalizing Unicode (so tonos/oxia compare consistently), collapsing
            whitespace, and ignoring punctuation/symbol characters. “Tone-marks only” means the strings become
            equal after removing combining diacritics (accents/breathings) but are not equal under the above
            normalization.
        </p>

        <table>
            <tr>
                <th>Comparison</th>
                <th>Compared</th>
                <th>Same</th>
                <th>Different</th>
                <th>Tone-marks only</th>
                <th>Substantive</th>
            </tr>
            {row("Human-corrected Greek vs Meineke", comparisons.get("human_corrected_vs_meineke", {}))}
            {row("Uncorrected OCR vs Meineke", comparisons.get("uncorrected_ocr_vs_meineke", {}))}
            {row("Best available (corrected else OCR) vs Meineke", comparisons.get("best_available_vs_meineke", {}))}
            {row("Human-reviewed (best available) vs Meineke", comparisons.get("human_reviewed_best_vs_meineke", {}))}
        </table>

        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def extract_images_from_database(cur, output_dir: Path):
    """Extract image BLOBs from database to protected directory"""
    protected_dir = output_dir / "protected"
    protected_dir.mkdir(exist_ok=True)
    used_names = set()

    # Get all unique image filenames used in assembled lemmas
    cur.execute(
        """
        SELECT DISTINCT i.image_filename, i.image_data, i.image_mime_type
        FROM images i
        WHERE i.id IN (
            SELECT DISTINCT unnest(
                ARRAY(
                    SELECT jsonb_array_elements_text(a.source_image_ids::jsonb)::int
                    FROM assembled_lemmas a
                    WHERE COALESCE(a.quarantined, FALSE) = FALSE
                )
            )
        )
        AND i.image_data IS NOT NULL
        """
    )

    images = cur.fetchall()
    extracted = 0

    for filename, image_data, mime_type in images:
        if not image_data:
            continue

        # Keep extracted files inside protected/ even if DB filename contains paths like ../graphic/...
        safe_name = Path(filename or "").name
        if not safe_name:
            safe_name = f"image_{extracted + 1:06d}.bin"
        if safe_name in used_names:
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix
            digest = hashlib.sha1((filename or safe_name).encode("utf-8")).hexdigest()[:8]
            safe_name = f"{stem}_{digest}{suffix}"
        used_names.add(safe_name)

        image_path = protected_dir / safe_name
        image_path.write_bytes(image_data)
        extracted += 1

    return extracted


def main():
    conn = get_connection()
    cur = conn.cursor()

    # Get all lemmas and bucket by letter
    lemmas = get_all_lemmas(cur)
    stats = {
        'total_lemmas': len(lemmas),
        'translated_lemmas': sum(1 for l in lemmas if l.get('translated')),
        'total_images': 0,
        'processed_images': 0,
    }

    # Page counts
    cur.execute("SELECT COUNT(*), SUM(processed) FROM images")
    img_row = cur.fetchone()
    stats['total_images'] = img_row[0] or 0
    stats['processed_images'] = img_row[1] or 0

    buckets = {slug: [] for _, _, slug in GREEK_LETTERS}
    buckets["other"] = []
    for lemma in lemmas:
        buckets.setdefault(lemma['letter_slug'], []).append(lemma)

    # Sort lemmas within each bucket by lemma text then entry number
    # Normalize Greek text by stripping accents/diacritics for alphabetical sorting
    def normalize_for_sort(text: str) -> str:
        """Normalize Greek text for alphabetical sorting by removing accents."""
        return ''.join(strip_combining(ch) for ch in text)

    def entry_number_for_sort(item) -> int:
        raw = item.get("entry_number")
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.isdigit():
                return int(raw)
        return 0

    for slug in buckets:
        buckets[slug].sort(key=lambda x: (normalize_for_sort(x['lemma']), entry_number_for_sort(x)))

    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    # Extract images from database to protected directory
    images_extracted = extract_images_from_database(cur, output_dir)

    # Generate Meineke comparison page (best-effort; don't fail the whole site on stats issues)
    try:
        protected_dir = output_dir / "protected"
        protected_dir.mkdir(exist_ok=True)
        meineke_stats = compute_meineke_comparison_stats(cur)
        meineke_html = generate_meineke_comparison_page(meineke_stats)
        (protected_dir / "meineke_comparison.html").write_text(meineke_html, encoding='utf-8')
    except Exception as e:
        print(f"Warning: failed to generate Meineke comparison page: {e}")
        fallback_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meineke vs Billerbeck - Stephanos Ethnika</title>
    <style>
    {common_styles()}
    code, pre {{
        background: #f2f4f8;
        padding: 2px 6px;
        border-radius: 4px;
    }}
    pre {{
        padding: 12px;
        overflow-x: auto;
    }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Meineke vs Billerbeck</h1>
        <p>Greek text comparison and human review coverage</p>
    </div>
    <div class="container">
	        <div class="nav-links">
	            <a href="../index.html">All Letters</a>
	            <a href="../statistics.html">Statistics</a>
	            <a href="meineke_difference_analysis.html">Difference Analysis</a>
	            <a href="clustering.html">Clustering</a>
	            <a href="../pipeline.html">Pipeline Status</a>
	            <a href="../cgi-bin/review.cgi">Human Review</a>
	        </div>
        <div class="breadcrumb"><a href="../index.html">All Letters</a> / Meineke vs Billerbeck</div>
        <h2>Page Unavailable</h2>
        <p>This page could not be generated.</p>
        <p class="note">
            Common causes:
            <code>meineke_headwords</code> table missing, <code>billerbeck_id</code>/<code>meineke_id</code> not populated, or database schema mismatch.
        </p>
        <h3>Error</h3>
        <pre>{html_module.escape(str(e))}</pre>
        <div class="footer">
            <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
</body>
</html>
"""
        (protected_dir / "meineke_comparison.html").write_text(fallback_html, encoding='utf-8')

    overlap_by_lemma, overlap_run_id = fetch_herodian_overlaps_by_lemma(
        [int(lemma.get("lemma_id") or 0) for lemma in lemmas],
        metric_version="v1",
        per_lemma_limit=10,
    )

    conn.close()

    # Generate index
    letter_counts = {slug: len(items) for slug, items in buckets.items()}
    index_html = generate_index_html(letter_counts, stats)
    (output_dir / "index.html").write_text(index_html, encoding='utf-8')

    # Generate per-letter pages (list of links to canonical headword pages).
    for char, name, slug in GREEK_LETTERS:
        page_html = generate_letter_page(char, name, slug, buckets.get(slug, []))
        (output_dir / f"letter_{slug}.html").write_text(page_html, encoding='utf-8')

    # Generate canonical per-headword pages.
    for lemma in lemmas:
        lemma_id = int(lemma.get("lemma_id") or 0)
        page_html = generate_headword_page(
            lemma,
            overlaps=overlap_by_lemma.get(lemma_id, []),
            overlap_run_id=overlap_run_id,
        )
        (output_dir / headword_page_filename(lemma_id)).write_text(page_html, encoding='utf-8')

    print(f"Reference website generated in {output_dir.absolute()}")
    print(f"  Total lemmas: {stats['total_lemmas']}")
    print(f"  Translated lemmas: {stats['translated_lemmas']}")
    print(f"  Pages OCR'd: {stats['processed_images']} / {stats['total_images']}")
    print(f"  Images extracted from database: {images_extracted}")
    if overlap_run_id:
        print(f"  Herodian overlap run used: {overlap_run_id}")
    else:
        print("  Herodian overlap run used: unavailable")

if __name__ == "__main__":
    main()
