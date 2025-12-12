#!/usr/bin/env python3
"""
Generate a static HTML progress website showing processing status.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = "stephanos.db"
OUTPUT_FILE = "progress.html"

def get_stats(conn):
    """Get processing statistics"""
    # Total counts
    total_row = conn.execute("SELECT COUNT(*), SUM(processed), SUM(tokens_used) FROM images").fetchone()
    total_images = total_row[0]
    processed_images = total_row[1] or 0
    total_tokens = total_row[2] or 0

    # Today's tokens
    today = datetime.utcnow().date().isoformat()
    today_tokens = conn.execute(
        "SELECT COALESCE(SUM(tokens_used), 0) FROM images WHERE DATE(processed_at) = ?",
        (today,)
    ).fetchone()[0]

    # Recent processed images
    recent = conn.execute(
        """
        SELECT image_filename, processed_at, tokens_used,
               LENGTH(lemma_json) as json_length
        FROM images
        WHERE processed = 1
        ORDER BY processed_at DESC
        LIMIT 20
        """,
    ).fetchall()

    return {
        'total_images': total_images,
        'processed_images': processed_images,
        'remaining_images': total_images - processed_images,
        'progress_percent': (processed_images / total_images * 100) if total_images > 0 else 0,
        'total_tokens': total_tokens,
        'today_tokens': today_tokens,
        'avg_tokens_per_image': (total_tokens / processed_images) if processed_images > 0 else 0,
        'recent_images': recent
    }

def generate_html(stats):
    """Generate HTML page"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stephanos Processing Progress</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 40px;
            background: #f8f9fa;
        }}
        .stat-card {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .progress-bar {{
            margin: 40px;
        }}
        .progress-bar-label {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-weight: 500;
        }}
        .progress-bar-container {{
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
        }}
        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 15px;
            color: white;
            font-weight: bold;
        }}
        .recent-table {{
            margin: 40px;
        }}
        .recent-table h2 {{
            margin-bottom: 20px;
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 500;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .filename {{
            font-family: monospace;
            font-size: 0.9em;
        }}
        .timestamp {{
            color: #666;
            font-size: 0.9em;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Stephanos Processing Progress</h1>
            <p>Billerbeck 2006 Edition - Image Extraction Pipeline</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total Images</div>
                <div class="stat-value">{stats['total_images']:,}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Processed</div>
                <div class="stat-value">{stats['processed_images']:,}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Remaining</div>
                <div class="stat-value">{stats['remaining_images']:,}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Tokens Used</div>
                <div class="stat-value">{stats['total_tokens']:,}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Today's Tokens</div>
                <div class="stat-value">{stats['today_tokens']:,}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Avg Tokens/Image</div>
                <div class="stat-value">{stats['avg_tokens_per_image']:,.0f}</div>
            </div>
        </div>

        <div class="progress-bar">
            <div class="progress-bar-label">
                <span>Overall Progress</span>
                <span>{stats['progress_percent']:.1f}%</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: {stats['progress_percent']}%;">
                    {stats['processed_images']} / {stats['total_images']}
                </div>
            </div>
        </div>

        <div class="recent-table">
            <h2>Recently Processed Images</h2>
            <table>
                <thead>
                    <tr>
                        <th>Image Filename</th>
                        <th>Processed At</th>
                        <th>Tokens Used</th>
                        <th>JSON Size</th>
                    </tr>
                </thead>
                <tbody>
"""

    for row in stats['recent_images']:
        filename, processed_at, tokens, json_len = row
        # Format timestamp
        try:
            dt = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
            formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            formatted_time = processed_at

        html += f"""
                    <tr>
                        <td class="filename">{filename}</td>
                        <td class="timestamp">{formatted_time}</td>
                        <td>{tokens:,}</td>
                        <td>{json_len:,} bytes</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Last updated: """ + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC') + """</p>
            <p>Pipeline: HTML → SQLite → OpenAI Vision (gpt-4o-mini) → Structured JSON</p>
        </div>
    </div>
</body>
</html>
"""
    return html

def main():
    conn = sqlite3.connect(DB_PATH)
    stats = get_stats(conn)
    conn.close()

    html = generate_html(stats)

    output_path = Path(OUTPUT_FILE)
    output_path.write_text(html, encoding='utf-8')

    print(f"Progress website generated: {output_path.absolute()}")
    print(f"  Processed: {stats['processed_images']} / {stats['total_images']} ({stats['progress_percent']:.1f}%)")
    print(f"  Total tokens: {stats['total_tokens']:,}")
    print(f"  Today's tokens: {stats['today_tokens']:,}")

if __name__ == "__main__":
    main()
