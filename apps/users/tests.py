from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.yelp_service import YelpService
from apps.users.models import User


class AuthFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
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

    def test_yelp_demo_login_rejects_non_demo_user(self) -> None:
        response = self.client.post(
            "/api/v1/users/login/yelp-demo/",
            data=json.dumps({"user_id": self.local_user.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["msg"], "该 Yelp 演示账号不可用")

    def test_admin_demo_login_uses_first_user(self) -> None:
        response = self.client.post("/api/v1/users/login/admin-demo/", data="{}", content_type="application/json")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["redirect"], "/api/v1/admin/home/")

        session = self.client.session
        self.assertEqual(session["user_id"], self.local_user.id)
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

        with tempfile.TemporaryDirectory() as temp_dir:
            recommendation_path = Path(temp_dir) / "yelp_usercf.json"
            recommendation_path.write_text("{}", encoding="utf-8")
            with patch.object(YelpService, "USERCF_FILE", recommendation_path):
                response = self.client.get("/api/v1/yelp/recommendations/")

        self.assertEqual(response.status_code, 200)
        nav_menu = response.context["nav_menu"]
        all_labels = [item["label"] for section in nav_menu for item in section["items"]]
        self.assertIn("Yelp 为你推荐", all_labels)
        self.assertNotIn("个人中心", all_labels)
