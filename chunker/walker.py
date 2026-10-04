import re

from bs4.element import NavigableString, Tag

from common import SECTION_HEADING_RE, build_citation, is_notice_banner, is_trivial_text
from lists import render_list
from tables import serialize_table, serialize_table_rows


class ChunkWalker:
    """Walks a document's content region in document order, tracking a
    heading breadcrumb (Section > Part > sub-heading > sub-sub-heading) and
    an open numbered clause, and emits chunks as it goes.

    All the state that used to live as closure variables inside one big
    function now lives as instance attributes here, so the walking logic
    can be tested and reasoned about on its own.
    """

    def __init__(self, doc_title, policy_id, source_url):
        self.doc_title = doc_title
        self.policy_id = policy_id
        self.source_url = source_url

        self.chunks = []
        self.buffer_parts = []
        self.clause_number = None
        self.clause_started = False

        self.breadcrumb = {"h1": None, "h2": None, "h3": None, "h4": None}
        self.first_section_seen = False
        self.notice = None

        # Tables consumed anywhere (including the Key Information table,
        # seeded in by the caller before walk() runs) vs. tables that
        # actually produced their own chunk(s) - used later for validation.
        self.consumed_table_ids = set()
        self.tables_producing_chunks = set()

    def current_breadcrumb_list(self):
        return [self.breadcrumb[k] for k in ("h1", "h2", "h3", "h4") if self.breadcrumb[k]]

    def flush_clause(self):
        if self.clause_started:
            text = "\n".join(p for p in self.buffer_parts if p and p.strip()).strip()
            if text:
                bc = self.current_breadcrumb_list()
                self.chunks.append({
                    "chunk_type": "clause",
                    "policy_id": self.policy_id,
                    "policy_title": self.doc_title,
                    "breadcrumb": bc,
                    "clause_number": self.clause_number,
                    "text": text,
                    "citation": build_citation(self.doc_title, bc, self.clause_number),
                    "source_url": self.source_url,
                    "is_trivial": is_trivial_text(text),
                })
        self.buffer_parts = []
        self.clause_number = None
        self.clause_started = False

    def emit_freefloating(self, chunk_type, text, extra=None, citation_suffix=None):
        """Used for any chunk that isn't part of an accumulating clause
        buffer: notes, lists, tables, and table rows. If a table appears
        while a clause is open, pass extra={"clause_number": ...} so it
        still cites back to that clause without being merged into the
        clause's own text. citation_suffix appends e.g. a row label."""
        if not text or not text.strip():
            return
        bc = self.current_breadcrumb_list()
        clause_num = (extra or {}).get("clause_number")
        citation = build_citation(self.doc_title, bc, clause_num)
        if citation_suffix:
            citation += citation_suffix
        entry = {
            "chunk_type": chunk_type,
            "policy_id": self.policy_id,
            "policy_title": self.doc_title,
            "breadcrumb": bc,
            "clause_number": clause_num,
            "text": text.strip(),
            "is_trivial": is_trivial_text(text.strip()),
            "citation": citation,
            "source_url": self.source_url,
        }
        if extra:
            entry.update(extra)
        self.chunks.append(entry)

    def walk(self, nodes):
        for el in nodes:
            if isinstance(el, NavigableString):
                text = str(el).strip()
                if text:
                    if self.clause_started:
                        self.buffer_parts.append(text)
                    else:
                        self.emit_freefloating("note", text)
                continue

            if not isinstance(el, Tag):
                continue

            if el.name == "h1":
                self.flush_clause()
                text = el.get_text(strip=True)
                if SECTION_HEADING_RE.match(text):
                    self.first_section_seen = True
                self.breadcrumb["h1"] = text
                self.breadcrumb["h2"] = self.breadcrumb["h3"] = self.breadcrumb["h4"] = None
                continue

            if el.name == "h2":
                self.flush_clause()
                self.breadcrumb["h2"] = el.get_text(strip=True)
                self.breadcrumb["h3"] = self.breadcrumb["h4"] = None
                continue

            if el.name == "h3":
                self.flush_clause()
                self.breadcrumb["h3"] = el.get_text(strip=True)
                self.breadcrumb["h4"] = None
                continue

            if el.name == "h4":
                self.flush_clause()
                if is_notice_banner(self.first_section_seen):
                    self.notice = el.get_text(strip=True)
                else:
                    self.breadcrumb["h4"] = el.get_text(strip=True)
                continue

            if el.name == "div" and "sliph-document-status" in (el.get("class") or []):
                continue  # boilerplate "this is the current version" line

            if el.name == "p":
                self._handle_p(el)
                continue

            if el.name in ("ol", "ul"):
                rendered = render_list(el)
                if self.clause_started:
                    self.buffer_parts.append(rendered)
                else:
                    self.emit_freefloating("list", rendered)
                continue

            if el.name == "table":
                self._handle_table(el)
                continue

            if el.name == "span" and "top-link" in (el.get("class") or []):
                continue  # "Top of Page" nav noise

            if el.name == "div":
                self._handle_div(el)
                continue

            # Anything else (stray spans etc.) carried no content in any
            # sample document - ignored.

    def _handle_p(self, el):
        span = el.find("span", class_="enumerate")
        if span:
            self.flush_clause()
            num_text = span.get_text(strip=True).strip("()")
            self.clause_number = num_text
            self.clause_started = True
            remainder = el.get_text(" ", strip=True)
            remainder = re.sub(r"^\(?\s*" + re.escape(num_text) + r"\s*\)?\s*", "", remainder, count=1)
            self.buffer_parts.append(remainder)
        else:
            text = el.get_text(" ", strip=True)
            if self.clause_started:
                self.buffer_parts.append(text)
            else:
                self.emit_freefloating("intro_text", text)

    def _handle_table(self, el):
        if id(el) in self.consumed_table_ids:
            return
        self.consumed_table_ids.add(id(el))
        self.tables_producing_chunks.add(id(el))

        # Never folded into buffer_parts - a table inside an open clause
        # used to get appended to the clause's own text, producing chunks
        # up to 764 words and destroying citation precision. clause_num
        # keeps every row/table citing back to the clause it appeared
        # under, without merging the text.
        clause_num = self.clause_number if self.clause_started else None
        rows = serialize_table_rows(el)
        if len(rows) >= 2:
            for label, line in rows:
                self.emit_freefloating(
                    "table_row", line,
                    extra={"clause_number": clause_num, "row_label": label},
                    citation_suffix=f', row "{label}"',
                )
        else:
            rendered = serialize_table(el)
            extra = {"clause_number": clause_num} if clause_num else None
            self.emit_freefloating("table", rendered, extra=extra)

    def _handle_div(self, el):
        block_level = el.find_all(["p", "table", "ol", "ul", "h1", "h2", "h3", "h4"])
        if not block_level:
            # Pure inline content (text + inline tags like <a>). get_text()
            # correctly folds in link text; recursing child-by-child here
            # would drop hyperlinked text entirely, since <a> has no
            # explicit handler.
            text = el.get_text(" ", strip=True)
            if self.clause_started:
                self.buffer_parts.append(text)
            else:
                self.emit_freefloating("note", text)
            return
        # Transparent container - recurse rather than flattening, since at
        # least one document wraps a table AND two full numbered clauses
        # AND a heading in a single div.normal.
        self.walk(list(el.children))
