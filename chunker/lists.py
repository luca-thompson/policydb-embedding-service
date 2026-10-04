import re

from bs4.element import NavigableString, Tag


def render_list(list_tag, indent=0):
    """Recursively renders <ol>/<ul> as '- ' bullets. Letter/numeral style
    (a/b/c vs i/ii/iii) is CSS-driven and not recovered - only order is kept.

    Walks li.children rather than li.get_text(), so a nested list renders on
    its own indented line instead of being smashed into the parent item,
    while still keeping inline tags like <a> alongside plain text."""
    lines = []
    prefix = "  " * indent + "- "
    for li in list_tag.find_all("li", recursive=False):
        nested = li.find(["ol", "ul"], recursive=False)
        text_parts = []
        for child in li.children:
            if isinstance(child, Tag) and child.name in ("ol", "ul"):
                continue  # rendered separately below
            if isinstance(child, NavigableString):
                text_parts.append(str(child))
            elif isinstance(child, Tag):
                text_parts.append(child.get_text(" ", strip=True))
        direct_text = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
        lines.append(prefix + direct_text)
        if nested:
            lines.append(render_list(nested, indent + 1))
    return "\n".join(l for l in lines if l.strip())
