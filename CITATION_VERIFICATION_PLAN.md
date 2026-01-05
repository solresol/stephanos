# Citation Verification Plan

## Goal

Verify whether Stephanos of Byzantium's citations of ancient sources accurately reflect the original texts. When Stephanos cites Herodotus, Strabo, Homer, or other authors, we want to:

1. Find the original passage in digital text collections
2. Compare Stephanos's description/quotation with the original
3. Track discrepancies for scholarly analysis

## Current State

### What We Already Have ✅

The `extract_proper_nouns.py` script already extracts citation data from lemmas:

- **Author names** marked with `role='source'` (vs `role='entity'` for people in the story)
- **Citations** like "FGrHist 1 F 290", "fr. 32 Borries", "(I 529)"
- **Work titles** in Greek (e.g., "Ἀσίᾳ" = "Asia")

This data is stored in the `proper_nouns` table:
- `lemma_id` → links to `assembled_lemmas`
- `proper_noun`, `lemma_form`, `english_translation`
- `noun_type` (person, place, people, deity, other)
- `role` ('source' or 'entity')
- `citation` (the citation string)
- `work_title` (work name if present)

### What We Need to Build 🚧

A verification pipeline that:
1. Parses citations into structured formats
2. Resolves them to retrievable text passages (CTS URNs or API queries)
3. Fetches the original text from digital libraries
4. Compares with Stephanos's text using LLM assistance
5. Tracks verification status and findings

## Available Digital Text Resources

### 1. Perseus/Scaife Viewer (Primary Resource)

**Coverage**: 1,639 Greek editions, 95% complete
**API**: CTS (Canonical Text Services) at https://atlas.perseus.tufts.edu/
**Format**: CTS URNs like `urn:cts:greekLit:tlg0003.tlg001:5.84.1`
**Best for**: Major canonical authors (Homer, Herodotus, Thucydides, Strabo, etc.)

**Resources**:
- Perseus CTS API: https://sites.tufts.edu/perseusupdates/beta-features/perseus-cts-api/
- Scaife Viewer: https://scaife.perseus.org/
- CTS URN Guide: https://www.opengreekandlatin.org/what-is-a-cts-urn/

**Example Query**:
```
https://atlas.perseus.tufts.edu/api/text/urn:cts:greekLit:tlg0012.tlg001:1.529
```

### 2. DFHG (Digital Fragmenta Historicorum Graecorum)

**Coverage**: Fragmentary Greek historians (FGrHist/FHG collections)
**API**: http://www.dfhg-project.org/DFHG/api.php
**Best for**: Citations in "FGrHist X F Y" format

**Resources**:
- DFHG Project: https://www.dfhg-project.org/
- Müller-Jacoby Concordance for mapping FHG ↔ FGrHist

**Example Query**:
```
http://www.dfhg-project.org/DFHG/api.php?author=ACUSILAUS&fragment=10
```

### 3. ToposText (Not Suitable)

**Coverage**: 868 ancient texts, extensive gazetteer
**Limitation**: No public API - mobile app and website only
**Resources**: https://topostext.org/

## Implementation Plan

### Phase 1: Database Schema Updates

**Goal**: Add verification tracking columns to `proper_nouns` table

**Migration** (`migrations/add_citation_verification.sql`):

```sql
-- Add citation verification columns to proper_nouns
ALTER TABLE proper_nouns
ADD COLUMN IF NOT EXISTS citation_verified BOOLEAN DEFAULT FALSE;

ALTER TABLE proper_nouns
ADD COLUMN IF NOT EXISTS citation_cts_urn TEXT;
COMMENT ON COLUMN proper_nouns.citation_cts_urn IS
'Resolved CTS URN (e.g., urn:cts:greekLit:tlg0012.tlg001:1.529)';

ALTER TABLE proper_nouns
ADD COLUMN IF NOT EXISTS citation_text TEXT;
COMMENT ON COLUMN proper_nouns.citation_text IS
'Retrieved original text from digital library';

ALTER TABLE proper_nouns
ADD COLUMN IF NOT EXISTS verification_status TEXT
CHECK (verification_status IN (
    'not_verified',    -- Haven't checked yet
    'matched',         -- Found and verified as accurate
    'discrepancy',     -- Found but Stephanos differs from original
    'not_found',       -- Citation not found in digital libraries
    'ambiguous'        -- Multiple possible matches
));

ALTER TABLE proper_nouns
ADD COLUMN IF NOT EXISTS verification_notes TEXT;
COMMENT ON COLUMN proper_nouns.verification_notes IS
'LLM-generated comparison notes or error messages';

ALTER TABLE proper_nouns
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

-- Create indexes for filtering
CREATE INDEX IF NOT EXISTS idx_proper_nouns_role_source
ON proper_nouns(role) WHERE role = 'source';

CREATE INDEX IF NOT EXISTS idx_proper_nouns_verification_status
ON proper_nouns(verification_status);

CREATE INDEX IF NOT EXISTS idx_proper_nouns_citation_verified
ON proper_nouns(citation_verified);
```

**Test**:
```bash
psql -U stephanos -d stephanos -f migrations/add_citation_verification.sql
```

### Phase 2: Citation Parser

**Goal**: Parse citation strings into structured formats for querying

**File**: `parse_citation.py`

**Citation Formats to Handle**:

1. **FGrHist**: "FGrHist 1 F 290", "FGrHist 76 F 1"
2. **Fragment editions**: "fr. 32 Borries", "fr. 1 Müller"
3. **Book/line references**: "(I 529)" = Iliad book 1, line 529
4. **Combined**: "FGrHist 1 F 290 = fr. 32 Borries"
5. **Work titles**: Greek titles like "Ἀσίᾳ", "Εὐρώπῃ"

**Output Structure**:

```python
{
    "type": "fgrhist",  # or "iliad", "odyssey", "fragment", "book_reference"
    "author_num": 1,    # for FGrHist
    "fragment": 290,
    "book": None,
    "line": None,
    "editor": None,
    "raw": "FGrHist 1 F 290"
}
```

**Implementation**:

```python
#!/usr/bin/env python3
"""
Parse ancient Greek citation strings into structured formats.
"""
import re
from typing import Optional, Dict, Any

def parse_citation(citation: str, work_title: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse citation string into structured format.

    Args:
        citation: Citation string (e.g., "FGrHist 1 F 290")
        work_title: Optional work title in Greek

    Returns:
        Dict with parsed components and type
    """
    if not citation:
        return {"type": "unknown", "raw": citation}

    citation = citation.strip()

    # FGrHist pattern: "FGrHist 1 F 290"
    fgrhist_match = re.match(r'FGrHist\s+(\d+)\s+F\s+(\d+)', citation, re.IGNORECASE)
    if fgrhist_match:
        return {
            "type": "fgrhist",
            "author_num": int(fgrhist_match.group(1)),
            "fragment": int(fgrhist_match.group(2)),
            "raw": citation
        }

    # Fragment with editor: "fr. 32 Borries"
    fragment_match = re.match(r'fr\.\s*(\d+)\s+(\w+)', citation, re.IGNORECASE)
    if fragment_match:
        return {
            "type": "fragment",
            "fragment": int(fragment_match.group(1)),
            "editor": fragment_match.group(2),
            "raw": citation
        }

    # Book/line reference: "(I 529)" or "(1.529)"
    book_line_match = re.match(r'\(([IVX]+|\d+)[\s\.](\d+)\)', citation)
    if book_line_match:
        book = book_line_match.group(1)
        # Convert Roman numerals to Arabic
        if book in {'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                    'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII',
                    'XIX', 'XX', 'XXI', 'XXII', 'XXIII', 'XXIV'}:
            book_num = roman_to_int(book)
        else:
            book_num = int(book)

        return {
            "type": "book_line",
            "book": book_num,
            "line": int(book_line_match.group(2)),
            "raw": citation
        }

    # Unknown format
    return {
        "type": "unknown",
        "raw": citation
    }


def roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer."""
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    prev = 0
    for char in reversed(roman):
        val = values[char]
        if val < prev:
            total -= val
        else:
            total += val
        prev = val
    return total


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "FGrHist 1 F 290",
        "fr. 32 Borries",
        "(I 529)",
        "(5.84.1)",
        "unknown format"
    ]

    for citation in test_cases:
        result = parse_citation(citation)
        print(f"{citation:20} → {result}")
```

### Phase 3: Citation Resolver

**Goal**: Map parsed citations to CTS URNs or DFHG API queries

**File**: `resolve_citation.py`

**Author Name Mapping**:

Build a mapping table of Greek author names to CTS identifiers:

```python
# Author name → CTS work identifier
AUTHOR_CTS_MAP = {
    "Ὅμηρος": {
        "Iliad": "tlg0012.tlg001",
        "Odyssey": "tlg0012.tlg002"
    },
    "Ἡρόδοτος": {
        "Histories": "tlg0016.tlg001"
    },
    "Θουκυδίδης": {
        "History": "tlg0003.tlg001"
    },
    "Στράβων": {
        "Geography": "tlg0099.tlg001"
    },
    # Add more authors as needed
}

# English variants
AUTHOR_CTS_MAP_EN = {
    "Homer": AUTHOR_CTS_MAP["Ὅμηρος"],
    "Herodotus": AUTHOR_CTS_MAP["Ἡρόδοτος"],
    "Thucydides": AUTHOR_CTS_MAP["Θουκυδίδης"],
    "Strabo": AUTHOR_CTS_MAP["Στράβων"],
}
```

**Implementation**:

```python
#!/usr/bin/env python3
"""
Resolve parsed citations to CTS URNs or DFHG API queries.
"""
from typing import Optional, Dict, Any
from parse_citation import parse_citation

def resolve_to_cts(author_lemma: str, citation_data: Dict[str, Any],
                   work_title: Optional[str] = None) -> Optional[str]:
    """
    Map author + citation to CTS URN.

    Args:
        author_lemma: Canonical form of author name (Greek or English)
        citation_data: Parsed citation dict
        work_title: Optional work title

    Returns:
        CTS URN string or None if not resolvable
    """
    # Get CTS work identifier for author
    works = AUTHOR_CTS_MAP.get(author_lemma) or AUTHOR_CTS_MAP_EN.get(author_lemma)
    if not works:
        return None

    # Determine which work
    if work_title:
        work_id = works.get(work_title)
    elif len(works) == 1:
        work_id = list(works.values())[0]
    else:
        # Ambiguous - need work title
        return None

    if not work_id:
        return None

    # Build passage reference
    if citation_data["type"] == "book_line":
        passage = f"{citation_data['book']}.{citation_data['line']}"
    else:
        return None  # Can't convert this citation type

    return f"urn:cts:greekLit:{work_id}:{passage}"


def resolve_to_dfhg(author_name: str, citation_data: Dict[str, Any]) -> Optional[str]:
    """
    Map FGrHist citation to DFHG API query URL.

    Args:
        author_name: Author name (will need mapping to DFHG author names)
        citation_data: Parsed citation with type='fgrhist'

    Returns:
        DFHG API URL or None
    """
    if citation_data["type"] != "fgrhist":
        return None

    # TODO: Build FGrHist number → DFHG author name mapping
    # For now, return the API pattern
    author_num = citation_data["author_num"]
    fragment = citation_data["fragment"]

    # This requires a lookup table: FGrHist_num → DFHG_author_name
    # See: http://www.dfhg-project.org/Mueller-Jacoby-Concordance/

    return f"http://www.dfhg-project.org/DFHG/api.php?fgrhist={author_num}&fragment={fragment}"
```

**Research Task**: Build the FGrHist number → DFHG author name concordance

### Phase 4: Text Retrieval

**Goal**: Fetch original text passages from APIs

**File**: `fetch_source_text.py`

```python
#!/usr/bin/env python3
"""
Retrieve ancient text passages from Perseus CTS and DFHG APIs.
"""
import requests
from typing import Optional, Dict, Any

def fetch_from_perseus_cts(cts_urn: str) -> Optional[Dict[str, Any]]:
    """
    Query Perseus ATLAS API for text passage.

    Args:
        cts_urn: CTS URN (e.g., urn:cts:greekLit:tlg0012.tlg001:1.529)

    Returns:
        Dict with keys: greek_text, translation (if available), metadata
    """
    # Strip 'urn:cts:' prefix for API
    urn_path = cts_urn.replace("urn:cts:", "")

    url = f"https://atlas.perseus.tufts.edu/api/text/{urn_path}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Parse XML or JSON response
        # This will depend on Perseus ATLAS response format
        # Needs investigation of actual API response structure

        return {
            "greek_text": response.text,  # Placeholder
            "cts_urn": cts_urn,
            "source": "perseus"
        }
    except Exception as e:
        return {
            "error": str(e),
            "cts_urn": cts_urn
        }


def fetch_from_dfhg(author: str, fragment: int) -> Optional[Dict[str, Any]]:
    """
    Query DFHG API for fragmentary historian passage.

    Args:
        author: DFHG author name (uppercase)
        fragment: Fragment number

    Returns:
        Dict with fragment text and metadata
    """
    url = f"http://www.dfhg-project.org/DFHG/api.php?author={author}&fragment={fragment}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        return {
            "greek_text": data.get("fragment_text"),  # Placeholder - check actual format
            "testimonies": data.get("testimonies"),
            "author": author,
            "fragment": fragment,
            "source": "dfhg"
        }
    except Exception as e:
        return {
            "error": str(e),
            "author": author,
            "fragment": fragment
        }
```

**Research Tasks**:
1. Test Perseus ATLAS API to understand response format
2. Test DFHG API to understand JSON structure
3. Handle authentication if required

### Phase 5: Comparison & Verification

**Goal**: Compare Stephanos's text with original using LLM

**File**: `verify_citations.py`

```python
#!/usr/bin/env python3
"""
Verify Stephanos citations against original sources.
"""
from openai import OpenAI
from pathlib import Path
import json
from db import get_connection
from parse_citation import parse_citation
from resolve_citation import resolve_to_cts, resolve_to_dfhg
from fetch_source_text import fetch_from_perseus_cts, fetch_from_dfhg

def load_api_key():
    """Load OpenAI API key from ~/.openai.key"""
    key_path = Path.home() / ".openai.key"
    return key_path.read_text().strip()


VERIFICATION_SYSTEM_PROMPT = """You are a classical philologist comparing ancient citations.
You will be shown:
1. A passage from Stephanos of Byzantium that references an ancient author
2. The original text from that ancient author

Your task is to assess whether Stephanos's citation is accurate."""


VERIFICATION_USER_PROMPT = """Compare these two texts:

**Stephanos of Byzantium says:**
{stephanos_text}

**Original source ({author_name}, {citation}):**
{original_text}

Assess the citation accuracy:
- Does Stephanos quote directly, paraphrase, or summarize?
- Is the citation accurate, or are there discrepancies?
- Does Stephanos add interpretive commentary?

Classify as:
- "matched": Accurate quote or faithful paraphrase
- "discrepancy": Meaningful difference from original
- "ambiguous": Unclear if this is the right passage

Provide brief notes explaining your assessment."""


VERIFICATION_TOOL = {
    "type": "function",
    "function": {
        "name": "verify_citation",
        "description": "Assess citation accuracy",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["matched", "discrepancy", "ambiguous"],
                    "description": "Verification result"
                },
                "notes": {
                    "type": "string",
                    "description": "Explanation of assessment"
                }
            },
            "required": ["status", "notes"]
        }
    }
}


def verify_citation_with_llm(client, stephanos_context: str, original_text: str,
                             author_name: str, citation: str, model="gpt-5-mini"):
    """
    Use LLM to compare Stephanos's text with original source.

    Returns:
        Dict with keys: status ('matched'|'discrepancy'|'ambiguous'), notes
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": VERIFICATION_USER_PROMPT.format(
                stephanos_text=stephanos_context,
                original_text=original_text,
                author_name=author_name,
                citation=citation
            )}
        ],
        tools=[VERIFICATION_TOOL],
        tool_choice={"type": "function", "function": {"name": "verify_citation"}}
    )

    tool_call = response.choices[0].message.tool_calls[0]
    result = json.loads(tool_call.function.arguments)

    return result


def verify_proper_noun_citation(proper_noun_id: int):
    """
    Full verification pipeline for a single proper_noun citation.

    Steps:
    1. Get proper noun and related lemma from database
    2. Parse the citation
    3. Resolve to CTS URN or DFHG query
    4. Fetch original text
    5. Compare with LLM
    6. Update database with results
    """
    conn = get_connection()
    cur = conn.cursor()

    # Get proper noun data
    cur.execute("""
        SELECT pn.id, pn.lemma_form, pn.citation, pn.work_title, pn.lemma_id,
               al.greek_text, al.lemma
        FROM proper_nouns pn
        JOIN assembled_lemmas al ON pn.lemma_id = al.id
        WHERE pn.id = %s AND pn.role = 'source'
    """, (proper_noun_id,))

    row = cur.fetchone()
    if not row:
        print(f"Proper noun {proper_noun_id} not found or not a source")
        return

    pn_id, author_lemma, citation, work_title, lemma_id, stephanos_text, lemma_name = row

    print(f"Verifying: {author_lemma} citation '{citation}' in lemma '{lemma_name}'")

    # Parse citation
    citation_data = parse_citation(citation, work_title)
    if citation_data["type"] == "unknown":
        cur.execute("""
            UPDATE proper_nouns
            SET verification_status = 'not_found',
                verification_notes = 'Unknown citation format',
                verified_at = NOW()
            WHERE id = %s
        """, (pn_id,))
        conn.commit()
        print("  → Unknown citation format")
        return

    # Resolve to CTS URN or DFHG
    cts_urn = resolve_to_cts(author_lemma, citation_data, work_title)
    if cts_urn:
        print(f"  → Resolved to CTS: {cts_urn}")
        original = fetch_from_perseus_cts(cts_urn)
    elif citation_data["type"] == "fgrhist":
        print(f"  → Resolved to DFHG")
        original = fetch_from_dfhg(author_lemma, citation_data)
    else:
        cur.execute("""
            UPDATE proper_nouns
            SET verification_status = 'not_found',
                verification_notes = 'Could not resolve citation',
                verified_at = NOW()
            WHERE id = %s
        """, (pn_id,))
        conn.commit()
        print("  → Could not resolve")
        return

    if "error" in original:
        cur.execute("""
            UPDATE proper_nouns
            SET verification_status = 'not_found',
                verification_notes = %s,
                verified_at = NOW()
            WHERE id = %s
        """, (f"API error: {original['error']}", pn_id))
        conn.commit()
        print(f"  → API error: {original['error']}")
        return

    # Compare with LLM
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    verification = verify_citation_with_llm(
        client,
        stephanos_text,
        original["greek_text"],
        author_lemma,
        citation
    )

    # Update database
    cur.execute("""
        UPDATE proper_nouns
        SET citation_verified = TRUE,
            citation_cts_urn = %s,
            citation_text = %s,
            verification_status = %s,
            verification_notes = %s,
            verified_at = NOW()
        WHERE id = %s
    """, (
        cts_urn,
        original["greek_text"],
        verification["status"],
        verification["notes"],
        pn_id
    ))
    conn.commit()
    conn.close()

    print(f"  → {verification['status']}: {verification['notes']}")


def main():
    """Verify all unverified source citations."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, lemma_form, citation
        FROM proper_nouns
        WHERE role = 'source'
          AND citation IS NOT NULL
          AND (citation_verified = FALSE OR citation_verified IS NULL)
        ORDER BY id
    """)

    sources = cur.fetchall()
    conn.close()

    if not sources:
        print("No unverified citations found.")
        return

    print(f"Found {len(sources)} citations to verify\n")

    for pn_id, author, citation in sources:
        try:
            verify_proper_noun_citation(pn_id)
        except Exception as e:
            print(f"ERROR verifying {pn_id}: {e}")
            continue


if __name__ == "__main__":
    main()
```

### Phase 6: Reporting Interface

**Goal**: Display verification results on reference website

**Updates to** `generate_reference_site.py`:

1. Show citation verification status badges:
   - ✅ matched (green)
   - ⚠️ discrepancy (yellow)
   - ❓ ambiguous (gray)
   - ❌ not found (red)

2. For each source citation, display:
   - Author name and citation
   - Link to original (CTS viewer or DFHG)
   - Verification notes from LLM
   - Original text excerpt

3. Add a "Citations Report" page listing all discrepancies for scholarly review

**Example HTML**:

```html
<div class="citation">
    <span class="author">Herodotus</span>
    <span class="citation-ref">(I.529)</span>
    <span class="badge verified">✅ Verified</span>
    <a href="https://scaife.perseus.org/reader/urn:cts:greekLit:tlg0016.tlg001:1.529"
       target="_blank">View original</a>
    <p class="verification-note">Stephanos provides an accurate paraphrase of the original passage.</p>
</div>
```

## Integration with Daily Pipeline

Add to `run_daily_pipeline.sh`:

```bash
# After translate_lemmas.py
echo "Verifying source citations..."
uv run verify_citations.py
```

## Research Tasks Before Implementation

### 1. Perseus CTS API Testing
- Test actual API response format
- Determine authentication requirements
- Check rate limits
- Test with sample Stephanos citations

### 2. DFHG API Testing
- Understand JSON response structure
- Build FGrHist number → DFHG author concordance
- Test fragment retrieval

### 3. Author Name Mapping
- Build comprehensive Greek ↔ English author name mapping
- Map authors to CTS work identifiers
- Handle name variants and spelling differences

### 4. Citation Format Analysis
- Query existing `proper_nouns` table to see what citation formats actually appear
- Prioritize most common formats for parser implementation

### 5. LLM Prompt Tuning
- Test comparison prompts with sample citations
- Refine classification criteria
- Handle edge cases (paraphrase vs. quote, interpretive additions, etc.)

## Success Metrics

1. **Coverage**: % of source citations successfully resolved to original texts
2. **Accuracy**: Manual review of LLM verification assessments
3. **Discrepancy rate**: % of citations where Stephanos differs from original
4. **Scholarly value**: Identification of interesting discrepancies for publication

## Timeline Estimate

- **Phase 1** (Schema): 1 hour
- **Phase 2** (Parser): 4-6 hours
- **Phase 3** (Resolver): 8-12 hours (includes research)
- **Phase 4** (Retrieval): 6-8 hours (includes API testing)
- **Phase 5** (Verification): 4-6 hours
- **Phase 6** (Reporting): 4-6 hours

**Total**: ~30-40 hours of development + research time

## Future Enhancements

1. **Interactive review**: Web interface for scholars to correct LLM assessments
2. **Statistical analysis**: Patterns in Stephanos's citation practices
3. **Cross-referencing**: Compare same source cited in multiple lemmas
4. **Translation comparison**: Compare Stephanos's Greek with original Greek
5. **Apparatus criticus**: Eventually verify critical apparatus citations too
