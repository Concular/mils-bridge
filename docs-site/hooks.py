"""MkDocs hooks for the public documentation site.

The pages under docs/ are written for reading on GitHub, where
`../spec/mils-internal.yaml` is a file next to docs/. MkDocs only publishes
what is inside docs_dir, so this hook:

  1. publishes spec/mils-internal.yaml at /spec/mils-internal.yaml, and
  2. rewrites the pages' `../spec/` links to that published copy.

Nothing under docs/ or spec/ is modified on disk — the generated pages stay
byte-for-byte what the sync wrote.
"""

from __future__ import annotations

import os
import re

from mkdocs.structure.files import File, Files

SPEC = "spec/mils-internal.yaml"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC_LINK = re.compile(r"\]\((?:\.\./)+spec/")


def on_files(files: Files, config) -> Files:
    files.append(
        File.generated(config, SPEC, abs_src_path=os.path.join(_ROOT, SPEC))
    )
    return files


def on_page_markdown(markdown: str, page, config, files) -> str:
    # Every page lives at the docs root, so the published copy is `spec/…`
    # relative to the page's source file.
    depth = page.file.src_uri.count("/")
    return _SPEC_LINK.sub("](" + "../" * depth + "spec/", markdown)
