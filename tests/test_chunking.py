from uuid import uuid4

import pytest

from investigation.chunking import chunk_document, token_count
from investigation.models import Document, SourceLocation, TextBlock


def document(text, blocks=None):
    return Document(
        id=str(uuid4()),
        title="Test",
        filename="test.txt",
        format="txt",
        text=text,
        checksum="checksum",
        blocks=blocks or [],
    )


@pytest.mark.parametrize("strategy", ["fixed", "structure"])
def test_chunk_offsets_reconstruct_exact_source_and_budget(strategy):
    text = " ".join(f"value{i}" for i in range(130))
    doc = document(text)
    chunks = chunk_document(doc, strategy=strategy, size=32, overlap=5)
    assert len(chunks) > 1
    assert all(
        chunk.text == text[chunk.location.start_char : chunk.location.end_char] for chunk in chunks
    )
    assert all(token_count(chunk.text) <= 32 for chunk in chunks)
    assert chunks[-1].location.end_char == len(text)
    assert [chunk.id for chunk in chunks] == [
        chunk.id for chunk in chunk_document(doc, strategy=strategy, size=32, overlap=5)
    ]
    for left, right in zip(chunks, chunks[1:], strict=False):
        assert right.location.start_char < left.location.end_char


def test_structure_does_not_merge_pages_and_retains_sentence_ids():
    first = "The payment service changed on March 2."
    second = "An incident followed on March 3."
    text = f"{first}\n\n{second}"
    doc = document(
        text,
        [
            TextBlock(
                text=first,
                location=SourceLocation(
                    page=1, start_char=0, end_char=len(first), sentence_ids=[0]
                ),
            ),
            TextBlock(
                text=second,
                location=SourceLocation(
                    page=2, start_char=len(first) + 2, end_char=len(text), sentence_ids=[1]
                ),
            ),
        ],
    )
    chunks = chunk_document(doc, "structure", size=100, overlap=4)
    assert len(chunks) == 2
    assert [chunk.location.page for chunk in chunks] == [1, 2]
    assert [chunk.location.sentence_ids for chunk in chunks] == [[0], [1]]


def test_structure_merges_small_paragraphs():
    text = "First fact.\n\nSecond fact."
    doc = document(
        text,
        [
            TextBlock(text="First fact.", location=SourceLocation(start_char=0, end_char=11)),
            TextBlock(
                text="Second fact.", location=SourceLocation(start_char=13, end_char=len(text))
            ),
        ],
    )
    chunks = chunk_document(doc, "structure", 32, 4)
    assert len(chunks) == 1
    assert chunks[0].text == text


@pytest.mark.parametrize("size,overlap", [(0, 0), (32, 32), (32, -1)])
def test_invalid_chunk_parameters(size, overlap):
    with pytest.raises(ValueError):
        chunk_document(document("some text"), size=size, overlap=overlap)


@pytest.mark.parametrize("strategy", ["fixed", "structure"])
def test_model_offsets_split_subword_heavy_text_without_dropping_the_tail(strategy):
    text = "antidisestablishmentarianism pneumonoultramicroscopicsilicovolcanoconiosis tailfact"
    doc = document(text)

    def character_tokens(value):
        return [(index, index + 1) for index, char in enumerate(value) if not char.isspace()]

    chunks = chunk_document(doc, strategy, size=20, overlap=4, tokenizer=character_tokens)
    assert len(chunks) > 3
    assert all(len(character_tokens(chunk.text)) <= 20 for chunk in chunks)
    assert chunks[-1].text.endswith("tailfact")
    covered = {
        index
        for chunk in chunks
        for index in range(chunk.location.start_char, chunk.location.end_char)
    }
    assert all(index in covered for index, char in enumerate(text) if not char.isspace())
