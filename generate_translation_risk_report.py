#!/usr/bin/env python3
"""
Generate a protected HTML report of translation risk gating decisions.
"""
from datetime import datetime, timezone
from pathlib import Path
import html as html_module

from db import get_connection

OUTPUT_PATH = Path("reference_site/protected/translation_risk_report.html")
RISK_CODE = "billerbeck_likely_translation_change"


def fetch_rows(cur):
    cur.execute("SELECT to_regclass('public.translation_risk_flags') IS NOT NULL")
    has_risk = bool(cur.fetchone()[0])
    if not has_risk:
        return []

    cur.execute(
        """
        SELECT
            a.id,
            a.lemma,
            a.billerbeck_id,
            COALESCE(a.translation, (
                SELECT COALESCE(
                    (a.translation_json::json)->>'translation',
                    (a.translation_json::json)->>'english_translation'
                ) WHERE a.translation_json IS NOT NULL
            )) AS translation_text,
            COALESCE(md.translation_impact, '') AS translation_impact,
            COALESCE(md.translation_impact_note, '') AS translation_impact_note,
            COALESCE(md.summary, '') AS difference_summary,
            COALESCE(rf.is_blocked, FALSE) AS is_blocked,
            COALESCE(rf.details_json->>'summary', '') AS block_summary
        FROM assembled_lemmas a
        LEFT JOIN meineke_text_differences md ON md.lemma_id = a.id
        LEFT JOIN LATERAL (
            SELECT trf.is_blocked, trf.details_json, trf.updated_at
            FROM translation_risk_flags trf
            WHERE trf.lemma_id = a.id
              AND trf.variant_kind = 'legacy_assembled'
              AND trf.variant_id = 'translation'
              AND trf.risk_code = %s
            ORDER BY trf.updated_at DESC
            LIMIT 1
        ) rf ON TRUE
        WHERE a.translated = 1
        ORDER BY rf.is_blocked DESC, a.id
        """,
        (RISK_CODE,),
    )
    return cur.fetchall()


def render(rows):
    total = len(rows)
    blocked = sum(1 for row in rows if row[7])
    visible = total - blocked

    body_rows = []
    for (
        lemma_id,
        lemma,
        billerbeck_id,
        translation_text,
        translation_impact,
        translation_impact_note,
        difference_summary,
        is_blocked,
        block_summary,
    ) in rows:
        status = "Blocked" if is_blocked else "Visible"
        reason = block_summary or difference_summary or translation_impact_note
        short_translation = (translation_text or "").strip()
        if len(short_translation) > 220:
            short_translation = short_translation[:219] + "..."

        body_rows.append(
            "<tr>"
            f"<td>{lemma_id}</td>"
            f"<td>{html_module.escape(lemma or '')}</td>"
            f"<td>{html_module.escape(billerbeck_id or '')}</td>"
            f"<td>{html_module.escape(status)}</td>"
            f"<td>{html_module.escape(translation_impact or '')}</td>"
            f"<td>{html_module.escape(reason or '')}</td>"
            f"<td>{html_module.escape(short_translation)}</td>"
            "</tr>"
        )

    rows_html = "\n".join(body_rows) or "<tr><td colspan='7'>No translated entries found.</td></tr>"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Translation Risk Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 24px; background: #f5f5f5; color: #222; }}
    .wrap {{ max-width: 1400px; margin: 0 auto; background: #fff; padding: 24px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    h1 {{ margin-top: 0; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0 20px; }}
    .stat {{ background: #fafafa; border: 1px solid #eee; border-radius: 6px; padding: 12px; }}
    .label {{ color: #666; font-size: 0.9em; }}
    .value {{ font-size: 1.4em; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92em; }}
    th, td {{ border-bottom: 1px solid #eee; text-align: left; vertical-align: top; padding: 10px; }}
    th {{ background: #fafafa; position: sticky; top: 0; }}
    tr:hover td {{ background: #fcfcfc; }}
    .meta {{ color: #666; margin-top: 10px; font-size: 0.9em; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Translation Risk Report</h1>
    <p>Blocked condition: Billerbeck-dependent translation + differences bot indicates likely translation change.</p>
    <div class="stats">
      <div class="stat"><div class="label">Total translated</div><div class="value">{total}</div></div>
      <div class="stat"><div class="label">Blocked</div><div class="value">{blocked}</div></div>
      <div class="stat"><div class="label">Visible</div><div class="value">{visible}</div></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Lemma ID</th>
          <th>Lemma</th>
          <th>Billerbeck ID</th>
          <th>Status</th>
          <th>Impact</th>
          <th>Difference Summary</th>
          <th>Current Translation</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    <div class="meta">Generated: {generated}</div>
  </div>
</body>
</html>
"""


def main():
    conn = get_connection()
    cur = conn.cursor()
    rows = fetch_rows(cur)
    conn.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(rows), encoding="utf-8")
    print(f"Wrote translation risk report: {OUTPUT_PATH}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
