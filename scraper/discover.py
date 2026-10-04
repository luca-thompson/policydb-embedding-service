import time
import random
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urldefrag
import requests

DOC_ID_RE = re.compile(r"document/view\.php\?id=(\d+)")
NEXT_LINK_HINTS = {"next", "next page", "more", "load more", "»", "›"}

def polite_sleep(delay_min: float, delay_max: float) -> None:
    time.sleep(random.uniform(delay_min, delay_max))


def find_next_page(soup: BeautifulSoup, current_url: str) -> str | None:

    rel_next = soup.find("a", rel="next")
    if rel_next and rel_next.get("href"):
        return urljoin(current_url, rel_next["href"])

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if text in NEXT_LINK_HINTS:
            return urljoin(current_url, a["href"])
    return None


def discover_urls(
    session: requests.Session,
    start_urls: list[str],
    delay_min: float,
    delay_max: float,
) -> dict[str, dict[str, str | bool]]:

    #is_protected is for pages that require login
    #
    found: dict[str, dict[str, str | bool]] = {}
    to_visit = list(dict.fromkeys(start_urls))  # de-dupe, preserve order
    visited: set[str] = set()
    pages_fetched = 0

    while to_visit:
        url, _ = urldefrag(to_visit.pop(0))
        if url in visited:
            continue
        visited.add(url)

        print(f"fetching index page {url}.")
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"Failed to get index page {url}: {exc}.")
            continue
        pages_fetched += 1

        soup = BeautifulSoup(resp.text, "html.parser")
        new_on_this_page = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            m = DOC_ID_RE.search(href)
            if not m:
                continue
            doc_id = m.group(1)
            if doc_id not in found:
                new_on_this_page += 1
            parent_li = a.find_parent("li")
            is_protected = bool(parent_li and parent_li.find("span", class_="document-protected"))
            found[doc_id] = {"url": href, "link_text": a.get_text(strip=True), "is_protected": is_protected}

        next_url = find_next_page(soup, url)
        if next_url and next_url not in visited:
            to_visit.append(next_url)

        polite_sleep(delay_min, delay_max)

    if len(found) < 5:
        print(f"Only found {found}. Something is probably wrong")
    return found
