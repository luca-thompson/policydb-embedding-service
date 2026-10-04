
from dataclasses import dataclass
import os
import requests

from discover import discover_urls
from download import download_policies


USER_AGENT = (
    "LaTrobeCapstonePolicyDBBot/0.1 "
    "(La Trobe capstone project - Policy DB Chatbot; academic use; "
    "scraping authorised by client; contact: <team contact email here>)"
)

@dataclass
class config:
    out_dir: str = "../output/policy_html/"
    browse_url: str = "https://policies.latrobe.edu.au/browse"
    delay_min: float = 0
    delay_max: float = 0.001
    

def resolve_targets(session):

    found = discover_urls(session, [config.browse_url], config.delay_min, config.delay_max)
    print(f"Discovered {len(found)} policies.")

    items = list(found.items())

    return items


def main():
    os.makedirs(config.out_dir, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    items = resolve_targets(session)

    download_policies(session, items, config.out_dir, config.delay_min, config.delay_max)

if __name__ == "__main__":
    main()
