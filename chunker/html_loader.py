import re
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Comment

POLICY_ID_RE = re.compile(r"[?&]id=(\d+)")


def load_soup(html_path):
    with open(html_path, encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f, "html.parser")
    for tag in soup(["style", "script"]):
        tag.decompose()

    # Comment subclasses NavigableString in bs4, so MS Office paste artifacts
    # like <!--StartFragment--> leak into rendered text unless stripped first.
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Normalize nbsp to a regular space on every text node right after parse.
    # get_text(strip=True) only trims leading/trailing whitespace, so an
    # nbsp sitting mid-sentence would otherwise pass straight through.
    for text_node in soup.find_all(string=True):
        if "\xa0" in text_node:
            text_node.replace_with(text_node.replace("\xa0", " "))
    return soup


def extract_policy_id(soup, fallback_path=None):
    """Prefer the canonical id from the 'Current Version' nav link over the
    filename, since filenames can be renamed by whoever downloaded them."""
    link = soup.find("a", href=re.compile(r"document/view\.php\?id="))
    if link:
        m = POLICY_ID_RE.search(link["href"])
        if m:
            return m.group(1)
    if fallback_path:
        m = re.match(r"^(\d+)_", Path(fallback_path).name)
        if m:
            return m.group(1)
    return None


def extract_doc_title(soup):
    title_el = soup.find(id="sliph-document-title")
    if title_el:
        return title_el.get_text(strip=True)
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "UNKNOWN_TITLE"
