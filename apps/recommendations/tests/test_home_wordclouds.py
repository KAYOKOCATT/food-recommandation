from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.foods.models import Foods
from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.home_wordcloud_service import HomeWordCloudService
from apps.users.models import User


class HomeWordCloudServiceTests(TestCase):
    def setUp(self) -> None:
        Foods.objects.create(
            foodname="宫保鸡丁",
            foodtype="川菜",
            recommend="经典川菜，麻辣鲜香",
            imgurl="/static/image/test-food.jpg",
            price="38.50",
        )
        business = YelpBusiness.objects.create(
            business_id="wc-b1",
            name="Word Cloud Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.8,
            review_count=88,
            city="Seattle",
            state="WA",
            is_open=True,
        )
        user = User.objects.create(
            username="wc-user",
            password="secret123",
            email="wc@example.com",
            phone="13800138997",
            source="yelp",
        )
        YelpReview.objects.create(
            review_id="wc-r1",
            business=business,
            user=user,
            stars=5.0,
            text="Fresh sushi and omakase with perfect rice and friendly chef.",
            source="yelp",
        )
        YelpReview.objects.create(
            review_id="wc-r2",
            business=business,
            user=user,
            stars=4.0,
            text="Fresh fish, omakase dinner, and excellent nigiri experience.",
            source="yelp",
        )
        YelpReview.objects.create(
            review_id="wc-r3",
            business=business,
            user=user,
            stars=4.0,
            text="Omakase menu with fresh sushi and excellent fish quality.",
            source="yelp",
        )

    def test_build_home_wordclouds_command_writes_png_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with patch.object(HomeWordCloudService, "DATA_DIR", data_dir), patch.object(
                HomeWordCloudService,
                "FOOD_WORDCLOUD_FILE",
                data_dir / "home_food_recommend_wordcloud.png",
            ), patch.object(
                HomeWordCloudService,
                "YELP_WORDCLOUD_FILE",
                data_dir / "home_yelp_review_wordcloud.png",
            ):
                call_command("build_home_wordclouds")

                self.assertTrue(HomeWordCloudService.FOOD_WORDCLOUD_FILE.exists())
                self.assertTrue(HomeWordCloudService.YELP_WORDCLOUD_FILE.exists())
                self.assertGreater(HomeWordCloudService.FOOD_WORDCLOUD_FILE.stat().st_size, 0)
                self.assertGreater(HomeWordCloudService.YELP_WORDCLOUD_FILE.stat().st_size, 0)

    def test_build_home_wordclouds_handles_empty_inputs(self) -> None:
        Foods.objects.all().delete()
        YelpReview.objects.all().delete()
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with patch.object(HomeWordCloudService, "DATA_DIR", data_dir), patch.object(
                HomeWordCloudService,
                "FOOD_WORDCLOUD_FILE",
                data_dir / "home_food_recommend_wordcloud.png",
            ), patch.object(
                HomeWordCloudService,
                "YELP_WORDCLOUD_FILE",
                data_dir / "home_yelp_review_wordcloud.png",
            ):
                outputs = HomeWordCloudService.build_all()

                self.assertTrue(outputs["food"].exists())
                self.assertTrue(outputs["yelp"].exists())
