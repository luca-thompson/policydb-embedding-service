def looks_like_key_info_table(table):
    """Checked by content, not position - the real 'Key Information' table
    always opens with a first cell reading 'Policy Type and Approval Body'.
    Some documents (e.g. Admissions Schedule) have no Key Information table
    at all, so "first table = metadata" can't be assumed positionally."""
    rows = table.find_all("tr")
    if not rows:
        return False
    first_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    if not first_cells:
        return False
    return "policy type" in first_cells[0].lower()


def extract_key_info_metadata(all_tables_in_doc):
    """If the first table in the document is the Key Information table,
    parse it into a metadata dict and return that table alongside it, so
    the caller can mark it consumed and exclude it from normal chunking.

    Returns ({}, None) if there's no Key Information table - the walker
    will then hit that first table in document order and emit it as a
    normal "table" chunk, which is correct for documents (e.g. Admissions
    Schedule) whose only table is real content, not metadata."""
    if not all_tables_in_doc or not looks_like_key_info_table(all_tables_in_doc[0]):
        return {}, None

    first_table = all_tables_in_doc[0]
    metadata = {}
    for row in first_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) == 2:
            metadata[cells[0]] = cells[1]
    return metadata, first_table


def _extract_table_rows(table):
    """Shared header-detection and row parsing, used by both serialize_table()
    and serialize_table_rows(). A row only counts as a real header row if
    EVERY cell in it is <th> AND its shape differs from the next row - some
    tables (e.g. a role -> email lookup) put a <th> in every row as a
    per-row label with no header row at all. Treating row 0 as the header
    in that case would corrupt row associations (a Staff row would appear
    to show the Students email)."""
    rows = table.find_all("tr")
    if not rows:
        return False, [], []
    row_cells = [row.find_all(["th", "td"]) for row in rows]
    row_shapes = [[c.name for c in cells] for cells in row_cells]

    def is_all_th(shape):
        return bool(shape) and all(name == "th" for name in shape)

    has_real_header = is_all_th(row_shapes[0]) and (
        len(rows) == 1 or row_shapes[1] != row_shapes[0]
    )
    headers = [c.get_text(" ", strip=True) for c in row_cells[0]] if has_real_header else []
    data = list(zip(row_cells[1:], row_shapes[1:])) if has_real_header else list(zip(row_cells, row_shapes))
    data_rows = [([c.get_text(" ", strip=True) for c in cells], shape) for cells, shape in data]
    return has_real_header, headers, data_rows


def _render_row(values, shape, headers, has_real_header):
    """One row -> (label, line). label is the best identifying value for
    that row (used in table_row citations); line already carries its own
    header/label context inline, so it's self-contained even split out on
    its own - column names aren't hardcoded since semantics differ per
    table (Key Decisions vs. contact lookup vs. outcome matrix)."""
    if not any(values):
        return None
    if has_real_header and len(values) == len(headers):
        line = " | ".join((f"{h}: {v}" if h else v) for h, v in zip(headers, values) if v)
        label = values[0] or (headers[0] if headers else "row")
    elif shape and shape[0] == "th" and len(values) > 1:
        # Row-label table: first cell is this row's own label (a role, a
        # user type). Render as "Label: rest" for a clean key:value pair.
        label, rest = values[0], values[1:]
        line = f"{label}: " + "; ".join(v for v in rest if v)
    else:
        line = " | ".join(v for v in values if v)
        label = values[0] if values and values[0] else "row"
    return label, line


def serialize_table(table):
    """Whole table -> one text blob, all rows joined. Used only when a table
    has fewer than 2 data rows - not worth splitting (see serialize_table_rows
    for the multi-row case, which is what most tables hit)."""
    has_real_header, headers, rows = _extract_table_rows(table)
    lines = []
    if has_real_header:
        lines.append("Table headers: " + " | ".join(h for h in headers if h))
    for values, shape in rows:
        rendered = _render_row(values, shape, headers, has_real_header)
        if rendered:
            lines.append(rendered[1])
    return "\n".join(lines)


def serialize_table_rows(table):
    """Table -> list of (row_label, row_text), one entry per data row.
    Splitting multi-row tables this way exists because even a correctly
    isolated table can still be a 250-650 word single chunk - a 7-role
    responsibility table serialized as one blob is still one oversized,
    low-precision chunk. A query about one role/item should retrieve just
    that row, not the whole table."""
    has_real_header, headers, rows = _extract_table_rows(table)
    out = []
    for values, shape in rows:
        rendered = _render_row(values, shape, headers, has_real_header)
        if rendered:
            out.append(rendered)
    return out
