#!/usr/bin/env python3
"""Shared navigation for generated Stephanos site pages."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    path: str
    protected: bool = False


@dataclass(frozen=True)
class MenuSection:
    key: str
    label: str
    items: tuple[MenuItem, ...]


MENU_SECTIONS: tuple[MenuSection, ...] = (
    MenuSection(
        "translations",
        "Translations",
        (
            MenuItem("reference", "Reference Home", "index.html"),
            MenuItem("word_index", "Word Index", "word_index.html"),
            MenuItem("lemma_index", "Lemma Index", "lemma_index.html"),
            MenuItem("guidance", "Translation Guidance Rules", "translation_guidance.html"),
        ),
    ),
    MenuSection(
        "sources",
        "Sources & Citations",
        (
            MenuItem("sources", "Ancient Sources", "sources.html"),
            MenuItem("works", "Works Cited", "works.html"),
            MenuItem("fgrhist", "FGrHist Index", "fgrhist.html"),
        ),
    ),
    MenuSection(
        "extracted",
        "Extracted Information",
        (
            MenuItem("map", "Places Map", "map.html"),
            MenuItem("entities", "People & Deities", "entities.html"),
            MenuItem("peoples", "Ethnic Groups", "peoples.html"),
            MenuItem("aliases", "Alias Review", "aliases.html"),
            MenuItem("topostext_authority_status", "ToposText Entity Status", "topostext_authority_status.html"),
            MenuItem("topostext_review", "ToposText Review Queue", "topostext_review.html"),
            MenuItem("topostext_history", "ToposText Change History", "topostext_history.html"),
            MenuItem("topostext_intake", "ToposText Intake Report", "topostext_intake_report.html"),
        ),
    ),
    MenuSection(
        "analysis",
        "Statistics & Analysis",
        (
            MenuItem("statistics", "Overview", "statistics.html"),
            MenuItem("word_count_stats", "Word Counts", "statistics/word_count.html"),
            MenuItem("translation_length", "Translation Length", "statistics/translation_length.html"),
            MenuItem("prompt_eval", "Prompt Evaluation", "statistics/prompt_evaluation.html"),
            MenuItem("translation_quality_predictor", "Translation Quality Predictor", "statistics/translation_quality_predictor.html"),
            MenuItem("guidance_stats", "Guidance Rule Statistics", "statistics/guidance_rules.html"),
            MenuItem("fingerprinting", "Stylometric Fingerprinting", "statistics/fingerprinting.html"),
            MenuItem("vocabulary_signatures", "Vocabulary Signatures", "statistics/vocabulary_signatures.html"),
            MenuItem("regression", "Stephanos vs Epitomizer", "statistics/regression.html"),
            MenuItem("categories", "Categories", "statistics/categories.html"),
            MenuItem("etymology", "Etymology", "statistics/etymology.html"),
            MenuItem("parisinus", "Parisinus Comparison", "statistics/parisinus_comparison.html"),
            MenuItem("pausanias", "Pausanias Citations", "statistics/pausanias_analysis.html"),
        ),
    ),
    MenuSection(
        "editing",
        "Editing Tools",
        (
            MenuItem("review", "Translation Review", "cgi-bin/review.cgi", protected=True),
            MenuItem("final_review", "Final Workspace", "cgi-bin/final_review.cgi", protected=True),
            MenuItem("entity_review", "Entity Resolution", "cgi-bin/entities.cgi", protected=True),
            MenuItem("guidance_editor", "Guidance Editor", "cgi-bin/guidance.cgi", protected=True),
            MenuItem("guidance_impacts", "Guidance Rule Impacts", "cgi-bin/guidance_impacts.cgi", protected=True),
            MenuItem("brady_review", "ToposText Intake Review", "protected/brady_entity_review.html", protected=True),
        ),
    ),
    MenuSection(
        "operations",
        "Operations",
        (
            MenuItem("pipeline", "Pipeline Status", "pipeline.html"),
            MenuItem("translation_operations", "Translation Operations", "statistics/translation_operations.html"),
            MenuItem("page_scans", "Page Scans", "protected/", protected=True),
            MenuItem("text_comparison", "Greek Text Review", "protected/meineke_comparison.html", protected=True),
            MenuItem("difference_analysis", "Text Difference Analysis", "protected/meineke_difference_analysis.html", protected=True),
            MenuItem("scan_diagnostics", "Scan Diagnostics", "protected/meineke_holes_report.html", protected=True),
            MenuItem("translation_risk", "Translation Risk Report", "protected/translation_risk_report.html", protected=True),
            MenuItem("clustering", "Headword Clustering", "protected/clustering.html", protected=True),
            MenuItem("entity_resolution_report", "Entity Review Report", "protected/entity_resolution_review.html", protected=True),
        ),
    ),
    MenuSection(
        "downloads",
        "Downloads & Project",
        (
            MenuItem("downloads", "Downloads", "downloads.html"),
            MenuItem("pdf_book", "PDF Book", "stephanos_ethnika_translations.pdf"),
        ),
    ),
)


def site_navigation_styles() -> str:
    """Return CSS for the shared dropdown menu."""
    return """
        .site-menu {
            align-items: stretch;
            background: #ffffff;
            border: 1px solid #d8e0ec;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(20, 36, 58, 0.08);
            display: flex;
            flex-wrap: wrap;
            gap: 0;
            justify-content: space-between;
            margin: 0 0 18px;
            position: relative;
            z-index: 20;
        }
        .site-menu a {
            text-decoration: none;
        }
        .site-menu-brand {
            align-items: center;
            color: #0d47a1;
            display: inline-flex;
            font-weight: 700;
            min-height: 44px;
            padding: 0 14px;
            white-space: nowrap;
        }
        .site-menu-groups {
            display: flex;
            flex: 1;
            flex-wrap: wrap;
            justify-content: flex-end;
            min-width: 0;
        }
        .site-menu-section {
            position: relative;
        }
        .site-menu-section summary {
            align-items: center;
            color: #24364f;
            cursor: pointer;
            display: flex;
            font-size: 0.9rem;
            font-weight: 650;
            gap: 6px;
            list-style: none;
            min-height: 44px;
            padding: 0 9px;
            white-space: nowrap;
        }
        .site-menu-section summary::-webkit-details-marker {
            display: none;
        }
        .site-menu-section summary::after {
            color: #6f7f96;
            content: "\\25BE";
            font-size: 0.72rem;
        }
        .site-menu-section[open] summary,
        .site-menu-section.is-current summary {
            background: #eef4ff;
            color: #0d47a1;
        }
        .site-menu-panel {
            background: #ffffff;
            border: 1px solid #d8e0ec;
            border-radius: 8px;
            box-shadow: 0 14px 30px rgba(20, 36, 58, 0.16);
            display: grid;
            gap: 2px;
            min-width: 235px;
            padding: 8px;
            position: absolute;
            right: 0;
            top: calc(100% + 4px);
        }
        .site-menu-item {
            border-radius: 6px;
            color: #213248;
            display: block;
            font-weight: 550;
            line-height: 1.35;
            padding: 8px 10px;
        }
        .site-menu-item:hover,
        .site-menu-item:focus {
            background: #f1f5fb;
            color: #0d47a1;
            outline: none;
        }
        .site-menu-item.is-current {
            background: #e7f0ff;
            color: #0d47a1;
        }
        .site-menu-protected {
            color: #6b7280;
            display: block;
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 2px;
        }
        .site-breadcrumbs {
            color: #5d6a7d;
            font-size: 0.94rem;
            margin: 0 0 14px;
        }
        .site-breadcrumbs a {
            color: #0d47a1;
            font-weight: 600;
            text-decoration: none;
        }
        .site-breadcrumbs a:hover {
            text-decoration: underline;
        }
        @media (max-width: 760px) {
            .site-menu {
                display: block;
            }
            .site-menu-brand {
                border-bottom: 1px solid #e3e8f0;
                display: flex;
            }
            .site-menu-groups {
                display: block;
            }
            .site-menu-section summary {
                border-bottom: 1px solid #edf1f7;
                justify-content: space-between;
            }
            .site-menu-panel {
                border: 0;
                border-bottom: 1px solid #edf1f7;
                border-radius: 0;
                box-shadow: none;
                min-width: 0;
                padding: 6px 10px 10px;
                position: static;
            }
        }
    """


def _link_for(path: str, depth: int = 0, absolute: bool = False) -> str:
    if path.startswith(("http://", "https://", "#")):
        return path
    if absolute:
        return "/" + path.lstrip("/")
    return "../" * max(depth, 0) + path.lstrip("/")


def render_site_navigation(
    current_section: str | None = None,
    current_item: str | None = None,
    *,
    depth: int = 0,
    absolute_links: bool = False,
    protected_suffix: str = "[Password protected]",
) -> str:
    """Render the shared dropdown menu.

    `depth` is the directory depth below the deployed site root: pages in
    `reference_site/statistics/` and `reference_site/protected/` use depth 1.
    CGI templates should pass `absolute_links=True`.
    """
    groups = []
    for section in MENU_SECTIONS:
        section_classes = ["site-menu-section"]
        if section.key == current_section:
            section_classes.append("is-current")
        items = []
        for item in section.items:
            item_classes = ["site-menu-item"]
            if item.key == current_item:
                item_classes.append("is-current")
            protected = (
                f'<span class="site-menu-protected">{escape(protected_suffix)}</span>'
                if item.protected
                else ""
            )
            href = escape(_link_for(item.path, depth=depth, absolute=absolute_links), quote=True)
            items.append(
                f'<a class="{" ".join(item_classes)}" href="{href}">'
                f"{escape(item.label)}{protected}</a>"
            )
        groups.append(
            f'<details class="{" ".join(section_classes)}">'
            f"<summary>{escape(section.label)}</summary>"
            f'<div class="site-menu-panel">{"".join(items)}</div>'
            "</details>"
        )

    brand_href = escape(_link_for("index.html", depth=depth, absolute=absolute_links), quote=True)
    return (
        '<nav class="site-menu" aria-label="Main navigation">'
        f'<a class="site-menu-brand" href="{brand_href}">Stephanos - Ethnika</a>'
        f'<div class="site-menu-groups">{"".join(groups)}</div>'
        "</nav>"
    )


def render_site_breadcrumbs(
    crumbs: Iterable[tuple[str, str | None]],
    *,
    depth: int = 0,
    absolute_links: bool = False,
) -> str:
    parts = []
    for label, path in crumbs:
        if path:
            href = escape(_link_for(path, depth=depth, absolute=absolute_links), quote=True)
            parts.append(f'<a href="{href}">{escape(label)}</a>')
        else:
            parts.append(f"<span>{escape(label)}</span>")
    return f'<nav class="site-breadcrumbs" aria-label="Breadcrumb">{" / ".join(parts)}</nav>'
