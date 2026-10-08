# policydb-embedding-service

This is a "service" that creates vector databases out of Latrobe policy. At set intervals it checks if policy content has changed, automatically rebuilding the db if it has.

### Installation

Clone the repo:
```bash
git clone https://github.com/luca-thompson/policydb-embedding-service.git
```

Install python requirements:
```bash
pip install -r requirements.txt
```

### Running
```bash
python main.py
```

### Configuration
Each configurable part of the service has a config dataclass at the top of its file. For example, to change time between corpus re-checks for the main service edit the "sleep" parameter.

### Components

**Scraper**
This components role is to go to the 'browse' page of Latrobe's policy website and download all policy documents it can find there.

**Hasher**
The hasher simply looks in the directory where all policy has been scraped to and hashes all the policy content available. It strips all dynamic content before doing so.

**Chunker**
Chunking is the process of walking through policy and carefully breaking it up into smaller 'chunks', ready for embedding.

**Embedder**
The embedder simply goes through the generated json files, in small-ish batches, and embeds each chunk into the Chroma vector database.
