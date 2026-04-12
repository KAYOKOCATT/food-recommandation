from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Max

from apps.users.models import User


@dataclass(frozen=True)
class YelpDemoCandidate:
    user_id: int
    username: str
    display_name: str
    review_count: int
    last_review_at: str | None


DEMO_CANDIDATE_FILE = (
    settings.BASE_DIR / "data" / "recommendations" / "yelp_demo_users.json"
)


def load_yelp_demo_candidates(
    *,
    limit: int = 30,
    source_path: str | Path | None = None,
) -> list[YelpDemoCandidate]:
    path = Path(source_path) if source_path else DEMO_CANDIDATE_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    if not isinstance(payload, list):
        return []

    candidates: list[YelpDemoCandidate] = []
    for item in payload[: max(limit, 0)]:
        if not isinstance(item, dict):
            continue
        try:
            candidates.append(
                YelpDemoCandidate(
                    user_id=int(item["user_id"]),
                    username=str(item.get("username") or ""),
                    display_name=str(item.get("display_name") or item.get("username") or ""),
                    review_count=max(int(item.get("review_count") or 0), 0),
                    last_review_at=(
                        str(item["last_review_at"])
                        if item.get("last_review_at") is not None
                        else None
                    ),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return candidates


def save_yelp_demo_candidates(
    *,
    candidate_count: int = 100,
    output_path: str | Path | None = None,
) -> list[YelpDemoCandidate]:
    queryset = (
        User.objects.filter(source="yelp")
        .annotate(
            review_count=Count("yelp_reviews"),
            last_review_at=Max("yelp_reviews__review_date"),
        )
        .filter(review_count__gt=0)
        .order_by("-review_count", "-last_review_at", "id")
    )

    candidates = [
        YelpDemoCandidate(
            user_id=user.id,
            username=user.username,
            display_name=_resolve_display_name(user),
            review_count=int(user.review_count),
            last_review_at=user.last_review_at.isoformat() if user.last_review_at else None,
        )
        for user in queryset[: max(candidate_count, 0)]
    ]

    path = Path(output_path) if output_path else DEMO_CANDIDATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "user_id": candidate.user_id,
                    "username": candidate.username,
                    "display_name": candidate.display_name,
                    "review_count": candidate.review_count,
                    "last_review_at": candidate.last_review_at,
                }
                for candidate in candidates
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return candidates


def candidate_user_ids(
    *,
    limit: int | None = None,
    source_path: str | Path | None = None,
) -> set[int]:
    candidates = load_yelp_demo_candidates(
        limit=limit if limit is not None else 10_000,
        source_path=source_path,
    )
    return {candidate.user_id for candidate in candidates}


def _resolve_display_name(user: User) -> str:
    info = (user.info or "").strip()
    if info.startswith("Yelp user: "):
        display_name = info.removeprefix("Yelp user: ").strip()
        if display_name:
            return display_name
    return user.username
