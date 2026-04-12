from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.yelp_service import YelpService
from apps.recommendations.yelp_content import is_restaurant_business, iter_json_lines
from apps.users.demo_candidates import save_yelp_demo_candidates
from apps.users.models import User


@dataclass(frozen=True)
class ImportProfile:
    target_business_count: int
    target_user_count: int
    target_review_count: int
    min_business_review_count: int
    demo_candidate_count: int


PROFILE_DEFAULTS: dict[str, ImportProfile] = {
    "dev-demo": ImportProfile(
        target_business_count=1_000,
        target_user_count=10_000,
        target_review_count=50_000,
        min_business_review_count=20,
        demo_candidate_count=50,
    ),
    "balanced": ImportProfile(
        target_business_count=10_000,
        target_user_count=100_000,
        target_review_count=500_000,
        min_business_review_count=25,
        demo_candidate_count=100,
    ),
    "large": ImportProfile(
        target_business_count=50_000,
        target_user_count=300_000,
        target_review_count=1_500_000,
        min_business_review_count=10,
        demo_candidate_count=200,
    ),
}


@dataclass(frozen=True)
class ImportTargets:
    business_count: int | None
    user_count: int | None
    review_count: int | None
    min_business_review_count: int
    demo_candidate_count: int


@dataclass(frozen=True)
class ReviewUserSelection:
    user_ids: set[str]
    matched_business_review_rows: int
    selected_review_capacity: int


class Command(BaseCommand):
    help = "Import Yelp restaurant businesses, users, and reviews into database tables."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--mode",
            choices=["businesses", "users", "reviews", "all"],
            default="all",
        )
        parser.add_argument(
            "--data-dir",
            default="data/archive_4",
            help="Directory containing Yelp academic dataset JSON files.",
        )
        parser.add_argument("--business-limit", type=int, default=None)
        parser.add_argument("--user-limit", type=int, default=None)
        parser.add_argument("--review-limit", type=int, default=None)
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--include-closed", action="store_true")
        parser.add_argument(
            "--profile",
            choices=sorted(PROFILE_DEFAULTS),
            default=None,
            help="Sampling profile for demo-oriented imports.",
        )
        parser.add_argument("--target-business-count", type=int, default=None)
        parser.add_argument("--target-user-count", type=int, default=None)
        parser.add_argument("--target-review-count", type=int, default=None)
        parser.add_argument("--min-business-review-count", type=int, default=None)
        parser.add_argument("--demo-candidate-count", type=int, default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        data_dir = Path(options["data_dir"])
        if not data_dir.exists():
            raise CommandError(f"Data directory does not exist: {data_dir}")

        mode = options["mode"]
        batch_size = max(int(options["batch_size"]), 1)
        include_closed = bool(options["include_closed"])
        legacy_limits_enabled = any(
            options[key] is not None for key in ("business_limit", "user_limit", "review_limit")
        )
        targets = self._resolve_targets(options, legacy_limits_enabled=legacy_limits_enabled)

        selected_business_ids: set[str] | None = None
        selected_user_ids: set[str] | None = None

        if mode in {"businesses", "all"}:
            selected_business_ids = self._import_businesses(
                data_dir=data_dir,
                line_limit=options["business_limit"] if legacy_limits_enabled else None,
                batch_size=batch_size,
                include_closed=include_closed,
                targets=targets,
            )

        if mode in {"users", "all"}:
            if selected_business_ids is None and not legacy_limits_enabled:
                selected_business_ids = self._selected_business_ids_from_db(targets.business_count)
            selected_user_ids = self._import_users(
                data_dir=data_dir,
                line_limit=options["user_limit"] if legacy_limits_enabled else None,
                batch_size=batch_size,
                selected_business_ids=selected_business_ids,
                targets=targets,
            )

        if mode in {"reviews", "all"}:
            if selected_business_ids is None and not legacy_limits_enabled:
                selected_business_ids = self._selected_business_ids_from_db(targets.business_count)
            if selected_user_ids is None and not legacy_limits_enabled:
                selected_user_ids = self._selected_user_ids_from_db(targets.user_count)
            self._import_reviews(
                data_dir=data_dir,
                line_limit=options["review_limit"] if legacy_limits_enabled else None,
                batch_size=batch_size,
                selected_business_ids=selected_business_ids,
                selected_user_ids=selected_user_ids,
                targets=targets,
            )
            save_yelp_demo_candidates(candidate_count=targets.demo_candidate_count)

    def _resolve_targets(
        self,
        options: dict[str, Any],
        *,
        legacy_limits_enabled: bool,
    ) -> ImportTargets:
        profile_name = options["profile"] or "balanced"
        profile = PROFILE_DEFAULTS[profile_name]
        if legacy_limits_enabled:
            return ImportTargets(
                business_count=None,
                user_count=None,
                review_count=None,
                min_business_review_count=max(
                    int(options["min_business_review_count"] or 10),
                    1,
                ),
                demo_candidate_count=max(int(options["demo_candidate_count"] or 100), 0),
            )

        return ImportTargets(
            business_count=max(
                int(options["target_business_count"] or profile.target_business_count),
                1,
            ),
            user_count=max(
                int(options["target_user_count"] or profile.target_user_count),
                1,
            ),
            review_count=max(
                int(options["target_review_count"] or profile.target_review_count),
                1,
            ),
            min_business_review_count=max(
                int(options["min_business_review_count"] or profile.min_business_review_count),
                1,
            ),
            demo_candidate_count=max(
                int(options["demo_candidate_count"] or profile.demo_candidate_count),
                0,
            ),
        )

    def _import_businesses(
        self,
        *,
        data_dir: Path,
        line_limit: int | None,
        batch_size: int,
        include_closed: bool,
        targets: ImportTargets,
    ) -> set[str]:
        source = data_dir / "yelp_academic_dataset_business.json"
        if not source.exists():
            raise CommandError(f"Business file does not exist: {source}")

        selected_records = self._select_business_records(
            source=source,
            line_limit=line_limit,
            include_closed=include_closed,
            targets=targets,
        )

        batch: list[YelpBusiness] = []
        imported = 0
        selected_business_ids: set[str] = set()
        for record in selected_records:
            business_id = str(record.get("business_id") or "")
            if not business_id:
                continue
            selected_business_ids.add(business_id)
            batch.append(
                YelpBusiness(
                    business_id=business_id,
                    name=str(record.get("name") or ""),
                    categories=str(record.get("categories") or ""),
                    stars=_safe_float(record.get("stars")),
                    review_count=_safe_int(record.get("review_count")),
                    city=str(record.get("city") or ""),
                    state=str(record.get("state") or ""),
                    latitude=_safe_optional_float(record.get("latitude")),
                    longitude=_safe_optional_float(record.get("longitude")),
                    is_open=record.get("is_open") != 0,
                )
            )
            if len(batch) >= batch_size:
                imported += self._upsert_businesses(batch)
                batch = []

        if batch:
            imported += self._upsert_businesses(batch)

        self.stdout.write(self.style.SUCCESS(f"Imported/updated {imported} Yelp businesses."))
        return selected_business_ids

    def _import_users(
        self,
        *,
        data_dir: Path,
        line_limit: int | None,
        batch_size: int,
        selected_business_ids: set[str] | None,
        targets: ImportTargets,
    ) -> set[str]:
        source = data_dir / "yelp_academic_dataset_user.json"
        if not source.exists():
            raise CommandError(f"User file does not exist: {source}")

        selected_user_ids: set[str] | None = None
        if line_limit is None and selected_business_ids:
            selection = self._collect_target_user_ids(
                review_source=data_dir / "yelp_academic_dataset_review.json",
                selected_business_ids=selected_business_ids,
                target_review_count=targets.review_count,
                target_user_count=targets.user_count,
            )
            selected_user_ids = selection.user_ids

        batch: list[User] = []
        imported = 0
        scanned_rows = 0
        skipped_not_selected = 0
        imported_external_user_ids: set[str] = set()
        for record in iter_json_lines(source, limit=line_limit):
            scanned_rows += 1
            external_user_id = str(record.get("user_id") or "")
            if not external_user_id:
                continue
            if selected_user_ids is not None and external_user_id not in selected_user_ids:
                skipped_not_selected += 1
                continue

            imported_external_user_ids.add(external_user_id)
            username = _build_yelp_username(external_user_id)
            display_name = str(record.get("name") or "").strip()
            batch.append(
                User(
                    username=username,
                    password=make_password(None),
                    email=None,
                    phone=None,
                    info=(f"Yelp user: {display_name}" if display_name else None),
                    source="yelp",
                    external_user_id=external_user_id,
                )
            )
            if len(batch) >= batch_size:
                imported += self._upsert_users(batch)
                batch = []

        if batch:
            imported += self._upsert_users(batch)

        self.stdout.write(
            self.style.SUCCESS(
                "Imported/updated "
                f"{imported} Yelp users. "
                f"Scanned {scanned_rows} rows; skipped {skipped_not_selected} non-target users."
            )
        )
        return imported_external_user_ids

    def _import_reviews(
        self,
        *,
        data_dir: Path,
        line_limit: int | None,
        batch_size: int,
        selected_business_ids: set[str] | None,
        selected_user_ids: set[str] | None,
        targets: ImportTargets,
    ) -> None:
        source = data_dir / "yelp_academic_dataset_review.json"
        if not source.exists():
            raise CommandError(f"Review file does not exist: {source}")

        if selected_business_ids is None:
            selected_business_ids = set(YelpBusiness.objects.values_list("business_id", flat=True))
        if not selected_business_ids:
            raise CommandError("No Yelp businesses found. Import businesses before reviews.")
        if selected_user_ids is None:
            selected_user_ids = set(
                User.objects.filter(source="yelp", external_user_id__isnull=False).values_list(
                    "external_user_id",
                    flat=True,
                )
            )
        if not selected_user_ids:
            raise CommandError("No Yelp users found. Import users before reviews.")

        business_pk_map = YelpBusiness.objects.in_bulk(selected_business_ids, field_name="business_id")
        review_limit = line_limit if line_limit is not None else targets.review_count
        batch: list[YelpReview] = []
        buffered_records: list[dict[str, Any]] = []
        user_cache: dict[str, int] = {}
        imported = 0
        scanned_rows = 0
        selected_rows = 0
        skipped_missing_review_id = 0
        skipped_missing_business = 0
        skipped_missing_user = 0
        skipped_user_not_selected = 0
        skipped_business_not_selected = 0
        affected_business_ids: set[int] = set()

        for record in iter_json_lines(source, limit=line_limit):
            scanned_rows += 1
            review_id = str(record.get("review_id") or "")
            business_id = str(record.get("business_id") or "")
            external_user_id = str(record.get("user_id") or "")

            if not review_id:
                skipped_missing_review_id += 1
                continue
            if business_id not in selected_business_ids:
                skipped_business_not_selected += 1
                continue
            if external_user_id not in selected_user_ids:
                skipped_user_not_selected += 1
                continue

            buffered_records.append(record)
            selected_rows += 1
            if review_limit is not None and selected_rows >= review_limit:
                imported += self._flush_review_batch(
                    buffered_records=buffered_records,
                    batch=batch,
                    business_pk_map=business_pk_map,
                    user_cache=user_cache,
                    affected_business_ids=affected_business_ids,
                )
                buffered_records = []
                batch = []
                break

            if len(buffered_records) >= batch_size:
                imported += self._flush_review_batch(
                    buffered_records=buffered_records,
                    batch=batch,
                    business_pk_map=business_pk_map,
                    user_cache=user_cache,
                    affected_business_ids=affected_business_ids,
                )
                buffered_records = []
                batch = []

        if buffered_records:
            imported += self._flush_review_batch(
                buffered_records=buffered_records,
                batch=batch,
                business_pk_map=business_pk_map,
                user_cache=user_cache,
                affected_business_ids=affected_business_ids,
            )
            buffered_records = []
            batch = []

        missing_user_rows = max(selected_rows - imported, 0)
        if missing_user_rows:
            skipped_missing_user += missing_user_rows

        YelpService.refresh_aggregated_review_counts(sorted(affected_business_ids))
        self.stdout.write(
            self.style.SUCCESS(
                "Imported/updated "
                f"{imported} Yelp reviews. "
                f"Scanned {scanned_rows} rows; "
                f"matched business filter {selected_rows}; "
                f"skipped business_not_target={skipped_business_not_selected}, "
                f"user_not_target={skipped_user_not_selected}, "
                f"missing review_id={skipped_missing_review_id}, "
                f"missing business={skipped_missing_business}, "
                f"missing user={skipped_missing_user}. "
                f"Incrementally refreshed {len(affected_business_ids)} businesses."
            )
        )

    def _select_business_records(
        self,
        *,
        source: Path,
        line_limit: int | None,
        include_closed: bool,
        targets: ImportTargets,
    ) -> list[dict[str, Any]]:
        selected = self._collect_business_records(
            source=source,
            line_limit=line_limit,
            include_closed=include_closed,
            min_business_review_count=targets.min_business_review_count,
        )
        if not selected and line_limit is None:
            selected = self._collect_business_records(
                source=source,
                line_limit=line_limit,
                include_closed=include_closed,
                min_business_review_count=1,
            )

        if targets.business_count is None:
            return selected

        selected.sort(
            key=lambda item: (
                -_safe_int(item.get("review_count")),
                str(item.get("city") or ""),
                str(item.get("business_id") or ""),
            )
        )
        return selected[: targets.business_count]

    def _collect_business_records(
        self,
        *,
        source: Path,
        line_limit: int | None,
        include_closed: bool,
        min_business_review_count: int,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for record in iter_json_lines(source, limit=line_limit):
            if not is_restaurant_business(
                record,
                min_review_count=min_business_review_count,
                include_closed=include_closed,
            ):
                continue
            selected.append(record)
        return selected

    def _collect_target_user_ids(
        self,
        *,
        review_source: Path,
        selected_business_ids: set[str],
        target_review_count: int | None,
        target_user_count: int | None,
    ) -> ReviewUserSelection:
        if not review_source.exists():
            raise CommandError(f"Review file does not exist: {review_source}")

        user_counts: Counter[str] = Counter()
        matched_business_review_rows = 0
        for record in iter_json_lines(review_source):
            business_id = str(record.get("business_id") or "")
            external_user_id = str(record.get("user_id") or "")
            if business_id not in selected_business_ids or not external_user_id:
                continue
            matched_business_review_rows += 1
            user_counts[external_user_id] += 1

        selected_users = [
            user_id
            for user_id, _count in sorted(
                user_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        if target_user_count is not None:
            selected_users = selected_users[:target_user_count]
        selected_user_ids = set(selected_users)

        selected_review_capacity = sum(
            count for user_id, count in user_counts.items() if user_id in selected_user_ids
        )
        if target_review_count is not None:
            selected_review_capacity = min(selected_review_capacity, target_review_count)

        return ReviewUserSelection(
            user_ids=selected_user_ids,
            matched_business_review_rows=matched_business_review_rows,
            selected_review_capacity=selected_review_capacity,
        )

    def _selected_business_ids_from_db(self, limit: int | None) -> set[str]:
        queryset = YelpBusiness.objects.order_by("-review_count", "business_id").values_list(
            "business_id",
            flat=True,
        )
        if limit is not None:
            queryset = queryset[:limit]
        return set(queryset)

    def _selected_user_ids_from_db(self, limit: int | None) -> set[str]:
        queryset = User.objects.filter(source="yelp", external_user_id__isnull=False).order_by(
            "id"
        ).values_list("external_user_id", flat=True)
        if limit is not None:
            queryset = queryset[:limit]
        return set(queryset)

    def _flush_review_batch(
        self,
        *,
        buffered_records: list[dict[str, Any]],
        batch: list[YelpReview],
        business_pk_map: dict[str, YelpBusiness],
        user_cache: dict[str, int],
        affected_business_ids: set[int],
    ) -> int:
        if not buffered_records:
            return 0

        missing_external_user_ids = {
            str(record.get("user_id") or "")
            for record in buffered_records
            if str(record.get("user_id") or "") and str(record.get("user_id") or "") not in user_cache
        }
        if missing_external_user_ids:
            for user in User.objects.filter(
                source="yelp",
                external_user_id__in=missing_external_user_ids,
            ).only("id", "external_user_id"):
                if user.external_user_id:
                    user_cache[user.external_user_id] = user.id

        for record in buffered_records:
            business = business_pk_map.get(str(record.get("business_id") or ""))
            user_id = user_cache.get(str(record.get("user_id") or ""))
            if business is None or user_id is None:
                continue
            batch.append(
                YelpReview(
                    review_id=str(record.get("review_id") or ""),
                    business_id=business.id,
                    user_id=user_id,
                    stars=_safe_float(record.get("stars")),
                    text=str(record.get("text") or ""),
                    source="yelp",
                    review_date=_parse_review_date(record.get("date")),
                )
            )
            affected_business_ids.add(business.id)

        if not batch:
            return 0

        imported = self._upsert_reviews(batch)
        batch.clear()
        return imported

    @staticmethod
    def _upsert_businesses(batch: Iterable[YelpBusiness]) -> int:
        items = list(batch)
        existing = YelpBusiness.objects.in_bulk(
            [item.business_id for item in items],
            field_name="business_id",
        )
        creates: list[YelpBusiness] = []
        updates: list[YelpBusiness] = []
        for item in items:
            current = existing.get(item.business_id)
            if current is None:
                creates.append(item)
                continue
            current.name = item.name
            current.categories = item.categories
            current.stars = item.stars
            current.review_count = item.review_count
            current.city = item.city
            current.state = item.state
            current.latitude = item.latitude
            current.longitude = item.longitude
            current.is_open = item.is_open
            updates.append(current)

        if creates:
            YelpBusiness.objects.bulk_create(creates, ignore_conflicts=True)
        if updates:
            YelpBusiness.objects.bulk_update(
                updates,
                [
                    "name",
                    "categories",
                    "stars",
                    "review_count",
                    "city",
                    "state",
                    "latitude",
                    "longitude",
                    "is_open",
                ],
            )
        return len(items)

    @staticmethod
    def _upsert_users(batch: Iterable[User]) -> int:
        items = list(batch)
        existing = User.objects.in_bulk([item.username for item in items], field_name="username")
        creates: list[User] = []
        updates: list[User] = []
        for item in items:
            current = existing.get(item.username)
            if current is None:
                creates.append(item)
                continue
            current.password = item.password
            current.info = item.info
            current.source = item.source
            current.external_user_id = item.external_user_id
            updates.append(current)

        if creates:
            User.objects.bulk_create(creates, ignore_conflicts=True)
        if updates:
            User.objects.bulk_update(
                updates,
                ["password", "info", "source", "external_user_id"],
            )
        return len(items)

    @staticmethod
    def _upsert_reviews(batch: Iterable[YelpReview]) -> int:
        items = list(batch)
        existing = YelpReview.objects.in_bulk(
            [item.review_id for item in items],
            field_name="review_id",
        )
        creates: list[YelpReview] = []
        updates: list[YelpReview] = []
        for item in items:
            current = existing.get(item.review_id)
            if current is None:
                creates.append(item)
                continue
            current.business_id = item.business_id
            current.user_id = item.user_id
            current.stars = item.stars
            current.text = item.text
            current.source = item.source
            current.review_date = item.review_date
            updates.append(current)

        if creates:
            YelpReview.objects.bulk_create(creates, ignore_conflicts=True)
        if updates:
            YelpReview.objects.bulk_update(
                updates,
                ["business", "user", "stars", "text", "source", "review_date"],
            )
        return len(items)


def _build_yelp_username(external_user_id: str) -> str:
    return f"yelp_{external_user_id}"[:255]


def _safe_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_review_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    except ValueError:
        return None
