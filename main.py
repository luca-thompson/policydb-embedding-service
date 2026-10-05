from dataclasses import dataclass
from time import sleep, localtime
import pathlib

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

    print(f"[{localtime}]: Build pipeline beginning")

    if not already_scraped:
        print(f"[{localtime}]: Scraping policy.")
        scrape.scrape_policy(working_dir)

    print(f"[{localtime}]: Stored hash at '{hash_storage_fname}'.")
    store_hash(hash.hash_dir(working_dir), working_dir, hash_storage_fname)

    print(f"[{localtime}]: Chunking policy.")
    chunk.chunk_policy(working_dir)

    print(f"[{localtime}]: Embedding policy.")
    embed.embed_policy(working_dir)


def main():

    print(f"[{localtime}]: Starting Embedding Service.")

    while True:

        stored_hash = get_stored_hash(config.working_dir, config.hash_storage_fname)

        print(f"Found hash: {stored_hash}")

        if stored_hash is None:
            print(f"[{localtime}]: Hash not found, triggering build pipeline.")
            run_embed_pipeline(config.working_dir, False, config.hash_storage_fname)
        else:

            print(f"[{localtime}]: Found hash, scraping then generating new hash.")
            #scrape.scrape_policy(config.working_dir)
            new_hash = hash.hash_dir(config.working_dir)


            if new_hash != stored_hash:
                print(f"[{localtime}]: Hash didnt match, triggering build pipeline.")
                run_embed_pipeline(config.working_dir, True, config.hash_storage_fname)


        sleep(config.sleep)

if __name__ == "__main__":
    main()
