#!/usr/bin/env python3
"""
Compatibility entry point for the retired root progress page.

The status report now has one generated HTML surface:
`reference_site/pipeline.html`.
"""

from generate_pipeline_progress import main


if __name__ == "__main__":
    main()
