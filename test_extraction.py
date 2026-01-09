#!/usr/bin/env python3
"""Quick test of proper noun extraction with new schema"""
import json
from pathlib import Path
from openai import OpenAI
from db import get_connection

# Import from extract_proper_nouns
import sys
sys.path.insert(0, str(Path(__file__).parent))
from extract_proper_nouns import extract_proper_nouns_for_lemma

def main():
    # Get test lemma
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, lemma, greek_text FROM assembled_lemmas WHERE id = 2055")
    lemma_id, lemma_name, greek_text = cur.fetchone()

    print(f"Testing lemma: {lemma_name}")
    print(f"Greek text: {greek_text}")
    print()

    # Load API key
    api_key = (Path.home() / ".openai.key").read_text().strip()
    client = OpenAI(api_key=api_key)

    # Extract
    print("Calling API...")
    proper_nouns, tokens = extract_proper_nouns_for_lemma(client, greek_text)

    print(f"\nTokens used: {tokens}")
    print(f"Proper nouns found: {len(proper_nouns)}")
    print()

    for noun in proper_nouns:
        print(json.dumps(noun, indent=2, ensure_ascii=False))
        print()

    conn.close()

if __name__ == "__main__":
    main()
