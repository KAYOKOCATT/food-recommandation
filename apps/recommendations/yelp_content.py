from __future__ import annotations

# pylint: disable=too-many-instance-attributes,too-many-arguments,too-many-locals

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from .services import RecommendationCandidate

FOOD_CATEGORY_PATTERN = re.compile(r"Restaurants|Cafe|Cafes", re.IGNORECASE)
EXCLUDED_CATEGORY_PATTERN = re.compile(
    r"Grocery|Pharmacy|Department Store|Pet Food",
    re.IGNORECASE,
)
CATEGORY_TOKEN_PATTERN = re.compile(r"[^a-z0-9\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")

BUSINESS_STOP_WORDS = sorted(
    set(ENGLISH_STOP_WORDS)
    | {
        "food",
        "place",
        "good",
        "great",
        "really",
        "just",
        "like",
        "restaurant",
        "service",
        "time",
        "nice",
        "ve",
        "ordered",
        "best",
        "delicious",
        "love",
        "amazing",
        "excellent",
        "friendly",
        "definitely",
        "favorite",
        "perfect",
        "horrible",
        "terrible",
        "worst",
        "awful",
        "got",
        "don",
        "came",
        "went",
        "come",
        "going",
        "try",
        "tried",
        "little",
        "wait",
        "said",
        "asked",
        "told",
        "took",
        "make",
        "know",
    }
)


@dataclass
class YelpBusinessProfile:
    """Filtered Yelp restaurant profile plus review text used for TF-IDF documents."""

    business_id: str
    name: str
    categories: str
    stars: float
    review_count: int
    city: str = ""
    state: str = ""
    latitude: float | None = None
    longitude: float | None = None
    review_texts: list[str] = field(default_factory=list)

    @property
    def aggregated_text(self) -> str:
        """Return the review corpus for one restaurant as a single document fragment."""
        return " ".join(self.review_texts)

    def combined_text(self, *, category_weight: int = 5) -> str:
        """Build the restaurant document consumed by TfidfVectorizer."""
        categories_text = preprocess_categories(self.categories)
        return " ".join(
            text
            for text in [
                self.name,
                (categories_text + " ") * max(category_weight, 0),
                self.aggregated_text,
            ]
            if text
        )

    def to_metadata(self) -> dict[str, Any]:
        """Serialize non-vector metadata for inspection/debugging."""
        return {
            "business_id": self.business_id,
            "name": self.name,
            "categories": self.categories,
            "stars": self.stars,
            "review_count": self.review_count,
            "city": self.city,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "aggregated_review_count": len(self.review_texts),
        }


@dataclass(frozen=True)
class YelpContentBuildResult:
    """Output bundle for the offline Yelp content recommendation build."""

    similarities: dict[str, list[RecommendationCandidate]]
    profiles: list[YelpBusinessProfile]
    feature_count: int


def iter_json_lines(path: str | Path, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Stream a JSON Lines file and skip malformed/non-object rows."""
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source):
            if limit is not None and line_number >= limit:
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield record


def preprocess_categories(categories: str | None) -> str:
    """Normalize comma-separated Yelp categories into stable TF-IDF tokens."""
    if not categories:
        return ""

    tokens: list[str] = []
    for category in categories.split(","):
        normalized = CATEGORY_TOKEN_PATTERN.sub(" ", category.strip().lower())
        normalized = WHITESPACE_PATTERN.sub("_", normalized).strip("_")
        if normalized:
            tokens.append(normalized)
    return " ".join(tokens)


def is_restaurant_business(
    record: dict[str, Any],
    *,
    min_review_count: int = 10,
    include_closed: bool = False,
) -> bool:
    """Return whether a Yelp business record is suitable for v1 restaurant modeling."""
    categories = str(record.get("categories") or "")
    if not FOOD_CATEGORY_PATTERN.search(categories):
        return False
    if EXCLUDED_CATEGORY_PATTERN.search(categories):
        return False
    if not include_closed and record.get("is_open") == 0:
        return False
    if record.get("latitude") is None or record.get("longitude") is None:
        return False
    try:
        return int(record.get("review_count") or 0) >= min_review_count
    except (TypeError, ValueError):
        return False


def build_business_profiles(
    business_records: Iterable[dict[str, Any]],
    review_records: Iterable[dict[str, Any]],
    *,
    min_business_review_count: int = 10,
    business_limit: int | None = None,
    include_closed: bool = False,
    max_reviews_per_business: int | None = 50,
) -> list[YelpBusinessProfile]:
    """Filter Yelp businesses and attach a bounded review corpus to each restaurant."""
    profiles_by_id: dict[str, YelpBusinessProfile] = {}
    # First pass: keep the restaurant subset only. This keeps the later review scan cheap.
    for record in business_records:
        if not is_restaurant_business(
            record,
            min_review_count=min_business_review_count,
            include_closed=include_closed,
        ):
            continue

        business_id = str(record.get("business_id") or "")
        if not business_id:
            continue

        profiles_by_id[business_id] = YelpBusinessProfile(
            business_id=business_id,
            name=str(record.get("name") or ""),
            categories=str(record.get("categories") or ""),
            stars=float(record.get("stars") or 0.0),
            review_count=int(record.get("review_count") or 0),
            city=str(record.get("city") or ""),
            state=str(record.get("state") or ""),
            latitude=_optional_float(record.get("latitude")),
            longitude=_optional_float(record.get("longitude")),
        )
        if business_limit is not None and len(profiles_by_id) >= business_limit:
            break

    if not profiles_by_id:
        return []

    # Second pass: stream reviews and keep only text for the selected restaurants.
    for review in review_records:
        business_id = str(review.get("business_id") or "")
        profile = profiles_by_id.get(business_id)
        if profile is None:
            continue
        if (
            max_reviews_per_business is not None
            and len(profile.review_texts) >= max_reviews_per_business
        ):
            continue
        text = str(review.get("text") or "").strip()
        if text:
            profile.review_texts.append(text)

    return list(profiles_by_id.values())


def build_yelp_content_recommendations(
    profiles: list[YelpBusinessProfile],
    *,
    top_k: int = 20,
    max_features: int = 5000,
    min_df: int = 3,
    max_df: float = 0.5,
    category_weight: int = 5,
    batch_size: int = 1000,
) -> YelpContentBuildResult:
    """Build top-k restaurant neighbors from TF-IDF cosine similarity."""
    if len(profiles) < 2 or top_k <= 0:
        return YelpContentBuildResult({}, profiles, 0)

    # Each restaurant is treated as one document: name + weighted categories + reviews.
    documents = [
        profile.combined_text(category_weight=category_weight)
        for profile in profiles
    ]
    # Small dev samples can make min_df and max_df conflict, so clamp them safely.
    effective_min_df = max(1, min(min_df, len(profiles)))
    effective_max_df = max_df
    if isinstance(max_df, float) and int(max_df * len(profiles)) < effective_min_df:
        effective_max_df = 1.0
    vectorizer = TfidfVectorizer(
        max_features=max(max_features, 1),
        min_df=effective_min_df,
        max_df=effective_max_df,
        stop_words=BUSINESS_STOP_WORDS,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-zA-Z_]{2,}\b",
        norm="l2",
    )
    tfidf = vectorizer.fit_transform(documents)
    neighbor_count = min(top_k + 1, len(profiles))
    model = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=neighbor_count)
    model.fit(tfidf)

    similarities: dict[str, list[RecommendationCandidate]] = {}
    # Query nearest neighbors in batches to avoid materializing an NxN similarity matrix.
    for start in range(0, len(profiles), max(batch_size, 1)):
        stop = min(start + max(batch_size, 1), len(profiles))
        distances, indices = model.kneighbors(tfidf[start:stop], return_distance=True)
        for row_offset, profile in enumerate(profiles[start:stop]):
            candidates: list[RecommendationCandidate] = []
            for distance, neighbor_index in zip(distances[row_offset], indices[row_offset]):
                neighbor = profiles[int(neighbor_index)]
                if neighbor.business_id == profile.business_id:
                    continue
                candidates.append(
                    RecommendationCandidate(
                        item_id=neighbor.business_id,
                        score=round(max(0.0, 1.0 - float(distance)), 6),
                    )
                )
                if len(candidates) >= top_k:
                    break
            similarities[profile.business_id] = candidates

    return YelpContentBuildResult(
        similarities=similarities,
        profiles=profiles,
        feature_count=len(vectorizer.get_feature_names_out()),
    )


def serialize_similarity(
    similarities: dict[str, list[RecommendationCandidate]],
) -> dict[str, list[dict[str, float | str]]]:
    """Convert internal candidates to the JSON shape read by SimilarityCache."""
    return {
        business_id: [
            {"business_id": candidate.item_id, "score": candidate.score}
            for candidate in candidates
        ]
        for business_id, candidates in similarities.items()
    }


def _optional_float(value: Any) -> float | None:
    """Coerce optional Yelp numeric fields without failing the full build."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
