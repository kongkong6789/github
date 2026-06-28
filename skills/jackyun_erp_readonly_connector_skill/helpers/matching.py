"""
Name matching helpers for master data.

ERP names are often typed with mixed Chinese/English parentheses or irregular
spacing. These helpers normalize that noise before exact/fuzzy matching.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable


def normalize_lookup_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text.casefold()


def lookup_score(query: object, candidate: object) -> tuple:
    query_text = normalize_lookup_text(query)
    candidate_text = normalize_lookup_text(candidate)
    if not query_text or not candidate_text:
        return (False, False, 0.0, 0)

    exact = query_text == candidate_text
    contains = (
        min(len(query_text), len(candidate_text)) >= 3
        and (query_text in candidate_text or candidate_text in query_text)
    )
    ratio = SequenceMatcher(None, query_text, candidate_text).ratio()
    return (exact, contains, ratio, -abs(len(candidate_text) - len(query_text)))


def best_match(
    query: object,
    candidates: Iterable[dict],
    fields: tuple[str, ...],
    min_ratio: float = 0.86,
) -> dict | None:
    scored = []
    for item in candidates or []:
        best_field_score = (False, False, 0.0, 0)
        for field in fields:
            field_score = lookup_score(query, item.get(field))
            if field_score > best_field_score:
                best_field_score = field_score
        if best_field_score[0] or best_field_score[1] or best_field_score[2] >= min_ratio:
            scored.append((best_field_score, item))

    if not scored:
        return None
    scored.sort(key=lambda row: row[0], reverse=True)
    return scored[0][1]
