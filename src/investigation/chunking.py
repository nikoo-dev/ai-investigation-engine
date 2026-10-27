"""Two location-preserving chunking strategies with pluggable model token offsets.

Production ingestion supplies the embedding model's untruncated tokenizer. The
word/punctuation fallback is deliberately limited to offline test fixtures and
standalone demonstrations of the chunking algorithm.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from uuid import NAMESPACE_URL, uuid5

from investigation.models import Chunk, Document, SourceLocation, TextBlock

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
TokenSpans = Callable[[str], list[tuple[int, int]]]


def token_count(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def _token_spans(text: str, tokenizer: TokenSpans | None) -> list[tuple[int, int]]:
    if tokenizer:
        return [(start, end) for start, end in tokenizer(text) if end > start]
    return [(token.start(), token.end()) for token in TOKEN_PATTERN.finditer(text)]


def _location(doc: Document, start: int, end: int) -> SourceLocation:
    blocks = [
        block
        for block in doc.blocks
        if block.location.end_char > start and block.location.start_char < end
    ]
    pages = {block.location.page for block in blocks if block.location.page is not None}
    sections = list(
        dict.fromkeys(block.location.section for block in blocks if block.location.section)
    )
    sentences = sorted({sid for block in blocks for sid in block.location.sentence_ids})
    return SourceLocation(
        page=next(iter(pages)) if len(pages) == 1 else None,
        section=" / ".join(sections)
        if sections
        else (f"Pages {min(pages)}-{max(pages)}" if len(pages) > 1 else None),
        start_char=start,
        end_char=end,
        sentence_ids=sentences,
    )


def _make_chunk(doc: Document, start: int, end: int, strategy: str) -> Chunk:
    raw = doc.text[start:end]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    start, end = start + left, start + right
    text = doc.text[start:end]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    chunk_id = str(
        uuid5(NAMESPACE_URL, f"{doc.id}:{doc.revision}:{strategy}:{start}:{end}:{digest}")
    )
    return Chunk(
        id=chunk_id,
        document_id=doc.id,
        revision=doc.revision,
        title=doc.title,
        text=text,
        checksum=digest,
        location=_location(doc, start, end),
        metadata=doc.metadata.copy(),
        strategy=strategy,
    )


def _windows(
    text: str,
    start: int,
    end: int,
    size: int,
    overlap: int,
    tokenizer: TokenSpans | None = None,
) -> list[tuple[int, int]]:
    tokens = [
        (left + start, right + start) for left, right in _token_spans(text[start:end], tokenizer)
    ]
    if not tokens:
        return []
    spans = []
    cursor = 0
    while cursor < len(tokens):
        last = min(cursor + size, len(tokens))
        spans.append((tokens[cursor][0], tokens[last - 1][1]))
        if last == len(tokens):
            break
        cursor = last - overlap
    return spans


def chunk_document(
    doc: Document,
    strategy: str = "structure",
    size: int = 256,
    overlap: int = 40,
    tokenizer: TokenSpans | None = None,
) -> list[Chunk]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be positive and 0 <= overlap < size")
    if strategy == "fixed":
        return [
            _make_chunk(doc, start, end, strategy)
            for start, end in _windows(doc.text, 0, len(doc.text), size, overlap, tokenizer)
        ]
    if strategy != "structure":
        raise ValueError("Chunk strategy must be fixed or structure")
    blocks = doc.blocks or [
        TextBlock(text=doc.text, location=SourceLocation(start_char=0, end_char=len(doc.text)))
    ]
    spans: list[tuple[int, int]] = []
    pending: tuple[int, int] | None = None
    pending_tokens = 0
    pending_page: int | None = None
    pending_section: str | None = None
    for block in blocks:
        start, end = block.location.start_char, block.location.end_char
        if end <= start:
            continue
        # Split only oversized structural blocks into overlapping token windows.
        windows = _windows(doc.text, start, end, size, overlap, tokenizer)
        for part_start, part_end in windows:
            count = len(_token_spans(doc.text[part_start:part_end], tokenizer))
            same_context = (
                block.location.page == pending_page and block.location.section == pending_section
            )
            combined_count = (
                len(_token_spans(doc.text[pending[0] : part_end], tokenizer))
                if pending and tokenizer and same_context
                else pending_tokens + count
            )
            if pending and (combined_count > size or not same_context or len(windows) > 1):
                spans.append(pending)
                pending = None
                pending_tokens = 0
            if pending:
                pending = (pending[0], part_end)
                pending_tokens = combined_count
            else:
                pending = (part_start, part_end)
                pending_tokens = count
                pending_page = block.location.page
                pending_section = block.location.section
    if pending:
        spans.append(pending)
    return [
        _make_chunk(doc, start, end, strategy)
        for start, end in spans
        if doc.text[start:end].strip()
    ]
