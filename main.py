from dataclasses import dataclass
from time import sleep
import pathlib
import datetime

from scraper import scrape
from hasher import hash
from chunker import chunk
from embedder import embed

@dataclass
class config:
    working_dir: str = str(pathlib.Path(__file__).parent.resolve()) + "/output/"
    sleep: int = 3600
    hash_storage_fname: str = "hash.txt"

def get_stored_hash(working_dir: str, hash_storage_fname: str):
    try:
        with open(working_dir + hash_storage_fname, 'r') as f:

            return f.read()

    except IOError:
        return None

def store_hash(hash:str, working_dir: str, hash_storage_fname: str):
    try:
        with open(working_dir + hash_storage_fname, 'w') as f:

            f.write(hash)

    except IOError:
        print("IO error: couldnt write to hash file")
        quit()


def run_embed_pipeline(working_dir: str, already_scraped: bool, hash_storage_fname):

    print(f"[{str(datetime.datetime.now())}]: Build pipeline beginning")

    if not already_scraped:
        print(f"[{str(datetime.datetime.now())}]: Scraping policy.")
        scrape.scrape_policy(working_dir)

    print(f"[{str(datetime.datetime.now())}]: Stored hash at '{hash_storage_fname}'.")
    store_hash(hash.hash_dir(working_dir), working_dir, hash_storage_fname)

    print(f"[{str(datetime.datetime.now())}]: Chunking policy.")
    chunk.chunk_policy(working_dir)

    print(f"[{str(datetime.datetime.now())}]: Embedding policy.")
    embed.embed_policy(working_dir)


def main():

    print(f"[{str(datetime.datetime.now())}]: Starting Embedding Service.")

    while True:

        stored_hash = get_stored_hash(config.working_dir, config.hash_storage_fname)

        print(f"Found hash: {stored_hash}")

        if stored_hash is None:
            print(f"[{str(datetime.datetime.now())}]: Hash not found, triggering build pipeline.")
            run_embed_pipeline(config.working_dir, False, config.hash_storage_fname)
        else:

            print(f"[{str(datetime.datetime.now())}]: Found hash, scraping then generating new hash.")
            scrape.scrape_policy(config.working_dir)
            new_hash = hash.hash_dir(config.working_dir)


            if new_hash != stored_hash:
                print(f"[{str(datetime.datetime.now())}]: Hash didnt match, triggering build pipeline.")
                run_embed_pipeline(config.working_dir, True, config.hash_storage_fname)


        sleep(config.sleep)

if __name__ == "__main__":
    main()
