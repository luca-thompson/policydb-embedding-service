from dataclasses import dataclass
from time import sleep
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
        print("IO error: couldnt read from hash storage file")
        quit()

def store_hash(hash:str, working_dir: str, hash_storage_fname: str):
    try:
        with open(working_dir + hash_storage_fname, 'w') as f:

            f.write(hash)

    except IOError:
        print("IO error: couldnt write to hash file")
        quit()


def run_embed_pipeline(working_dir: str, already_scraped: bool, hash_storage_fname):

    if not already_scraped:
         scrape.scrape_policy(working_dir)

    store_hash(hash.hash_dir(working_dir), working_dir, hash_storage_fname)

    chunk.chunk_policy(working_dir)

    embed.embed_policy(working_dir)


def main():

    while True:

        stored_hash = get_stored_hash(config.working_dir, config.hash_storage_fname)

        print(f"current hash: {hash}")

        if hash is None:
            run_embed_pipeline(config.working_dir, False, config.hash_storage_fname)
        else:

            scrape(config.working_dir)
            new_hash = generate_hash(config.working_dir)

            if new_hash != stored_hash:
                run_embed_pipeline(config.working_dir, True, config.hash_storage_fname)


        sleep(config.sleep)
