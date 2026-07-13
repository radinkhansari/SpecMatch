"""The matching engine. Implementation is yours to build (Task 3).

Design constraints:

- Implement the interfaces in interfaces.py.
- Composite scores combine at least two distinct signals; the weights come
  from Settings.matching.weights (config/settings.yaml).
- Tier assignment goes through tiering.assign_tier with thresholds from
  Settings.tiers.
- Persist the top-k candidates per record (Settings.matching.top_k) with
  enough information to answer: what matched, with what score, from which
  signals, and why it landed in its tier.
"""

import re
import sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from app.config import Settings, get_settings
from app.core.db import get_conn
from app.models.schemas import Candidate, CatalogEntry, MatchResult, RecordOut, Tier
from app.services.matching.interfaces import CandidateRetriever, CandidateScorer, MatchingEngine
from app.services.matching.tiering import assign_tier

ABBREVIATIONS = {
    "conc": "concrete",
    "rm": "ready mix",
    "w": "with",
    "fa": "fly ash",
    "stl": "steel",
    "gyp": "gypsum",
    "bd": "board",
    "mtl": "metal",
    "misc": "miscellaneous",
    "blk": "black",
    "sch": "schedule",
    "chan": "channel",
    "bm": "beam",
    "gr": "grade",
}

STOP_WORDS = {"with", "and", "the", "of", "for", "a", "an"}


def _normalize_text(value: str | None) -> str:
    text = (value or "").lower()
    text = text.replace("ready-mix", "ready mix")
    text = re.sub(r"(\d)([a-z])", r"\1 \2", text)
    text = re.sub(r"([a-z])(\d)", r"\1 \2", text)
    text = re.sub(r"[^a-z0-9/%x]+", " ", text)
    tokens = []
    for token in text.split():
        tokens.extend(ABBREVIATIONS.get(token, token).split())
    return " ".join(tokens)


def _tokens(value: str | None) -> set[str]:
    return {token for token in _normalize_text(value).split() if token not in STOP_WORDS}


def _string_similarity(left: str | None, right: str | None) -> float:
    left_norm = _normalize_text(left)
    right_norm = _normalize_text(right)
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    containment = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    return round((jaccard * 0.65) + (containment * 0.25) + (sequence * 0.10), 4)


def _category_agreement(record: RecordOut, entry: CatalogEntry) -> float:
    if not record.category:
        return 0.0
    return 1.0 if record.category.lower() == entry.category.lower() else 0.0


def _unit_compatibility(record: RecordOut, entry: CatalogEntry) -> float:
    if not record.unit:
        return 0.0
    return 1.0 if record.unit.lower() == entry.unit.lower() else 0.0


def _record_from_row(record: RecordOut | sqlite3.Row | dict[str, Any]) -> RecordOut:
    if isinstance(record, RecordOut):
        return record
    return RecordOut.model_validate(dict(record))


class LexicalCandidateRetriever(CandidateRetriever):
    """Ranks catalog entries with cheap lexical, category, and unit hints."""

    def retrieve(
        self, record: RecordOut, catalog: list[CatalogEntry], limit: int
    ) -> list[CatalogEntry]:
        ranked = sorted(
            catalog,
            key=lambda entry: (
                _string_similarity(record.raw_text, entry.description),
                _category_agreement(record, entry),
                _unit_compatibility(record, entry),
            ),
            reverse=True,
        )
        return ranked[:limit]


class WeightedCandidateScorer(CandidateScorer):
    """Builds Candidate objects using configured weighted signals."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def score(self, record: RecordOut, entry: CatalogEntry) -> Candidate:
        signals = {
            "string_similarity": _string_similarity(record.raw_text, entry.description),
            "category_agreement": _category_agreement(record, entry),
            "unit_compatibility": _unit_compatibility(record, entry),
        }
        weights = self.settings.matching.weights
        total_weight = sum(weights.get(name, 0.0) for name in signals)
        composite = 0.0
        if total_weight:
            composite = sum(signals[name] * weights.get(name, 0.0) for name in signals) / total_weight
        return Candidate(
            catalog_id=entry.catalog_id,
            description=entry.description,
            score=round(min(max(composite, 0.0), 1.0), 4),
            signals=signals,
        )


class LexicalMatchingEngine(MatchingEngine):
    """Retrieval + scoring over the ingested catalog."""

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        settings: Settings | None = None,
        retriever: CandidateRetriever | None = None,
        scorer: CandidateScorer | None = None,
    ):
        self.conn = conn or get_conn()
        self._owns_conn = conn is None
        self.settings = settings or get_settings()
        self.retriever = retriever or LexicalCandidateRetriever()
        self.scorer = scorer or WeightedCandidateScorer(self.settings)

    def match_record(self, record: RecordOut) -> MatchResult:
        source = _record_from_row(record)
        catalog = self._load_catalog()
        retrieve_limit = max(self.settings.matching.top_k * 10, self.settings.matching.top_k)
        retrieved = self.retriever.retrieve(source, catalog, retrieve_limit)
        candidates = sorted(
            (self.scorer.score(source, entry) for entry in retrieved),
            key=lambda candidate: candidate.score,
            reverse=True,
        )[: self.settings.matching.top_k]
        top_score = candidates[0].score if candidates else 0.0
        tier = assign_tier(top_score, self.settings.tiers)
        selected_catalog_id = candidates[0].catalog_id if tier is Tier.green and candidates else None
        result = MatchResult(
            record_id=source.record_id,
            source_text=source.raw_text,
            tier=tier,
            candidates=candidates,
            selected_catalog_id=selected_catalog_id,
            review=None,
            matched_at=datetime.now(timezone.utc),
        )
        self._persist(result)
        return result

    def match_all(self) -> list[MatchResult]:
        results = [self.match_record(record) for record in self._load_records()]
        if self._owns_conn:
            self.conn.close()
        return results

    def _load_records(self) -> list[RecordOut]:
        rows = self.conn.execute(
            "SELECT record_id, raw_text, category, unit, quantity, ingested_at"
            " FROM records ORDER BY id"
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    def _load_catalog(self) -> list[CatalogEntry]:
        rows = self.conn.execute(
            "SELECT catalog_id, description, category, unit FROM catalog ORDER BY catalog_id"
        ).fetchall()
        return [CatalogEntry.model_validate(dict(row)) for row in rows]

    def _persist(self, result: MatchResult) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO matches (record_id, payload, tier, matched_at)"
            " VALUES (?, ?, ?, ?)",
            (
                result.record_id,
                result.model_dump_json(),
                result.tier.value,
                result.matched_at.isoformat(),
            ),
        )
        self.conn.commit()
