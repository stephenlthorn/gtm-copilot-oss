from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True)
class Chunk:
    text: str
    chunk_index: int
    token_count: int


_ENCODING_NAME = "cl100k_base"


def _get_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def _count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    return len(encoding.encode(text))


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in parts if s.strip()]


def _build_chunks(
    blocks: list[str],
    max_tokens: int,
    overlap_tokens: int,
    encoding: tiktoken.Encoding,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_sentences: list[str] = []
    current_token_count = 0

    def _flush(overlap_carry: list[str] | None = None) -> list[str]:
        nonlocal current_sentences, current_token_count
        if not current_sentences:
            return overlap_carry or []
        text = " ".join(current_sentences).strip()
        if text:
            token_count = _count_tokens(text, encoding)
            chunks.append(Chunk(text=text, chunk_index=len(chunks), token_count=token_count))

        carry: list[str] = []
        if overlap_tokens > 0 and current_sentences:
            carry_tokens = 0
            for sent in reversed(current_sentences):
                sent_tokens = _count_tokens(sent, encoding)
                if carry_tokens + sent_tokens > overlap_tokens:
                    break
                carry.insert(0, sent)
                carry_tokens += sent_tokens

        current_sentences = []
        current_token_count = 0
        return carry

    for block in blocks:
        sentences = _split_sentences(block)
        if not sentences:
            continue
        for sentence in sentences:
            sent_tokens = _count_tokens(sentence, encoding)
            if sent_tokens > max_tokens:
                _flush()
                token_count = _count_tokens(sentence, encoding)
                chunks.append(Chunk(text=sentence.strip(), chunk_index=len(chunks), token_count=token_count))
                continue
            if current_token_count + sent_tokens > max_tokens and current_sentences:
                carry = _flush()
                current_sentences = carry
                current_token_count = sum(_count_tokens(s, encoding) for s in carry)
            current_sentences.append(sentence)
            current_token_count += sent_tokens

    _flush()
    return chunks


def _split_paragraphs(text: str) -> list[str]:
    blocks = re.split(r"\n{2,}", text.strip())
    return [b.strip() for b in blocks if b.strip()]


def _split_sections(text: str) -> list[str]:
    parts = re.split(r"(?m)^(#{1,6}\s+.+)$", text.strip())
    sections: list[str] = []
    current: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if re.match(r"^#{1,6}\s+", stripped):
            if current:
                sections.append("\n".join(current).strip())
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        sections.append("\n".join(current).strip())
    return [s for s in sections if s]


def _split_speaker_turns(text: str) -> list[str]:
    lines = text.strip().splitlines()
    turns: list[str] = []
    current_turn: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}\s+\w+", stripped) or re.match(r"^[\w\s]+:", stripped):
            if current_turn:
                turns.append("\n".join(current_turn).strip())
            current_turn = [stripped]
        else:
            current_turn.append(stripped)
    if current_turn:
        turns.append("\n".join(current_turn).strip())
    return turns if turns else _split_paragraphs(text)


def chunk_text(
    text: str,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
    strategy: str = "paragraph",
) -> list[Chunk]:
    if not text or not text.strip():
        return []

    encoding = _get_encoding()

    if strategy == "section":
        blocks = _split_sections(text)
    elif strategy == "speaker_turn":
        blocks = _split_speaker_turns(text)
    else:
        blocks = _split_paragraphs(text)

    if not blocks:
        return []

    return _build_chunks(blocks, max_tokens, overlap_tokens, encoding)
