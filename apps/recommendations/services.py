from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class RecommendationCandidate:
    item_id: str
    score: float


class SimilarityCache:
    """Load offline similarity results once per process and refresh when the file changes."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._path: Path | None = None
        self._mtime_ns: int | None = None
        self._data: dict[str, list[RecommendationCandidate]] = {}

    def get(self, path: str | Path) -> dict[str, list[RecommendationCandidate]]:
        source = Path(path)
        mtime_ns = source.stat().st_mtime_ns
        with self._lock:
            if self._path == source and self._mtime_ns == mtime_ns:
                return self._data

            self._data = self._load_json(source)
            self._path = source
            self._mtime_ns = mtime_ns
            return self._data

    def _load_json(self, path: Path) -> dict[str, list[RecommendationCandidate]]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("similarity file must be a JSON object keyed by item id")

        result: dict[str, list[RecommendationCandidate]] = {}
        for item_id, candidates in raw.items():
            if not isinstance(candidates, list):
                raise ValueError(f"candidate list expected for {item_id!r}")
            result[str(item_id)] = [
                self._parse_candidate(candidate)
                for candidate in candidates
            ]
        return result

    @staticmethod
    def _parse_candidate(candidate: Any) -> RecommendationCandidate:
        if isinstance(candidate, str):
            return RecommendationCandidate(item_id=candidate, score=1.0)
        if isinstance(candidate, int):
            return RecommendationCandidate(item_id=str(candidate), score=1.0)
        if isinstance(candidate, dict):
            item_id = (
                candidate.get("item_id")
                or candidate.get("id")
                or candidate.get("business_id")
            )
            if item_id is None:
                raise ValueError(f"candidate missing id field: {candidate!r}")
            raw_score = candidate.get("score", candidate.get("similarity", 1.0))
            if raw_score is None:
                raw_score = 1.0
            return RecommendationCandidate(item_id=str(item_id), score=float(raw_score))
        raise ValueError(f"unsupported candidate format: {candidate!r}")


similarity_cache = SimilarityCache()


def rerank_from_recent_items(
    recent_item_ids: list[str],
    similarity_file: str | Path,
    *,
    top_k: int = 20,
    exclude_seen: bool = True,
) -> list[RecommendationCandidate]:
    """Merge offline similar-item candidates using recent behavior context."""
    if top_k <= 0:
        return []

    similarity = similarity_cache.get(similarity_file)
    seen = set(recent_item_ids)
    scores: dict[str, float] = {}

    for offset, item_id in enumerate(recent_item_ids):
        recency_weight = 1.0 / (offset + 1)
        for candidate in similarity.get(str(item_id), []):
            if exclude_seen and candidate.item_id in seen:
                continue
            scores[candidate.item_id] = scores.get(candidate.item_id, 0.0) + (
                recency_weight * candidate.score
            )

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        RecommendationCandidate(item_id=item_id, score=score)
        for item_id, score in ranked[:top_k]
    ]
