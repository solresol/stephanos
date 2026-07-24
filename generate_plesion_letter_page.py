#!/usr/bin/env python3
"""Publish the dated πλησίον-by-letter research snapshot on the reference site."""

from __future__ import annotations

import argparse
import csv
import html
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

from site_navigation import render_site_navigation, site_navigation_styles


DEFAULT_SOURCE_CSV = Path("paper/figures/plesion-headword-rate-by-letter.csv")
DEFAULT_SOURCE_PNG = Path("paper/figures/plesion-headword-rate-by-letter.png")
DEFAULT_OUTPUT = Path("reference_site/statistics/plesion_by_letter.html")
DEFAULT_ASSET_DIR = Path("reference_site/statistics_images")
SNAPSHOT_DATE = "2026-06-20"


@dataclass(frozen=True)
class LetterRate:
    letter: str
    headwords: int
    plesion_headwords: int
    rate: float

    @property
    def percent(self) -> float:
        return self.rate * 100.0


def load_letter_rates(path: Path) -> list[LetterRate]:
    """Load and validate the committed chart data."""
    rows: list[LetterRate] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"letter", "headwords", "plesion_headwords", "rate"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        for raw in reader:
            row = LetterRate(
                letter=(raw["letter"] or "").strip(),
                headwords=int(raw["headwords"]),
                plesion_headwords=int(raw["plesion_headwords"]),
                rate=float(raw["rate"]),
            )
            if not row.letter:
                raise ValueError(f"{path} contains a row without a letter")
            if row.headwords <= 0:
                raise ValueError(f"{path}: {row.letter} has no headwords")
            if not 0 <= row.plesion_headwords <= row.headwords:
                raise ValueError(f"{path}: invalid πλησίον count for {row.letter}")
            expected_rate = row.plesion_headwords / row.headwords
            if not math.isclose(row.rate, expected_rate, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"{path}: rate does not match counts for {row.letter}")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no data rows")
    return rows


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Return the two-sided Fisher exact p-value for a 2x2 table."""
    first_row = a + b
    second_row = c + d
    successes = a + c
    total = first_row + second_row
    denominator = math.comb(total, successes)

    def probability(value: int) -> float:
        return (
            math.comb(first_row, value)
            * math.comb(second_row, successes - value)
            / denominator
        )

    lower = max(0, successes - second_row)
    upper = min(first_row, successes)
    observed = probability(a)
    return sum(
        probability(value)
        for value in range(lower, upper + 1)
        if probability(value) <= observed + 1e-15
    )


def render_rate_table(rows: list[LetterRate]) -> str:
    body = []
    for row in rows:
        emphasis = ' class="kappa-row"' if row.letter == "Κ" else ""
        body.append(
            f"""            <tr{emphasis}>
                <th scope="row">{html.escape(row.letter)}</th>
                <td>{row.headwords:,}</td>
                <td>{row.plesion_headwords:,}</td>
                <td>{row.percent:.2f}%</td>
            </tr>"""
        )
    return "\n".join(body)


def build_page(rows: list[LetterRate], *, image_name: str, csv_name: str) -> str:
    total_headwords = sum(row.headwords for row in rows)
    total_plesion = sum(row.plesion_headwords for row in rows)
    corpus_percent = 100.0 * total_plesion / total_headwords

    kappa = next((row for row in rows if row.letter == "Κ"), None)
    if kappa is None:
        raise ValueError("The snapshot does not contain a Kappa row")
    rest_headwords = total_headwords - kappa.headwords
    rest_plesion = total_plesion - kappa.plesion_headwords
    p_value = fisher_exact_two_sided(
        kappa.plesion_headwords,
        kappa.headwords - kappa.plesion_headwords,
        rest_plesion,
        rest_headwords - rest_plesion,
    )
    odds_ratio = (
        kappa.plesion_headwords
        * (rest_headwords - rest_plesion)
        / ((kappa.headwords - kappa.plesion_headwords) * rest_plesion)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>πλησίον by Headword Starting Letter - Stephanos Statistics</title>
    <style>
        {site_navigation_styles()}
        body {{
            background: #f7f9fc;
            color: #24364f;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.55;
            margin: 0 auto;
            max-width: 1180px;
            padding: 20px;
        }}
        h1, h2 {{ color: #17233a; }}
        .summary {{
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            margin: 18px 0;
        }}
        .metric {{
            background: #ffffff;
            border: 1px solid #d8e0ec;
            border-radius: 6px;
            padding: 14px;
        }}
        .metric strong {{
            color: #0d47a1;
            display: block;
            font-size: 1.45rem;
        }}
        .panel {{
            background: #ffffff;
            border: 1px solid #d8e0ec;
            border-radius: 8px;
            margin: 18px 0;
            padding: 18px;
        }}
        .chart {{
            border: 1px solid #d8e0ec;
            display: block;
            height: auto;
            margin: 16px 0;
            max-width: 100%;
        }}
        .downloads {{ display: flex; flex-wrap: wrap; gap: 16px; }}
        .downloads a {{ color: #0d47a1; font-weight: 650; }}
        .table-wrap {{ overflow-x: auto; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{
            border-bottom: 1px solid #e3e8f1;
            padding: 8px 10px;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}
        th:first-child, td:first-child {{ text-align: left; }}
        thead th {{ background: #eef4ff; color: #17345f; }}
        .kappa-row {{ background: #fff0ed; }}
        .note {{ color: #5f6f86; font-size: 0.95rem; }}
    </style>
</head>
<body>
    {render_site_navigation("analysis", "plesion_by_letter", depth=1)}
    <h1>πλησίον by Headword Starting Letter</h1>
    <p>
        This is the dated corpus snapshot used for the chart circulated on
        20 June 2026. It measures how often an entry contains πλησίον, grouped
        by the first letter of its headword.
    </p>

    <div class="summary">
        <div class="metric"><strong>{total_headwords:,}</strong>headwords</div>
        <div class="metric"><strong>{total_plesion:,}</strong>with πλησίον</div>
        <div class="metric"><strong>{corpus_percent:.2f}%</strong>corpus rate</div>
        <div class="metric"><strong>{kappa.plesion_headwords}/{kappa.headwords}</strong>Kappa ({kappa.percent:.2f}%)</div>
    </div>

    <div class="panel">
        <h2>Chart</h2>
        <a href="../statistics_images/{html.escape(image_name)}">
            <img class="chart" src="../statistics_images/{html.escape(image_name)}"
                 alt="Bar chart of πλησίον headword rates by Greek starting letter">
        </a>
        <div class="downloads">
            <a href="../statistics_images/{html.escape(image_name)}" download>Download PNG</a>
            <a href="../statistics_images/{html.escape(csv_name)}" download>Download CSV figures</a>
        </div>
    </div>

    <div class="panel">
        <h2>Letter Figures</h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th scope="col">Letter</th>
                        <th scope="col">Headwords</th>
                        <th scope="col">Headwords with πλησίον</th>
                        <th scope="col">Rate</th>
                    </tr>
                </thead>
                <tbody>
{render_rate_table(rows)}
                </tbody>
            </table>
        </div>
    </div>

    <div class="panel">
        <h2>Interpretation</h2>
        <p>
            Kappa has {kappa.plesion_headwords} πλησίον headwords among
            {kappa.headwords} entries ({kappa.percent:.2f}%), compared with
            {rest_plesion} among {rest_headwords:,} entries outside Kappa
            ({100.0 * rest_plesion / rest_headwords:.2f}%).
            The Kappa odds ratio is {odds_ratio:.2f}; a two-sided Fisher exact
            test gives <em>p</em> = {p_value:.4f}.
        </p>
        <p class="note">
            This supports a Kappa skew in this snapshot, not by itself a claim
            that Kappa had a different epitomiser. High rates for letters with
            small denominators, especially Zeta (2/18), should not be read as
            stable letter effects.
        </p>
    </div>

    <div class="panel">
        <h2>Method</h2>
        <p>
            Unit: one headword. Source: one current public Greek text per
            headword at the snapshot date, using project priority Kiesling
            before Meineke. A headword counts when its normalized Greek text
            contains πλησίον. Reciprocal ἀλλήλων πλησίον is excluded. The
            starting letter comes from the Billerbeck identifier when present,
            with the Greek lemma as fallback.
        </p>
        <p class="note">
            Snapshot date: {SNAPSHOT_DATE}. The site build republishes the
            committed PNG and CSV so the cited figures remain stable as the
            live corpus changes.
        </p>
    </div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the dated πλησίον-by-letter snapshot on the reference site."
    )
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--source-png", type=Path, default=DEFAULT_SOURCE_PNG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--asset-dir", type=Path, default=DEFAULT_ASSET_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source_png.is_file():
        raise FileNotFoundError(f"Chart image not found: {args.source_png}")
    rows = load_letter_rates(args.source_csv)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.asset_dir.mkdir(parents=True, exist_ok=True)
    published_png = args.asset_dir / args.source_png.name
    published_csv = args.asset_dir / args.source_csv.name
    shutil.copy2(args.source_png, published_png)
    shutil.copy2(args.source_csv, published_csv)

    page = build_page(
        rows,
        image_name=published_png.name,
        csv_name=published_csv.name,
    )
    args.output.write_text(page, encoding="utf-8")
    print(f"πλησίον letter page written to {args.output}")
    print(f"Chart published to {published_png}")
    print(f"Figures published to {published_csv}")


if __name__ == "__main__":
    main()
