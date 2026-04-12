from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.yelp_content import is_restaurant_business, iter_json_lines
from apps.users.models import User


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

    def handle(self, *args: Any, **options: Any) -> None:
        data_dir = Path(options["data_dir"])
        if not data_dir.exists():
            raise CommandError(f"Data directory does not exist: {data_dir}")

        mode = options["mode"]
        batch_size = max(int(options["batch_size"]), 1)
        include_closed = bool(options["include_closed"])

        if mode in {"businesses", "all"}:
            self._import_businesses(
                data_dir=data_dir,
                line_limit=options["business_limit"],
                batch_size=batch_size,
                include_closed=include_closed,
            )
        if mode in {"users", "all"}:
            self._import_users(
                data_dir=data_dir,
                line_limit=options["user_limit"],
                batch_size=batch_size,
            )
        if mode in {"reviews", "all"}:
            self._import_reviews(
                data_dir=data_dir,
                line_limit=options["review_limit"],
                batch_size=batch_size,
            )

    def _import_businesses(
        self,
        *,
        data_dir: Path,
        line_limit: int | None,
        batch_size: int,
        include_closed: bool,
    ) -> None:
        source = data_dir / "yelp_academic_dataset_business.json"
        if not source.exists():
            raise CommandError(f"Business file does not exist: {source}")

        batch: list[YelpBusiness] = []
        imported = 0
        for record in iter_json_lines(source, limit=line_limit):
            if not is_restaurant_business(record, include_closed=include_closed):
                continue
            business_id = str(record.get("business_id") or "")
            if not business_id:
                continue

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

    def _import_users(
        self,
        *,
        data_dir: Path,
        line_limit: int | None,
        batch_size: int,
    ) -> None:
        source = data_dir / "yelp_academic_dataset_user.json"
        if not source.exists():
            raise CommandError(f"User file does not exist: {source}")

        batch: list[User] = []
        imported = 0
        for record in iter_json_lines(source, limit=line_limit):
            external_user_id = str(record.get("user_id") or "")
            if not external_user_id:
                continue

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

        self.stdout.write(self.style.SUCCESS(f"Imported/updated {imported} Yelp users."))

    def _import_reviews(
        self,
        *,
        data_dir: Path,
        line_limit: int | None,
        batch_size: int,
    ) -> None:
        source = data_dir / "yelp_academic_dataset_review.json"
        if not source.exists():
            raise CommandError(f"Review file does not exist: {source}")

        business_ids = set(YelpBusiness.objects.values_list("business_id", flat=True))
        user_map = {
            user.external_user_id: user.id
            for user in User.objects.filter(source="yelp", external_user_id__isnull=False).only(
                "id", "external_user_id"
            )
        }
        if not business_ids:
            raise CommandError("No Yelp businesses found. Import businesses before reviews.")
        if not user_map:
            raise CommandError("No Yelp users found. Import users before reviews.")

        business_pk_map = YelpBusiness.objects.in_bulk(business_ids, field_name="business_id")
        batch: list[YelpReview] = []
        imported = 0
        skipped = 0

        for record in iter_json_lines(source, limit=line_limit):
            review_id = str(record.get("review_id") or "")
            business_id = str(record.get("business_id") or "")
            external_user_id = str(record.get("user_id") or "")
            business = business_pk_map.get(business_id)
            user_id = user_map.get(external_user_id)
            if not review_id or business is None or user_id is None:
                skipped += 1
                continue

            batch.append(
                YelpReview(
                    review_id=review_id,
                    business_id=business.id,
                    user_id=user_id,
                    stars=_safe_float(record.get("stars")),
                    text=str(record.get("text") or ""),
                    review_date=_parse_review_date(record.get("date")),
                )
            )
            if len(batch) >= batch_size:
                imported += self._upsert_reviews(batch)
                batch = []

        if batch:
            imported += self._upsert_reviews(batch)

        self._refresh_aggregated_review_counts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported/updated {imported} Yelp reviews. Skipped {skipped} rows missing business/user."
            )
        )

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
        existing = YelpReview.objects.in_bulk([item.review_id for item in items], field_name="review_id")
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
            current.review_date = item.review_date
            updates.append(current)

        if creates:
            YelpReview.objects.bulk_create(creates, ignore_conflicts=True)
        if updates:
            YelpReview.objects.bulk_update(
                updates,
                ["business", "user", "stars", "text", "review_date"],
            )
        return len(items)

    @staticmethod
    def _refresh_aggregated_review_counts() -> None:
        counts = YelpReview.objects.values("business_id").annotate(total=Count("id"))
        count_map = {row["business_id"]: row["total"] for row in counts}
        businesses = list(YelpBusiness.objects.all())
        for business in businesses:
            business.aggregated_review_count = count_map.get(business.id, 0)
        YelpBusiness.objects.bulk_update(businesses, ["aggregated_review_count"])


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
