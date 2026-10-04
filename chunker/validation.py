def validate(content, chunks, walker, key_info_consumed):
    """Sanity-checks a completed walk against the raw source, so a silent
    parsing regression shows up as a flagged document instead of a
    quietly-wrong chunk set."""
    total_enumerate_spans = len(content.find_all("span", class_="enumerate"))

    # Clause count is by distinct clause_number, not chunk_type == "clause",
    # since split_definitions() reassigns some clauses to
    # "clause_intro"/"definition".
    extracted_clause_count = len({
        c["clause_number"] for c in chunks
        if c["chunk_type"] in ("clause", "clause_intro", "definition") and c.get("clause_number")
    })

    tables_found = len(content.find_all("table"))
    tables_consumed = len(walker.consumed_table_ids)

    # Every consumed table should have produced its own chunk(s) - either
    # one "table" chunk or several "table_row" chunks - except the Key
    # Information table (consumed into document.metadata_table by design).
    # Counts distinct tables, not raw chunk count, since one table can
    # split into many table_row chunks. Catches a regression of the
    # table-merge bug either way it can happen.
    tables_as_own_chunk = len(walker.tables_producing_chunks)
    expected_table_chunks = tables_consumed - (1 if key_info_consumed else 0)

    # "No Section heading found" is only suspicious if h1 tags exist but
    # didn't match "Section N - ...". Some legitimate sub-templates (e.g.
    # "Schedule"-type policies) use Part (h2) headings only, with no h1
    # at all.
    h1_count = len(content.find_all("h1"))
    section_heading_is_suspicious = h1_count > 0 and not walker.first_section_seen

    result = {
        "ok": True,
        "enumerate_spans_in_source": total_enumerate_spans,
        "clause_chunks_extracted": extracted_clause_count,
        "clause_count_matches": total_enumerate_spans == extracted_clause_count,
        "tables_in_source": tables_found,
        "tables_consumed": tables_consumed,
        "all_tables_consumed": tables_found == tables_consumed,
        "tables_emitted_as_own_chunk": tables_as_own_chunk,
        "table_chunking_ok": tables_as_own_chunk == expected_table_chunks,
        "has_section1_heading": walker.first_section_seen,
        "h1_tags_in_source": h1_count,
    }
    if (
        not result["clause_count_matches"]
        or not result["all_tables_consumed"]
        or not result["table_chunking_ok"]
        or section_heading_is_suspicious
    ):
        result["ok"] = False
    return result
