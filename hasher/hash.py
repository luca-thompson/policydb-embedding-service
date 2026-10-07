import os
from dataclasses import dataclass
import hashlib
from bs4 import BeautifulSoup

@dataclass
class config:
    input_dir: str = "policy_html/"

def strip_html(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "link", "meta", "iframe", "svg"]):
        tag.decompose()

    return str(soup)

def hash_dir(working_dir: str):

    html_file_paths = []

    for path in sorted(os.listdir(working_dir + config.input_dir)):
        html_file_paths.append(path)

    file_contents = []

    for path in html_file_paths:
        file_contents.append(open(working_dir + config.input_dir + path, 'r').read())

    outer = hashlib.sha256()

    for file in file_contents:
        outer.update(strip_html(file).encode('utf-8'))

    return outer.hexdigest()
