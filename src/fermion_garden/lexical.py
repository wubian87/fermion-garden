"""Deterministic zero-network lexical scorer used by the v0.1 baseline."""

from __future__ import annotations

from collections import Counter
import math
import re
from typing import Iterable

from .models import ContextItem

_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize English words and Chinese characters, adding Chinese bigrams."""

    tokens: list[str] = []
    for segment in _TOKEN.findall(text):
        if "\u3400" <= segment[0] <= "\u9fff":
            characters = list(segment)
            tokens.extend(characters)
            tokens.extend(
                characters[index] + characters[index + 1]
                for index in range(len(characters) - 1)
            )
        else:
            tokens.append(segment.lower())
    return tokens


def score_items(query: str, items: Iterable[ContextItem]) -> dict[str, float]:
    """Return BM25-style scores for a query against a fixed candidate set."""

    candidates = list(items)
    if not candidates:
        return {}
    documents = {item.id: tokenize(item.text + " " + " ".join(item.tags)) for item in candidates}
    average_length = sum(len(tokens) for tokens in documents.values()) / len(documents) or 1.0
    document_frequency = Counter(
        token for tokens in documents.values() for token in set(tokens)
    )
    query_tokens = set(tokenize(query))
    scores: dict[str, float] = {}
    for item in candidates:
        tokens = documents[item.id]
        frequencies = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = frequencies[token]
            if not frequency:
                continue
            count = document_frequency[token]
            inverse_frequency = math.log((len(candidates) - count + 0.5) / (count + 0.5) + 1)
            denominator = frequency + 1.5 * (0.25 + 0.75 * len(tokens) / average_length)
            score += inverse_frequency * frequency * 2.5 / denominator
        scores[item.id] = round(score, 8)
    return scores
