from dataclasses import dataclass
import json
import os
from .document import chunk_policy_html

@dataclass
class config:
    input_dir: str = "/policy_html/"
    output_dir: str = "/policy_json/"


def process_one(html_path, out_dir):
    result = chunk_policy_html(html_path)
    out_path = out_dir + html_path.split("/")[3].split(".")[0] + ".chunk.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

def chunk_policy(working_dir: str):

    if not os.path.exists(working_dir + config.output_dir):
        os.makedirs(working_dir + config.output_dir)

    paths = os.listdir(working_dir + config.input_dir)

    if not paths:
        print("No files found in input dir.")

    for path in paths:
        process_one(working_dir + config.input_dir + path, working_dir + config.output_dir)

    print(f"\n{len(paths)} document(s) processed")
