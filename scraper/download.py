import re
from bs4 import BeautifulSoup
import requests
import random, time

LOGIN_PAGE_HINTS = ("please log in", "please login", "sign in to continue", "authentication required")


def slugify(text: str, max_len: int = 80) -> str:
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^A-Za-z0-9_\-]", "", text)
    return text[:max_len] or "untitled"


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        # Trim common site-name suffixes like "... - Document - La Trobe Policy Library"
        return re.split(r"\s*-\s*Document\s*-\s*", soup.title.string.strip())[0].strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "untitled"


def fetch_policy(
    session: requests.Session,
    doc_id: str,
    url: str,
    out_dir: str,
    working_dir: str,
    is_protected: bool = False,
):
    record = {
        "id": doc_id, "url": url, "title": "", "filename": "", "status": ""
    }

    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"{doc_id} fetch failed: {exc}.")
        record.update({"status": "failed"})
        return record

    soup = BeautifulSoup(resp.text, "html.parser")
    title = extract_title(soup)
    filename = f"{doc_id}_{slugify(title)}.html"
    out_path = out_dir + filename
    with open(out_path, 'w', encoding="utf-8") as f:
        f.writelines(resp.text)

    body_text_lower = soup.get_text(" ", strip=True).lower()
    looks_like_login = any(hint in body_text_lower for hint in LOGIN_PAGE_HINTS)
    if is_protected or looks_like_login:
        status = "downloaded_flagged"
    else:
        status = "downloaded"

    record.update({
        "title": title,
        "filename": filename,
        "status": status,
    })
    if status == "downloaded":
        print(f"{doc_id} saved: {filename}")
    return record

def polite_sleep(delay_min: float, delay_max: float) -> None:
    time.sleep(random.uniform(delay_min, delay_max))

def download_policies(session, items, out_dir, delay_min, delay_max):
    for doc_id, info in items:
        _ = fetch_policy(session, doc_id, info["url"], out_dir, info.get("is_protected", False))
        polite_sleep(delay_min, delay_max)
