from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.foods.models import Collect, Comment, Foods
from apps.foods.ingestion import CrawlResult, ImportResult
from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.home_wordcloud_service import HomeWordCloudService
from apps.users.demo_candidates import YelpDemoCandidate
from apps.users.models import User


class AuthFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.admin_user = User.objects.create(
            username="admin-user",
            password="secret123",
            email="admin@example.com",
            phone="13800138010",
        )
        self.local_user = User.objects.create(
            username="local-user",
            password="secret123",
            email="local@example.com",
            phone="13800138011",
        )
        self.yelp_user = User.objects.create(
            username="yelp-user",
            password="!",
            email="yelp@example.com",
            phone="13800138012",
            source="yelp",
            external_user_id="yelp-1",
        )
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
        YelpReview.objects.create(
            review_id="r1",
            business=self.business,
            user=self.yelp_user,
            stars=5.0,
            source="yelp",
        )

    def test_local_login_sets_session_metadata(self) -> None:
        response = self.client.post(
            "/api/v1/users/login/",
            data=json.dumps({"username": "local-user", "password": "secret123"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["redirect"], "/api/v1/users/home/")

        session = self.client.session
        self.assertEqual(session["user_id"], self.local_user.id)
        self.assertEqual(session["auth_role"], "user")
        self.assertEqual(session["login_source"], "local")
        self.assertFalse(session["is_demo_login"])

    def test_yelp_demo_login_sets_demo_session(self) -> None:
        with patch("apps.users.views.candidate_user_ids", return_value={self.yelp_user.id}):
            response = self.client.post(
                "/api/v1/users/login/yelp-demo/",
                data=json.dumps({"user_id": self.yelp_user.id}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["redirect"], "/api/v1/yelp/recommendations/")

        session = self.client.session
        self.assertEqual(session["user_id"], self.yelp_user.id)
        self.assertEqual(session["auth_role"], "user")
        self.assertEqual(session["login_source"], "yelp_demo")
        self.assertTrue(session["is_demo_login"])

    def test_unified_login_can_route_to_yelp_demo_session(self) -> None:
        with patch("apps.users.views.candidate_user_ids", return_value={self.yelp_user.id}):
            response = self.client.post(
                "/api/v1/users/login/",
                data=json.dumps(
                    {
                        "login_mode": "yelp_demo",
                        "selectedYelpUser": self.yelp_user.id,
                        "username": self.yelp_user.username,
                        "password": "",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["redirect"], "/api/v1/yelp/recommendations/")

        session = self.client.session
        self.assertEqual(session["user_id"], self.yelp_user.id)
        self.assertEqual(session["auth_role"], "user")
        self.assertEqual(session["login_source"], "yelp_demo")
        self.assertTrue(session["is_demo_login"])

    def test_yelp_demo_login_rejects_non_demo_user(self) -> None:
        with patch("apps.users.views.candidate_user_ids", return_value={self.yelp_user.id}):
            response = self.client.post(
                "/api/v1/users/login/yelp-demo/",
                data=json.dumps({"user_id": self.local_user.id}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["msg"], "该 Yelp 演示账号不可用")

    def test_login_get_uses_demo_candidate_cache_without_count_aggregation(self) -> None:
        with patch(
            "apps.users.views.load_yelp_demo_candidates",
            return_value=[
                YelpDemoCandidate(
                    user_id=self.yelp_user.id,
                    username=self.yelp_user.username,
                    display_name=self.yelp_user.username,
                    review_count=1,
                    last_review_at=None,
                )
            ],
        ):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.yelp_user.username)
        self.assertFalse(any("COUNT(" in query["sql"] for query in queries.captured_queries))

    def test_first_user_login_gets_admin_session(self) -> None:
        response = self.client.post(
            "/api/v1/users/login/",
            data=json.dumps({"username": "admin-user", "password": "secret123"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["redirect"], "/api/v1/admin/home/")

        session = self.client.session
        self.assertEqual(session["user_id"], self.admin_user.id)
        self.assertEqual(session["auth_role"], "admin")
        self.assertEqual(session["login_source"], "admin_demo")
        self.assertTrue(session["is_demo_login"])

    def test_yelp_demo_user_cannot_access_profile(self) -> None:
        session = self.client.session
        session["user_id"] = self.yelp_user.id
        session["auth_role"] = "user"
        session["login_source"] = "yelp_demo"
        session["is_demo_login"] = True
        session.save()

        response = self.client.get("/api/v1/users/profile/")

        self.assertEqual(response.status_code, 403)

    def test_admin_user_cannot_access_user_home(self) -> None:
        session = self.client.session
        session["user_id"] = self.local_user.id
        session["auth_role"] = "admin"
        session["login_source"] = "admin_demo"
        session["is_demo_login"] = True
        session.save()

        response = self.client.get("/api/v1/users/home/")

        self.assertEqual(response.status_code, 403)

    def test_yelp_demo_navigation_is_injected(self) -> None:
        session = self.client.session
        session["user_id"] = self.yelp_user.id
        session["auth_role"] = "user"
        session["login_source"] = "yelp_demo"
        session["is_demo_login"] = True
        session.save()

        response = self.client.get("/api/v1/yelp/recommendations/")

        self.assertEqual(response.status_code, 200)
        nav_menu = response.context["nav_menu"]
        all_labels = [item["label"] for section in nav_menu for item in section["items"]]
        self.assertIn("Yelp 为你推荐", all_labels)
        self.assertNotIn("个人中心", all_labels)

    def test_user_home_renders_wordcloud_cards(self) -> None:
        session = self.client.session
        session["user_id"] = self.local_user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            food_path = data_dir / "home_food_recommend_wordcloud.png"
            yelp_path = data_dir / "home_yelp_review_wordcloud.png"
            food_path.write_bytes(b"food-png")
            yelp_path.write_bytes(b"yelp-png")
            with patch.object(HomeWordCloudService, "FOOD_WORDCLOUD_FILE", food_path), patch.object(
                HomeWordCloudService,
                "YELP_WORDCLOUD_FILE",
                yelp_path,
            ):
                response = self.client.get("/api/v1/users/home/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "中文菜品推荐语词云")
        self.assertContains(response, "Yelp 餐厅评论词云")
        self.assertContains(response, "/api/v1/users/home/wordclouds/food/")
        self.assertContains(response, "/api/v1/users/home/wordclouds/yelp/")


class AdminCrudTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.admin_user = User.objects.create(
            username="admin-user",
            password="secret123",
            email="admin@example.com",
            phone="13800138111",
        )
        self.local_user = User.objects.create(
            username="normal-user",
            password="secret123",
            email="normal@example.com",
            phone="13800138112",
        )
        self.food = Foods.objects.create(
            foodname="宫保鸡丁",
            foodtype="川菜",
            recommend="经典川菜",
            imgurl="/static/image/test.jpg",
            price="38.50",
        )
        self.business = YelpBusiness.objects.create(
            business_id="admin-b1",
            name="Admin Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.5,
            review_count=10,
            city="Seattle",
            state="WA",
            is_open=True,
        )

    def _login_admin(self) -> None:
        session = self.client.session
        session["user_id"] = self.admin_user.id
        session["auth_role"] = "admin"
        session["login_source"] = "admin_demo"
        session["is_demo_login"] = True
        session.save()

    def test_admin_dashboard_renders_links(self) -> None:
        self._login_admin()

        response = self.client.get("/api/v1/admin/home/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "管理员后台")
        self.assertContains(response, "用户")
        self.assertContains(response, "菜品")

    def test_local_user_cannot_access_admin_list(self) -> None:
        session = self.client.session
        session["user_id"] = self.local_user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

        response = self.client.get("/api/v1/admin/users/")

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_user_with_hashed_password(self) -> None:
        self._login_admin()

        response = self.client.post(
            "/api/v1/admin/users/create/",
            {
                "username": "created-user",
                "password": "plain-secret",
                "email": "created@example.com",
                "phone": "13800138113",
                "info": "note",
                "face": "",
                "source": "local",
                "external_user_id": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created = User.objects.get(username="created-user")
        self.assertTrue(check_password("plain-secret", created.password))
        self.assertContains(response, "用户已保存")

    def test_admin_collect_create_syncs_food_collect_count(self) -> None:
        self._login_admin()

        response = self.client.post(
            "/api/v1/admin/collects/create/",
            {"user": self.local_user.id, "food": self.food.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.food.refresh_from_db()
        self.assertEqual(Collect.objects.count(), 1)
        self.assertEqual(self.food.collect_count, 1)

    def test_admin_comment_delete_syncs_food_comment_count(self) -> None:
        self._login_admin()
        comment = Comment.objects.create(
            uid=self.local_user.id,
            fid=self.food.id,
            realname=self.local_user.username,
            content="好吃",
        )
        self.food.comment_count = 1
        self.food.save(update_fields=["comment_count"])

        response = self.client.post(
            f"/api/v1/admin/comments/{comment.id}/delete/",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.food.refresh_from_db()
        self.assertEqual(Comment.objects.count(), 0)
        self.assertEqual(self.food.comment_count, 0)

    def test_admin_can_create_yelp_review(self) -> None:
        self._login_admin()

        response = self.client.post(
            "/api/v1/admin/yelp-reviews/create/",
            {
                "review_id": "admin-review-1",
                "business": self.business.id,
                "user": self.local_user.id,
                "stars": "4.0",
                "text": "后台录入评论",
                "source": "admin",
                "review_date": "2026-04-13T10:30",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        review = YelpReview.objects.get(review_id="admin-review-1")
        self.assertEqual(review.user_id, self.local_user.id)
        self.assertEqual(review.business_id, self.business.id)

    def test_admin_food_ingestion_page_renders(self) -> None:
        self._login_admin()

        response = self.client.get("/api/v1/admin/foods/ingestion/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "中文菜品数据采集")

    def test_admin_food_ingestion_crawl_uses_service(self) -> None:
        self._login_admin()
        with patch(
            "apps.users.admin_views.crawl_to_csv",
            return_value=CrawlResult(csv_path=Path("food.csv"), page_count=2, row_count=6),
        ) as mocked_crawl:
            response = self.client.post(
                "/api/v1/admin/foods/ingestion/",
                {
                    "action": "crawl",
                    "source_url": "https://example.com/cuisine/",
                    "page_count": "2",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mocked_crawl.assert_called_once_with("https://example.com/cuisine/", 2)
        self.assertContains(response, "抓取完成")

    def test_admin_food_ingestion_import_uses_service(self) -> None:
        self._login_admin()
        with patch(
            "apps.users.admin_views.import_csv_to_foods",
            return_value=ImportResult(csv_path=Path("food.csv"), created_count=8, cleared_count=3),
        ) as mocked_import:
            response = self.client.post(
                "/api/v1/admin/foods/ingestion/",
                {
                    "action": "import",
                    "clear_existing": "on",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mocked_import.assert_called_once_with(clear_existing=True)
        self.assertContains(response, "新增 8 条菜品")


class HomeWordCloudEndpointTests(TransactionTestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.local_user = User.objects.create(
            username="endpoint-user",
            password="secret123",
            email="endpoint@example.com",
            phone="13800138996",
        )

    def _login_local(self) -> None:
        session = self.client.session
        session["user_id"] = self.local_user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

    def test_home_wordcloud_image_returns_png_response(self) -> None:
        self._login_local()

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "home_food_recommend_wordcloud.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            with patch.object(HomeWordCloudService, "FOOD_WORDCLOUD_FILE", image_path):
                response = self.client.get("/api/v1/users/home/wordclouds/food/")
                payload = b"".join(response.streaming_content)
                response.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(payload.startswith(b"\x89PNG"))

    def test_home_wordcloud_image_returns_404_when_missing(self) -> None:
        self._login_local()

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "missing.png"
            with patch.object(HomeWordCloudService, "YELP_WORDCLOUD_FILE", image_path):
                response = self.client.get("/api/v1/users/home/wordclouds/yelp/")

        self.assertEqual(response.status_code, 404)
