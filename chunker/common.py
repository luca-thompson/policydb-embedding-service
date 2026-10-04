import re

SECTION_HEADING_RE = re.compile(r"^Section\s+\d+\s*-", re.IGNORECASE)


def is_notice_banner(first_section_seen):
    """An <h4> before the first 'Section N - ...' h1 is a document-level
    notice banner, not a real heading. Heuristic, not a certainty."""
    return not first_section_seen


def build_citation(doc_title, breadcrumb_list, clause_number=None):
    """Shared citation-string builder, used by every chunk type so the
    format stays identical no matter which code path produced the chunk."""
    parts = [doc_title] + breadcrumb_list
    if clause_number:
        parts.append(f"clause ({clause_number})")
    return " > ".join(parts)


def is_trivial_text(text):
    """Placeholder-only content ('Nil', 'N/A') that carries no retrievable
    information. A property of the text itself, so every chunk type gets
    checked, not just clauses."""
    return text.strip().rstrip(".").lower() in ("nil", "n/a")
