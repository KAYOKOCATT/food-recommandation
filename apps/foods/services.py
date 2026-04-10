from django.db.models import Count, QuerySet

from .models import Foods


def popular_foods(limit: int = 20) -> QuerySet[Foods]:
    """Statistical fallback for Chinese dish data without reliable behavior records."""
    safe_limit = max(limit, 1)
    return (
        Foods.objects.annotate(
            collect_count=Count("collect", distinct=True),
        )
        .order_by("-collect_count", "foodtype", "foodname")[:safe_limit]
    )
