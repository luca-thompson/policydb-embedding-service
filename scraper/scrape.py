
from dataclasses import dataclass
import os

from .discover import discover_urls
from .download import download_policies

@dataclass
class config:
    out_dir: str = "policy_html/"
    browse_url: str = "https://policies.latrobe.edu.au/browse"
    delay_min: float = 0
    delay_max: float = 0.001

USER_AGENT = (
    "LaTrobeCapstonePolicyDBBot/0.1 "
    "(La Trobe capstone project - Policy DB Chatbot; academic use; "
    "scraping authorised by client; contact: <team contact email here>)"
)

def resolve_targets(session):

    found = discover_urls(session, [config.browse_url], config.delay_min, config.delay_max)
    print(f"Discovered {len(found)} policies.")

    items = list(found.items())

    return items


def scrape_policy(working_dir):
    os.makedirs(working_dir + config.out_dir, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    items = resolve_targets(session)

    download_policies(session, items, config.out_dir, config.delay_min, config.delay_max)
