from __future__ import annotations

from django.db import models


class YelpBusiness(models.Model):
    business_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    categories = models.TextField(blank=True, default="")
    stars = models.FloatField(default=0.0)
    review_count = models.PositiveIntegerField(default=0, db_index=True)
    city = models.CharField(max_length=120, blank=True, default="")
    state = models.CharField(max_length=32, blank=True, default="", db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    aggregated_review_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "yelp_business"
        ordering = ["-review_count", "-stars", "name"]
        indexes = [
            models.Index(fields=["state", "city"]),
        ]

    def __str__(self) -> str:
        return self.name


class YelpReview(models.Model):
    review_id = models.CharField(max_length=32, unique=True)
    business = models.ForeignKey(
        YelpBusiness,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="yelp_reviews",
    )
    stars = models.FloatField(default=0.0)
    text = models.TextField(blank=True, default="")
    review_date = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "yelp_review"
        ordering = ["-review_date", "-id"]
        indexes = [
            models.Index(fields=["business", "review_date"]),
            models.Index(fields=["user", "review_date"]),
        ]

    def __str__(self) -> str:
        return self.review_id
