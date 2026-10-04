import re

# Allowed characters for a definition TERM (not its unrestricted definition text)
_TERM_CHARS = r"A-Za-z0-9À-ÿ '’‘\"(),/&\-\."

# "Term: definition". Allows a comma in the term (some terms cite a standard
# inline, e.g. "Access (AS ISO 15489.1-2002, s3.1): ..."). The trailing group
# is (.*) not (.+) because some terms have nothing after their own colon -
# the whole definition lives in a nested sub-list instead. Safe to allow an
# empty match only because this regex is only ever tried on a confirmed
# top-level bulleted list item, so an ordinary sentence ending in a bare
# colon never reaches it.
DEFINITION_TERM_RE = re.compile(r"^([\"'’‘A-Za-z][" + _TERM_CHARS + r"]{1,70}?):\s*(.*)$", re.DOTALL)

# Fallback for "Term means definition" / "Term means: definition" - both
# conventions appear, sometimes within the same document's Definitions section.
DEFINITION_TERM_MEANS_RE = re.compile(r"^([\"'’‘A-Za-z][" + _TERM_CHARS + r"]{1,70}?)\s+means:?\s+(.+)$", re.DOTALL)

# "Term is Definition", no colon or "means" at all.
DEFINITION_TERM_IS_RE = re.compile(r"^([\"'’‘A-Za-z][" + _TERM_CHARS + r"]{1,70}?)\s+is:?\s+(.+)$", re.DOTALL)

# "Term – definition" (en-dash separator). Whatever follows the dash is kept
# as-is rather than trying to enumerate every verb variant; the en-dash is
# the actually reliable signal here.
DEFINITION_TERM_DASH_RE = re.compile(r"^([\"'’‘A-Za-z][" + _TERM_CHARS + r"]{1,70}?)\s*–\s*(.+)$", re.DOTALL)

# "Term refers to definition" - a convention with no colon, dash, "means" or
# "is" at all (seen in Leave Entitlements policies).
DEFINITION_TERM_REFERS_RE = re.compile(
    r"^([\"'’‘A-Za-z][" + _TERM_CHARS + r"]{1,70}?)\s+refers\s+to\s+(.+)$", re.DOTALL | re.IGNORECASE
)


def split_definitions(chunks):
    """Splits bundled 'Term: definition' pairs (one per clause) into
    individually citable sub-chunks, so retrieval doesn't return a wall of
    unrelated terms for a single-term query. Scoped to clauses whose
    breadcrumb includes 'Definitions', to avoid false-positive splitting of
    ordinary colon-containing sentences elsewhere.

    Runs as a sequential state machine rather than two global buckets,
    because a term's own nested sub-list (e.g. lettered legal criteria)
    renders as extra lines that don't match the term pattern themselves.
    Each non-matching line attaches to whichever term is currently open;
    only lines seen before any term has opened count as real intro text.

    Known remaining limitations (source-authoring issues, not fixed here):
    a few documents split one logical definition across two consecutive
    top-level <li> elements with no structural signal distinguishing that
    from an actual second term; a couple of others cram two terms into one
    <li> (seen in Leave Entitlements Policy's "NES refers to... Voluntary
    Emergency Management Activity where..." - both stay glued into one
    definition since the second term never starts its own line)."""
    out = []
    for c in chunks:
        is_definitions_clause = (
            c["chunk_type"] == "clause"
            and c["breadcrumb"]
            and any("definition" in b.lower() for b in c["breadcrumb"])
        )
        if not is_definitions_clause:
            out.append(c)
            continue

        # Track indent depth and whether each line is a real bullet, rather
        # than blindly stripping "-". Top-level bullets get "- ", nested
        # sub-items get "  - ", "    - " etc; a plain intro sentence (from a
        # <p>) has no bullet prefix at all. Only a genuine top-level bullet
        # can open a new term, so a plain sentence ending in a bare colon
        # (e.g. "For the purpose of this Policy:") can never be misread
        # as one.
        raw_lines = [l for l in c["text"].split("\n") if l.strip()]
        parsed_lines = []
        for l in raw_lines:
            leading = len(l) - len(l.lstrip(" "))
            rest = l[leading:]
            is_bullet = rest.startswith("- ")
            text = rest[2:].strip() if is_bullet else rest.strip()
            parsed_lines.append((leading // 2, is_bullet, text))

        intro_lines = []
        term_entries = []  # [term, [definition_line, ...]]
        for indent, is_bullet, line in parsed_lines:
            m = None
            if indent == 0 and is_bullet:
                m = DEFINITION_TERM_RE.match(line)
                if m and re.search(r"\b(means|is)$", m.group(1).strip(), re.IGNORECASE):
                    # Colon pattern grabbed the wrong colon, e.g. term="Serious
                    # Misconduct means" on "Serious Misconduct means: ...".
                    # Discard and let the dedicated fallback patterns re-parse.
                    m = None
                if not m:
                    m = DEFINITION_TERM_MEANS_RE.match(line)
                if not m:
                    m = DEFINITION_TERM_IS_RE.match(line)
                if not m:
                    m = DEFINITION_TERM_DASH_RE.match(line)
                if not m:
                    m = DEFINITION_TERM_REFERS_RE.match(line)
            if m and len(m.group(1)) < 60:
                term = m.group(1).strip()
                definition = m.group(2).strip()
                term_entries.append([term, [definition] if definition else []])
            elif term_entries:
                # Continuation of whichever term is currently open.
                term_entries[-1][1].append(line)
            else:
                intro_lines.append(line)

        if len(term_entries) >= 2:
            if intro_lines:
                intro_chunk = dict(c)
                intro_chunk["text"] = " ".join(intro_lines)
                intro_chunk["chunk_type"] = "clause_intro"
                out.append(intro_chunk)
            for term, def_lines in term_entries:
                dc = dict(c)
                dc["chunk_type"] = "definition"
                dc["term"] = term
                dc["text"] = f"{term}: " + " ".join(def_lines)
                dc["citation"] = c["citation"] + f', term "{term}"'
                out.append(dc)
        else:
            out.append(c)
    return out
