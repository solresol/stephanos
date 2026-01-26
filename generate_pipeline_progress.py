#!/usr/bin/env python3
"""
Generate pipeline progress monitoring page.

This script collects statistics from all pipeline stages and estimates
completion times based on processing rates.

Usage:
  uv run generate_pipeline_progress.py
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import db


def get_progress_stats(conn) -> dict:
    """Collect progress statistics from all pipeline stages."""
    cur = conn.cursor()
    stats = {}

    # 1. Image OCR processing
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN processed = 1 THEN 1 END) as processed,
            COUNT(CASE WHEN processed = 0 THEN 1 END) as pending
        FROM images
    """)
    row = cur.fetchone()
    stats["ocr"] = {
        "name": "Image OCR",
        "total": row[0],
        "completed": row[1],
        "pending": row[2],
        "unit": "images",
    }

    # OCR processing rate (last 7 days)
    cur.execute("""
        SELECT COUNT(*) FROM images
        WHERE processed = 1
          AND processed_at > NOW() - INTERVAL '7 days'
    """)
    stats["ocr"]["rate_7d"] = cur.fetchone()[0]

    # 2. Lemma assembly
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN greek_text IS NOT NULL AND greek_text != '' THEN 1 END) as with_text
        FROM assembled_lemmas
    """)
    row = cur.fetchone()
    stats["assembly"] = {
        "name": "Lemma Assembly",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    # 3. Translation
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN translation IS NOT NULL THEN 1 END) as translated,
            COUNT(CASE WHEN reviewed_english_translation IS NOT NULL THEN 1 END) as human_reviewed,
            COUNT(CASE WHEN corrected_english_translation IS NOT NULL THEN 1 END) as human_edited
        FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL
    """)
    row = cur.fetchone()
    total_with_billerbeck = row[0]
    stats["translation_ai"] = {
        "name": "AI Translation",
        "total": total_with_billerbeck,
        "completed": row[1],
        "pending": total_with_billerbeck - row[1],
        "unit": "entries",
    }
    stats["translation_human"] = {
        "name": "Human Review",
        "total": total_with_billerbeck,
        "completed": row[2] + row[3],  # reviewed or edited
        "pending": total_with_billerbeck - row[2] - row[3],
        "unit": "entries",
    }

    # Translation rate (last 7 days)
    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE translated_at > NOW() - INTERVAL '7 days'
    """)
    stats["translation_ai"]["rate_7d"] = cur.fetchone()[0]

    # 4. Wikidata linking - sources
    cur.execute("""
        SELECT
            COUNT(DISTINCT proper_noun) as total,
            COUNT(DISTINCT CASE WHEN wikidata_qid IS NOT NULL THEN proper_noun END) as linked
        FROM proper_nouns
        WHERE role = 'source'
    """)
    row = cur.fetchone()
    stats["wikidata_sources"] = {
        "name": "Wikidata Sources",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "sources",
    }

    cur.execute("""
        SELECT COUNT(DISTINCT proper_noun) FROM proper_nouns
        WHERE role = 'source'
          AND wikidata_linked_at > NOW() - INTERVAL '7 days'
    """)
    stats["wikidata_sources"]["rate_7d"] = cur.fetchone()[0]

    # 5. Wikidata linking - places
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN wikidata_place_qid IS NOT NULL THEN 1 END) as linked
        FROM assembled_lemmas
        WHERE type IN ('place', 'city', 'region', 'island', 'country', 'village',
                       'mountain', 'river', 'lake', 'spring', 'promontory', 'fortress')
    """)
    row = cur.fetchone()
    stats["wikidata_places"] = {
        "name": "Wikidata Places",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "places",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE wikidata_place_linked_at > NOW() - INTERVAL '7 days'
    """)
    stats["wikidata_places"]["rate_7d"] = cur.fetchone()[0]

    # 6. Alias extraction
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN aliases_analyzed = true THEN 1 END) as analyzed
        FROM assembled_lemmas
        WHERE greek_text IS NOT NULL AND greek_text != ''
    """)
    row = cur.fetchone()
    stats["aliases"] = {
        "name": "Alias Extraction",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE aliases_analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["aliases"]["rate_7d"] = cur.fetchone()[0]

    # 7. Etymology extraction
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN etymologies_analyzed = true THEN 1 END) as analyzed
        FROM assembled_lemmas
        WHERE greek_text IS NOT NULL AND greek_text != ''
    """)
    row = cur.fetchone()
    stats["etymologies"] = {
        "name": "Etymology Extraction",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE etymologies_analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["etymologies"]["rate_7d"] = cur.fetchone()[0]

    # 8. Proper noun extraction
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN proper_nouns_analyzed = true THEN 1 END) as analyzed
        FROM assembled_lemmas
        WHERE greek_text IS NOT NULL AND greek_text != ''
    """)
    row = cur.fetchone()
    stats["proper_nouns"] = {
        "name": "Proper Noun Extraction",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "lemmas",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE proper_nouns_analyzed_at > NOW() - INTERVAL '7 days'
    """)
    stats["proper_nouns"]["rate_7d"] = cur.fetchone()[0]

    # 9. nodegoat sync
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN last_synced_to_nodegoat_at IS NOT NULL THEN 1 END) as synced
        FROM assembled_lemmas
        WHERE billerbeck_id IS NOT NULL AND billerbeck_id != ''
    """)
    row = cur.fetchone()
    stats["nodegoat_sync"] = {
        "name": "nodegoat Sync",
        "total": row[0],
        "completed": row[1],
        "pending": row[0] - row[1],
        "unit": "entries",
    }

    cur.execute("""
        SELECT COUNT(*) FROM assembled_lemmas
        WHERE last_synced_to_nodegoat_at > NOW() - INTERVAL '7 days'
    """)
    stats["nodegoat_sync"]["rate_7d"] = cur.fetchone()[0]

    return stats


def estimate_completion(pending: int, rate_7d: int) -> str:
    """Estimate days to completion based on 7-day rate."""
    if rate_7d == 0:
        return "stalled"
    if pending == 0:
        return "complete"

    days = pending / (rate_7d / 7)
    if days < 1:
        return "< 1 day"
    elif days < 7:
        return f"{days:.1f} days"
    elif days < 30:
        return f"{days/7:.1f} weeks"
    elif days < 365:
        return f"{days/30:.1f} months"
    else:
        return f"{days/365:.1f} years"


def generate_html(stats: dict) -> str:
    """Generate HTML progress page."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for key, data in stats.items():
        total = data["total"]
        completed = data["completed"]
        pending = data["pending"]
        rate_7d = data.get("rate_7d", 0)

        pct = (completed / total * 100) if total > 0 else 0
        eta = estimate_completion(pending, rate_7d)

        # Color based on progress
        if pct >= 100:
            color = "#22c55e"  # green
        elif pct >= 75:
            color = "#3b82f6"  # blue
        elif pct >= 50:
            color = "#eab308"  # yellow
        elif pct >= 25:
            color = "#f97316"  # orange
        else:
            color = "#ef4444"  # red

        rows.append(f"""
        <tr>
            <td><strong>{data['name']}</strong></td>
            <td style="text-align: right;">{completed:,}</td>
            <td style="text-align: right;">{total:,}</td>
            <td>
                <div style="background: #e5e7eb; border-radius: 4px; overflow: hidden; height: 20px;">
                    <div style="background: {color}; width: {pct:.1f}%; height: 100%;"></div>
                </div>
            </td>
            <td style="text-align: right;">{pct:.1f}%</td>
            <td style="text-align: right;">{rate_7d:,}/week</td>
            <td style="text-align: right;"><em>{eta}</em></td>
        </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos Pipeline Progress</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f9fafb;
        }}
        h1 {{
            color: #1f2937;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
        }}
        .updated {{
            color: #6b7280;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            background: #1f2937;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }}
        tr:hover {{
            background: #f9fafb;
        }}
        .note {{
            margin-top: 20px;
            padding: 15px;
            background: #fef3c7;
            border-radius: 8px;
            color: #92400e;
        }}
        a {{
            color: #2563eb;
        }}
    </style>
</head>
<body>
    <h1>Stephanos Pipeline Progress</h1>
    <p class="updated">Last updated: {now}</p>

    <table>
        <thead>
            <tr>
                <th>Stage</th>
                <th style="text-align: right;">Done</th>
                <th style="text-align: right;">Total</th>
                <th style="width: 200px;">Progress</th>
                <th style="text-align: right;">%</th>
                <th style="text-align: right;">Rate</th>
                <th style="text-align: right;">ETA</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>

    <div class="note">
        <strong>Note:</strong> ETA estimates are based on the processing rate over the past 7 days.
        "Stalled" means no progress in the last week. Some stages run with daily limits to control costs.
    </div>

    <p style="margin-top: 20px;">
        <a href="index.html">&larr; Back to main site</a> |
        <a href="progress.html">OCR Progress</a> |
        <a href="statistics.html">Statistics</a>
    </p>
</body>
</html>
"""
    return html


def main():
    print("Generating pipeline progress page...")

    conn = db.get_connection()
    stats = get_progress_stats(conn)
    conn.close()

    html = generate_html(stats)

    # Write to reference_site
    output_path = Path("reference_site/pipeline.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    print(f"Written to {output_path}")

    # Also write JSON for potential API use
    json_path = Path("reference_site/pipeline.json")
    json_path.write_text(json.dumps(stats, indent=2, default=str))
    print(f"JSON written to {json_path}")

    # Print summary
    print("\nPipeline Status:")
    print("-" * 60)
    for key, data in stats.items():
        pct = (data["completed"] / data["total"] * 100) if data["total"] > 0 else 0
        eta = estimate_completion(data["pending"], data.get("rate_7d", 0))
        print(f"  {data['name']:25} {pct:5.1f}%  ({eta})")


if __name__ == "__main__":
    main()
