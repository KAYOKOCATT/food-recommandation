from django.test import Client, TestCase

from apps.foods.models import Foods
from apps.users.models import User


class FoodListViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create(
            username="food-list-user",
            password="secret123",
            email="food-list@example.com",
            phone="13800138188",
        )
        self._login_local()

        Foods.objects.create(
            foodname="麻婆豆腐",
            foodtype="川菜",
            recommend="麻辣鲜香",
            imgurl="/static/image/a.jpg",
            price="22.00",
        )
        Foods.objects.create(
            foodname="宫保鸡丁",
            foodtype="川菜",
            recommend="经典下饭",
            imgurl="/static/image/b.jpg",
            price="32.00",
        )
        Foods.objects.create(
            foodname="蓝莓蛋糕",
            foodtype="甜品",
            recommend="甜而不腻",
            imgurl="/static/image/c.jpg",
            price="16.00",
        )

    def _login_local(self) -> None:
        session = self.client.session
        session["user_id"] = self.user.id
        session["auth_role"] = "user"
        session["login_source"] = "local"
        session["is_demo_login"] = False
        session.save()

    def test_food_list_renders_search_form(self) -> None:
        response = self.client.get("/api/v1/foods/list/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "搜索菜品")
        self.assertContains(response, 'name="q"', html=False)

    def test_food_list_search_filters_by_food_name(self) -> None:
        response = self.client.get("/api/v1/foods/list/?q=麻婆")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "麻婆豆腐")
        self.assertNotContains(response, "宫保鸡丁")
        self.assertNotContains(response, "蓝莓蛋糕")

    def test_food_list_search_can_stack_with_category(self) -> None:
        response = self.client.get("/api/v1/foods/list/?category=川菜&q=宫保")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "宫保鸡丁")
        self.assertNotContains(response, "麻婆豆腐")
        self.assertNotContains(response, "蓝莓蛋糕")

    def test_food_list_shows_empty_state_when_search_has_no_result(self) -> None:
        response = self.client.get("/api/v1/foods/list/?q=不存在的菜")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "没有找到符合条件的菜品")

    def test_food_list_pagination_and_category_links_keep_search_query(self) -> None:
        for index in range(20):
            Foods.objects.create(
                foodname=f"测试炒饭{index}",
                foodtype="主食",
                recommend="",
                imgurl=f"/static/image/test-{index}.jpg",
                price="12.00",
            )

        response = self.client.get("/api/v1/foods/list/?category=主食&q=炒饭")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "?category=%E4%B8%BB%E9%A3%9F&q=%E7%82%92%E9%A5%AD&page=2")
