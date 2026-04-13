from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.yelp_service import YelpService
from apps.users.models import User


class YelpServiceTests(TestCase):
    def setUp(self) -> None:
        self.business_1 = YelpBusiness.objects.create(
            business_id="b1",
            name="Alpha Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.5,
            review_count=120,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.business_2 = YelpBusiness.objects.create(
            business_id="b2",
            name="Beta Sushi",
            categories="Restaurants, Japanese",
            stars=4.2,
            review_count=80,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )

    def test_get_similar_businesses_hydrates_from_similarity_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps({"b1": [{"business_id": "b2", "score": 0.91}]}),
                encoding="utf-8",
            )

            result = YelpService.get_similar_businesses(
                "b1",
                top_k=6,
                similarity_file=similarity_path,
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].business.business_id, "b2")
        self.assertEqual(result[0].score, 0.91)

    def test_build_business_queryset_filters_by_keyword(self) -> None:
        queryset = YelpService.build_business_queryset(q="Alpha")

        self.assertEqual(list(queryset.values_list("business_id", flat=True)), ["b1"])

    def test_get_similar_businesses_returns_empty_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"
            result = YelpService.get_similar_businesses(
                "b1",
                top_k=6,
                similarity_file=missing_path,
            )

        self.assertEqual(result, [])

    def test_get_similar_businesses_returns_empty_when_json_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text("{invalid", encoding="utf-8")

            result = YelpService.get_similar_businesses(
                "b1",
                top_k=6,
                similarity_file=similarity_path,
            )

        self.assertEqual(result, [])

    def test_get_similar_businesses_skips_candidates_missing_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps({"b1": [{"business_id": "missing", "score": 0.91}]}),
                encoding="utf-8",
            )

            result = YelpService.get_similar_businesses(
                "b1",
                top_k=6,
                similarity_file=similarity_path,
            )

        self.assertEqual(result, [])

    def test_build_business_queryset_filters_open_businesses(self) -> None:
        self.business_2.is_open = False
        self.business_2.save(update_fields=["is_open"])

        queryset = YelpService.build_business_queryset(is_open_only=True)

        self.assertEqual(list(queryset.values_list("business_id", flat=True)), ["b1"])

    def test_get_usercf_recommendations_hydrates_from_json_and_skips_seen(self) -> None:
        user = User.objects.create(
            username="local-user",
            password="secret123",
            email="local@example.com",
            phone="13800138001",
        )
        YelpReview.objects.create(
            review_id="local_r1",
            business=self.business_1,
            user=user,
            stars=5.0,
            source="local",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            recommendation_path = Path(temp_dir) / "yelp_usercf.json"
            recommendation_path.write_text(
                json.dumps(
                    {
                        str(user.id): [
                            {"business_id": "b1", "score": 4.9},
                            {"business_id": "b2", "score": 4.7},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = YelpService.get_usercf_recommendations(
                user.id,
                top_k=5,
                recommendation_file=recommendation_path,
            )

        self.assertEqual([item.business.business_id for item in result], ["b2"])

    def test_get_usercf_recommendations_returns_empty_when_json_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            recommendation_path = Path(temp_dir) / "yelp_usercf.json"
            recommendation_path.write_text("{invalid", encoding="utf-8")

            result = YelpService.get_usercf_recommendations(
                1,
                recommendation_file=recommendation_path,
            )

        self.assertEqual(result, [])

    def test_get_recent_recommendations_uses_recent_reviews_and_similarity(self) -> None:
        user = User.objects.create(
            username="recent-user",
            password="secret123",
            email="recent@example.com",
            phone="13800138002",
        )
        business_3 = YelpBusiness.objects.create(
            business_id="b3",
            name="Gamma Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.8,
            review_count=300,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        YelpReview.objects.create(
            review_id="recent_r1",
            business=self.business_1,
            user=user,
            stars=5.0,
            source="local",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps(
                    {
                        "b1": [
                            {"business_id": "b1", "score": 0.99},
                            {"business_id": "b3", "score": 0.91},
                            {"business_id": "b2", "score": 0.60},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result, has_recent_activity = YelpService.get_recent_recommendations(
                user.id,
                top_k=2,
                similarity_file=similarity_path,
            )

        self.assertTrue(has_recent_activity)
        self.assertEqual([item.business.business_id for item in result], ["b3", "b2"])

    def test_get_recent_recommendations_falls_back_to_popular_when_no_recent_reviews(self) -> None:
        user = User.objects.create(
            username="fallback-user",
            password="secret123",
            email="fallback@example.com",
            phone="13800138003",
        )

        result, has_recent_activity = YelpService.get_recent_recommendations(user.id, top_k=2)

        self.assertFalse(has_recent_activity)
        self.assertEqual([item.business.business_id for item in result], ["b1", "b2"])


class YelpViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.business = YelpBusiness.objects.create(
            business_id="b1",
            name="Alpha Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.5,
            review_count=120,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.user = User.objects.create(
            username="reviewer",
            password="secret123",
            email="reviewer@example.com",
            phone="13800138000",
        )
        self.business.reviews.create(
            review_id="r1",
            user=self.user,
            stars=5.0,
            text="Excellent omakase.",
        )
        for index in range(2, 22):
            YelpBusiness.objects.create(
                business_id=f"b{index}",
                name=f"Restaurant {index}",
                categories="Restaurants, Cafes",
                stars=4.0,
                review_count=100 - index,
                city="Philadelphia" if index % 2 == 0 else "Boston",
                state="PA" if index % 2 == 0 else "MA",
                is_open=True,
            )

    def test_yelp_business_list_renders(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Sushi")
        self.assertNotContains(response, "查看为你推荐")

    def test_yelp_business_list_shows_recommendation_entry_for_yelp_demo_user(self) -> None:
        demo_user = User.objects.create(
            username="demo-user",
            password="!",
            email="demo@example.com",
            phone="13800138998",
            source="yelp",
        )
        session = self.client.session
        session["user_id"] = demo_user.id
        session["auth_role"] = "user"
        session["login_source"] = "yelp_demo"
        session["is_demo_login"] = True
        session.save()

        response = self.client.get("/api/v1/yelp/restaurants/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "查看为你推荐")

    def test_yelp_business_list_shows_recommendation_entry_for_local_user(self) -> None:
        session = self.client.session
        session["user_id"] = self.user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

        response = self.client.get("/api/v1/yelp/restaurants/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "查看为你推荐")

    def test_yelp_business_list_filters_by_query_and_city(self) -> None:
        response = self.client.get(
            "/api/v1/yelp/restaurants/",
            {"q": "Alpha", "city": "Philadelphia"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Sushi")
        self.assertNotContains(response, "Restaurant 3")

    def test_yelp_business_list_filters_open_businesses(self) -> None:
        closed_business = YelpBusiness.objects.create(
            business_id="closed-biz",
            name="Closed Cafe",
            categories="Restaurants, Cafes",
            stars=4.0,
            review_count=5,
            city="Philadelphia",
            state="PA",
            is_open=False,
        )

        response = self.client.get("/api/v1/yelp/restaurants/", {"is_open": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Sushi")
        self.assertNotContains(response, closed_business.name)

    def test_yelp_business_list_renders_empty_state_for_no_matches(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/", {"q": "does-not-exist"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "暂无可展示的 Yelp 餐厅数据。")

    def test_yelp_business_list_supports_pagination(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/", {"page": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 / 2")

    def test_yelp_business_list_invalid_page_falls_back_to_first_page(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/", {"page": "bad"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 / 2")

    def test_yelp_business_detail_renders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(json.dumps({"b1": []}), encoding="utf-8")
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get(
                    f"/api/v1/yelp/restaurants/{self.business.business_id}/"
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent omakase.")

    def test_yelp_business_detail_renders_empty_reviews_state(self) -> None:
        business = YelpBusiness.objects.create(
            business_id="empty-reviews",
            name="No Review Cafe",
            categories="Restaurants, Cafes",
            stars=4.0,
            review_count=0,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(json.dumps({"empty-reviews": []}), encoding="utf-8")
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get(
                    f"/api/v1/yelp/restaurants/{business.business_id}/"
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "当前餐厅暂无可展示的评论。")

    def test_yelp_business_detail_returns_404_for_unknown_business(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/missing/")

        self.assertEqual(response.status_code, 404)

    def test_yelp_business_detail_degrades_when_similarity_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"
            with patch.object(YelpService, "SIMILARITY_FILE", missing_path):
                response = self.client.get(
                    f"/api/v1/yelp/restaurants/{self.business.business_id}/"
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "当前餐厅暂无相似推荐。")

    def test_yelp_business_detail_degrades_when_similarity_json_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text("{invalid", encoding="utf-8")
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get(
                    f"/api/v1/yelp/restaurants/{self.business.business_id}/"
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "当前餐厅暂无相似推荐。")

    def test_yelp_business_detail_skips_missing_candidate_businesses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps({"b1": [{"business_id": "missing", "score": 0.91}]}),
                encoding="utf-8",
            )
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get(
                    f"/api/v1/yelp/restaurants/{self.business.business_id}/"
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "当前餐厅暂无相似推荐。")

    def test_yelp_business_detail_allows_yelp_demo_user_to_submit_review(self) -> None:
        demo_user = User.objects.create(
            username="demo-user-write",
            password="!",
            email="demo-write@example.com",
            phone="13800138997",
            source="yelp",
        )
        session = self.client.session
        session["user_id"] = demo_user.id
        session["auth_role"] = "user"
        session["login_source"] = "yelp_demo"
        session["is_demo_login"] = True
        session.save()

        response = self.client.get(f"/api/v1/yelp/restaurants/{self.business.business_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "已登录用户可提交评分")
        self.assertContains(response, "提交评分")

    def test_submit_yelp_review_requires_login(self) -> None:
        response = self.client.post(
            f"/api/v1/yelp/restaurants/{self.business.business_id}/review/",
            {"stars": "5", "comment": "Love it"},
        )

        self.assertEqual(response.status_code, 401)

    def test_submit_yelp_review_validates_stars(self) -> None:
        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

        response = self.client.post(
            f"/api/v1/yelp/restaurants/{self.business.business_id}/review/",
            {"stars": "6", "comment": "Too high"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(YelpReview.objects.filter(source="local").count(), 0)

    def test_submit_yelp_review_creates_multiple_local_reviews(self) -> None:
        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

        url = f"/api/v1/yelp/restaurants/{self.business.business_id}/review/"
        first = self.client.post(url, {"stars": "4", "comment": "Pretty good"})
        second = self.client.post(url, {"stars": "5", "comment": "Actually great"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            YelpReview.objects.filter(
                business=self.business,
                user=self.user,
                source="local",
            ).count(),
            2,
        )
        local_reviews = list(
            YelpReview.objects.filter(
                business=self.business,
                user=self.user,
                source="local",
            ).order_by("id")
        )
        self.business.refresh_from_db()
        self.assertEqual(local_reviews[0].text, "Pretty good")
        self.assertEqual(local_reviews[1].stars, 5.0)
        self.assertEqual(local_reviews[1].text, "Actually great")
        self.assertEqual(self.business.aggregated_review_count, 3)

    def test_submit_yelp_review_allows_yelp_demo_user(self) -> None:
        demo_user = User.objects.create(
            username="demo-user",
            password="!",
            email="demo@example.com",
            phone="13800138999",
            source="yelp",
        )
        session = self.client.session
        session["user_id"] = demo_user.id
        session["auth_role"] = "user"
        session["login_source"] = "yelp_demo"
        session["is_demo_login"] = True
        session.save()

        response = self.client.post(
            f"/api/v1/yelp/restaurants/{self.business.business_id}/review/",
            {"stars": "5", "comment": "Love it"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            YelpReview.objects.filter(
                business=self.business,
                user=demo_user,
                source="local",
            ).count(),
            1,
        )

    def test_yelp_recommendations_uses_recent_activity_copy(self) -> None:
        session = self.client.session
        session["user_id"] = self.user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

        candidate_business = YelpBusiness.objects.create(
            business_id="recent-rec",
            name="Recent Rank Sushi",
            categories="Restaurants, Japanese",
            stars=4.9,
            review_count=500,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        YelpReview.objects.create(
            review_id="local_recent_review",
            business=self.business,
            user=self.user,
            stars=5.0,
            source="local",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps(
                    {
                        "b1": [
                            {"business_id": candidate_business.business_id, "score": 0.95}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get("/api/v1/yelp/recommendations/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "基于你最近评分过的餐厅生成")
        self.assertContains(response, "Recent Rank Sushi")

    def test_yelp_recommendations_falls_back_to_popular_copy(self) -> None:
        session = self.client.session
        session["user_id"] = self.user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

        response = self.client.get("/api/v1/yelp/recommendations/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "以下先展示热门餐厅作为兜底结果。")
        self.assertContains(response, "Alpha Sushi")

    def test_yelp_recommendations_renders_for_yelp_demo_user_with_local_review(self) -> None:
        demo_user = User.objects.create(
            username="demo-user-recent",
            password="!",
            email="demo-recent@example.com",
            phone="13800138996",
            source="yelp",
        )
        session = self.client.session
        session["user_id"] = demo_user.id
        session["auth_role"] = "user"
        session["login_source"] = "yelp_demo"
        session["is_demo_login"] = True
        session.save()

        candidate_business = YelpBusiness.objects.create(
            business_id="recent-demo-rec",
            name="Demo Recent Sushi",
            categories="Restaurants, Japanese",
            stars=4.8,
            review_count=320,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        YelpReview.objects.create(
            review_id="demo_local_recent_review",
            business=self.business,
            user=demo_user,
            stars=4.0,
            source="local",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps(
                    {
                        "b1": [
                            {"business_id": candidate_business.business_id, "score": 0.93}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get("/api/v1/yelp/recommendations/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "基于你最近评分过的餐厅生成")
        self.assertContains(response, "Demo Recent Sushi")


class YelpReviewUserCFCommandTests(TestCase):
    def setUp(self) -> None:
        self.business_1 = YelpBusiness.objects.create(
            business_id="b1",
            name="Alpha Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.5,
            review_count=120,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.business_2 = YelpBusiness.objects.create(
            business_id="b2",
            name="Beta Sushi",
            categories="Restaurants, Japanese",
            stars=4.2,
            review_count=80,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.business_3 = YelpBusiness.objects.create(
            business_id="b3",
            name="Gamma Noodles",
            categories="Restaurants, Noodles",
            stars=4.1,
            review_count=60,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.business_4 = YelpBusiness.objects.create(
            business_id="b4",
            name="Delta BBQ",
            categories="Restaurants, BBQ",
            stars=4.0,
            review_count=55,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.user_1 = User.objects.create(
            username="user1",
            password="secret123",
            email="user1@example.com",
            phone="13800138100",
        )
        self.user_2 = User.objects.create(
            username="user2",
            password="secret123",
            email="user2@example.com",
            phone="13800138101",
        )
        self.user_3 = User.objects.create(
            username="user3",
            password="secret123",
            email="user3@example.com",
            phone="13800138102",
        )

    def test_build_yelp_review_usercf_writes_ranked_recommendations(self) -> None:
        ratings = [
            (self.user_1, self.business_1, 5),
            (self.user_1, self.business_2, 4),
            (self.user_1, self.business_3, 2),
            (self.user_2, self.business_1, 5),
            (self.user_2, self.business_2, 4),
            (self.user_2, self.business_3, 2),
            (self.user_2, self.business_4, 5),
            (self.user_3, self.business_1, 4),
            (self.user_3, self.business_2, 5),
            (self.user_3, self.business_3, 2),
            (self.user_3, self.business_4, 4),
        ]
        for index, (user, business, stars) in enumerate(ratings, start=1):
            YelpReview.objects.create(
                review_id=f"r{index}",
                business=business,
                user=user,
                stars=stars,
                source="local",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "yelp_usercf.json"
            call_command(
                "build_yelp_review_usercf",
                "--output",
                str(output_path),
                "--top-k",
                "3",
                "--similar-user-k",
                "2",
                "--min-user-reviews",
                "2",
                "--min-business-reviews",
                "2",
                "--min-common-items",
                "2",
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload[str(self.user_1.id)][0]["business_id"], "b4")
        self.assertGreater(payload[str(self.user_1.id)][0]["score"], 4.0)

    def test_build_yelp_review_usercf_skips_when_filtered_interactions_are_empty(self) -> None:
        YelpReview.objects.create(
            review_id="r1",
            business=self.business_1,
            user=self.user_1,
            stars=5,
            source="local",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "yelp_usercf.json"
            call_command(
                "build_yelp_review_usercf",
                "--output",
                str(output_path),
                "--min-user-reviews",
                "2",
                "--min-business-reviews",
                "2",
            )

            self.assertFalse(output_path.exists())

    def test_build_yelp_review_usercf_uses_latest_review_per_user_business(self) -> None:
        ratings = [
            ("r1", self.user_1, self.business_1, 2),
            ("r2", self.user_1, self.business_1, 5),
            ("r3", self.user_1, self.business_2, 4),
            ("r4", self.user_1, self.business_3, 2),
            ("r5", self.user_2, self.business_1, 5),
            ("r6", self.user_2, self.business_2, 4),
            ("r7", self.user_2, self.business_3, 2),
            ("r8", self.user_2, self.business_4, 5),
            ("r9", self.user_3, self.business_1, 4),
            ("r10", self.user_3, self.business_2, 5),
            ("r11", self.user_3, self.business_3, 2),
            ("r12", self.user_3, self.business_4, 4),
        ]
        for review_id, user, business, stars in ratings:
            YelpReview.objects.create(
                review_id=review_id,
                business=business,
                user=user,
                stars=stars,
                source="local",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "yelp_usercf.json"
            call_command(
                "build_yelp_review_usercf",
                "--output",
                str(output_path),
                "--top-k",
                "3",
                "--similar-user-k",
                "2",
                "--min-user-reviews",
                "2",
                "--min-business-reviews",
                "2",
                "--min-common-items",
                "2",
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload[str(self.user_1.id)][0]["business_id"], "b4")

    def test_build_yelp_review_usercf_respects_build_set_limits(self) -> None:
        user_4 = User.objects.create(
            username="user4",
            password="secret123",
            email="user4@example.com",
            phone="13800138103",
        )
        ratings = [
            (self.user_1, self.business_1, 5),
            (self.user_1, self.business_2, 4),
            (self.user_1, self.business_3, 2),
            (self.user_2, self.business_1, 5),
            (self.user_2, self.business_2, 4),
            (self.user_2, self.business_4, 5),
            (self.user_3, self.business_1, 4),
            (self.user_3, self.business_2, 5),
            (self.user_3, self.business_4, 4),
            (user_4, self.business_1, 5),
        ]
        for index, (user, business, stars) in enumerate(ratings, start=1):
            YelpReview.objects.create(
                review_id=f"bounded-r{index}",
                business=business,
                user=user,
                stars=stars,
                source="local",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "yelp_usercf.json"
            call_command(
                "build_yelp_review_usercf",
                "--output",
                str(output_path),
                "--top-k",
                "3",
                "--similar-user-k",
                "2",
                "--min-user-reviews",
                "2",
                "--min-business-reviews",
                "2",
                "--min-common-items",
                "1",
                "--target-user-count",
                "3",
                "--target-review-count",
                "8",
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertNotIn(str(user_4.id), payload)
