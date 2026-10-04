from common import build_citation
from definitions_splitter import split_definitions
from html_loader import extract_doc_title, extract_policy_id, load_soup
from tables import extract_key_info_metadata
from validation import validate
from walker import ChunkWalker


def chunk_policy_html(html_path, manifest_lookup=None):
    soup = load_soup(html_path)
    doc_title = extract_doc_title(soup)
    policy_id = extract_policy_id(soup, fallback_path=html_path)
    source_url = f"https://policies.latrobe.edu.au/document/view.php?id={policy_id}" if policy_id else None

    content = soup.find("div", id="sliph-document-content")
    if content is None:
        return {
            "document": {"title": doc_title, "policy_id": policy_id, "source_file": str(html_path)},
            "chunks": [],
            "validation": {
                "ok": False,
                "reason": "No <div id='sliph-document-content'> found - different template, needs manual review.",
            },
        }

    all_tables_in_doc = content.find_all("table")
    metadata, key_info_table = extract_key_info_metadata(all_tables_in_doc)
    key_info_consumed = key_info_table is not None

    walker = ChunkWalker(doc_title, policy_id, source_url)
    if key_info_table is not None:
        walker.consumed_table_ids.add(id(key_info_table))

    # The Key Information table (Review Date, Policy Type etc.) is parsed above into
    # `metadata` and deliberately excluded from the normal table-walk
    if metadata:
        meta_bc = ["Key Information"]
        meta_text = "\n".join(f"{k}: {v}" for k, v in metadata.items())
        walker.chunks.append({
            "chunk_type": "document_metadata",
            "policy_id": policy_id,
            "policy_title": doc_title,
            "breadcrumb": meta_bc,
            "clause_number": None,
            "text": meta_text,
            "citation": build_citation(doc_title, meta_bc, None),
            "source_url": source_url,
            "is_trivial": False,
        })

    walker.walk(list(content.children))
    walker.flush_clause()

    chunks = split_definitions(walker.chunks)

    # Assign reading-order chunk_index after splitting (not during the
    # walk), since split_definitions() can turn one chunk into several.
    # clause_number can't serve this role - several chunks can share one
    # (e.g. a Definitions clause split into 8 pieces), and tables/notes
    # have none at all.
    for i, c in enumerate(chunks):
        c["chunk_index"] = i

    validation = validate(content, chunks, walker, key_info_consumed)

    if manifest_lookup and policy_id in manifest_lookup:
        manifest_row = manifest_lookup[policy_id]
        for c in chunks:
            c["content_hash"] = manifest_row.get("sha256_hash") or manifest_row.get("hash")
            c["fetch_timestamp"] = manifest_row.get("fetch_timestamp") or manifest_row.get("timestamp")

    document_meta = {
        "title": doc_title,
        "policy_id": policy_id,
        "source_url": source_url,
        "source_file": str(html_path),
        "metadata_table": metadata,
        "notice": walker.notice,
    }

    return {"document": document_meta, "chunks": chunks, "validation": validation}
