from dataclasses import dataclass
import json
import re
import sys
import os

from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb

@dataclass
class config:
    input_dir = "../output/policy_json/"
    output_dir = "../output/chroma_db/"
    embedding_model = "BAAI/bge-m3"
    device = "cuda" #cpu, cuda etc.
    collection_name = "policydb"
    batch_size = 32


def normalize_key(key: str) -> str:
    """Turn an arbitrary metadata_table key into a clean snake_case string.
    e.g. 'Accountable Executive - Policy' -> 'accountable_executive_policy'
    """
    key = key.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key or "field"


def load_document_metadata(input_dir) -> dict:
    lookup = {}

    files = sorted(os.listdir(input_dir))
    for fp in files:
        try:
            with open(input_dir + fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] could not read {fp}: {e}", file=sys.stderr)
            continue

        doc = data.get("document") or {}
        policy_id = doc.get("policy_id")
        if policy_id is None:
            print(f"[warn] {fp} has no document.policy_id -- skipping enrichment for this file",
                  file=sys.stderr)
            continue
        policy_id = str(policy_id)

        flat = {
            "doc_title": doc.get("title") or "",
            "doc_source_file": doc.get("source_file") or "",
            "doc_notice": doc.get("notice") or "",
        }

        metadata_table = doc.get("metadata_table") or {}
        for k, v in metadata_table.items():
            flat[f"doc_{normalize_key(k)}"] = v if isinstance(v, (str, int, float, bool)) else str(v or "")

        lookup[policy_id] = flat

    print(f"[info] loaded document-level metadata for {len(lookup)} policies from {input_dir}")
    return lookup

def iter_chunks_from_chunks_dir(input_dir):
    #Read every per-policy file's "chunks" list directly, yielding one raw chunk dict at a time.

    files = sorted(os.listdir(input_dir))
    for fp in files:
        try:
            with open(input_dir + fp, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] could not read {fp}: {e}", file=sys.stderr)
            continue

        for chunk in data.get("chunks", []):
            yield chunk


def load_chunks(input_dir):
    """Unified chunk loader that filters empty/trivial/clause_intro chunks regardless of source."""
    n_skipped_empty = 0
    n_skipped_trivial = 0
    n_skipped_clause_intro = 0
    n_yielded = 0


    raw_iter = iter_chunks_from_chunks_dir(input_dir)

    for record in raw_iter:
        text = (record.get("text") or "").strip()
        if not text:
            n_skipped_empty += 1
            continue

        if record.get("is_trivial"):
            n_skipped_trivial += 1
            continue

        if record.get("chunk_type") == "clause_intro":
            n_skipped_clause_intro += 1
            continue

        yield record
        n_yielded += 1

    print(f"[info] loaded {n_yielded} chunks from source='{input_dir}' "
          f"(skipped {n_skipped_empty} empty, {n_skipped_trivial} trivial, "
          f"{n_skipped_clause_intro} clause_intro)")


def extract_breadcrumb_str(record: dict) -> str:
    """Flatten a chunk's breadcrumb (list or scalar) into a single display/embedding string."""
    breadcrumb = record.get("breadcrumb") or []
    if isinstance(breadcrumb, list):
        return " > ".join(str(b) for b in breadcrumb)
    return str(breadcrumb)


def build_embed_text(record: dict) -> str:
    #Construct the ENRICHED string that actually gets embedded: title + breadcrumb + text.

    title = (record.get("policy_title") or "").strip()
    breadcrumb_str = extract_breadcrumb_str(record)
    text = (record.get("text") or "").strip()

    parts = [p for p in (title, breadcrumb_str, text) if p]
    return "\n".join(parts)


def make_embedding_text(record: dict, tokenizer, max_seq_length):
    # make enriched embed text, truncate if needed
    enriched = build_embed_text(record)
    if max_seq_length is None or not enriched:
        return enriched, None, False

    n_tokens = len(tokenizer.encode(enriched, truncation=False))
    if n_tokens <= max_seq_length:
        return enriched, n_tokens, False

    ids = tokenizer.encode(enriched, truncation=True, max_length=max_seq_length)
    truncated = tokenizer.decode(ids, skip_special_tokens=True)
    return truncated, n_tokens, True


def build_chunk_id(record: dict) -> str:
    #make a unique id per chunk
    policy_id = record.get("policy_id", "unknown")
    idx = record.get("chunk_index")
    if idx is None:
        idx = record.get("clause_number", "0")
    return f"{policy_id}_{idx}"


def sanitize_metadata(record: dict, doc_metadata_lookup: dict) -> dict:
    #cleanup a chunk record and its metadata (for chroma)
    breadcrumb_str = extract_breadcrumb_str(record)

    def clean(v):
        if v is None:
            return ""
        if isinstance(v, (str, int, float, bool)):
            return v
        return str(v)

    policy_id = clean(record.get("policy_id"))

    metadata = {
        "policy_id": policy_id,
        "policy_title": clean(record.get("policy_title")),
        "breadcrumb": breadcrumb_str,
        "clause_number": clean(record.get("clause_number")),
        "citation": clean(record.get("citation")),
        "source_url": clean(record.get("source_url")),
        "chunk_type": clean(record.get("chunk_type")),
        "chunk_index": clean(record.get("chunk_index")),
        "is_trivial": bool(record.get("is_trivial", False)),
        "term": clean(record.get("term")),
        "row_label": clean(record.get("row_label")),
        "content_hash": clean(record.get("content_hash")),
        "fetch_timestamp": clean(record.get("fetch_timestamp")),
    }

    doc_meta = doc_metadata_lookup.get(str(policy_id), {})
    metadata.update(doc_meta)

    return metadata


def batched(iterable):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) > config.batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def embed_policy(working_dir: str):
    doc_metadata_lookup = load_document_metadata(working_dir + config.input_dir)

    print(f"loading embedding model: {config.embedding_model}")
    model = SentenceTransformer(config.embedding_model, device=config.device)

    print(f"opening persistent ChromaDB at: {working_dir + config.output_dir}")
    client = chromadb.PersistentClient(path=(working_dir + config.output_dir))


    # cosine similarity is the standard choice for BGE embeddings
    collection = client.get_or_create_collection(
        name=config.collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    records = list(load_chunks(
        config.input_dir,
    ))

    if not records:
        print("no chunks to embed, exiting.")
        return

    max_len = getattr(model, "max_seq_length", None)
    if max_len is None:
        print("model has no max_seq_length attribute: skipping truncation checks")

    n_truncated = 0

    for batch in tqdm(batched(records), total=(len(records) + 31)//32, desc="Embedding + upserting"):
        ids, texts, embed_texts, metadatas = [], [], [], []

        for record in batch:
            base_id = build_chunk_id(record)
            raw_text = record["text"]  # stored as the Chroma document, unmodified
            base_meta = sanitize_metadata(record, doc_metadata_lookup)
            base_meta["parent_chunk_id"] = base_id

            embed_text, n_tokens, was_truncated = make_embedding_text(
                record, model.tokenizer, max_len,
            )

            if was_truncated:
                n_truncated += 1
                print(f"[warn] chunk {base_id!r} has {n_tokens} tokens > "
                      f"max_seq_length={max_len}; truncated (windowing is out of scope)")

            ids.append(base_id)
            texts.append(raw_text)
            embed_texts.append(embed_text)
            metadatas.append(base_meta)

        # no passage prefix
        embeddings = model.encode(
            embed_texts,
            batch_size=len(embed_texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )

    print(f"done. Collection '{config.collection_name}' now has {collection.count()} chunks.")

    print(f"{n_truncated} chunk(s) exceeded max_seq_length={max_len} "
          f"and were truncated.")


if __name__ == "__main__":
    main()
