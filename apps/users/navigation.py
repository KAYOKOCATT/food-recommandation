from __future__ import annotations

from typing import Any

from .session_auth import (
    LOGIN_SOURCE_ADMIN_DEMO,
    LOGIN_SOURCE_LOCAL,
    LOGIN_SOURCE_YELP_DEMO,
    SessionIdentity,
)


def build_navigation(identity: SessionIdentity) -> list[dict[str, Any]]:
    if identity.is_admin:
        return [
            _section(
                "管理入口",
                [
                    _item("admin_home", "后台首页", "uim uim-airplay"),
                ],
            ),
        ]

    items = [
        _section(
            "首页",
            [
                _item("user_home", "首页", "uim uim-airplay"),
            ],
        ),
        _section(
            "推荐",
            [
                _item("statistics_recommendations", "热门推荐", "uim uim-star"),
                _item("food_list", "美食列表", "uim uim-schedule"),
                _item("recommendations:yelp_business_list", "Yelp 餐厅推荐", "uim uim-store"),
            ],
        ),
    ]

    if identity.is_local_user:
        items.insert(
            1,
            _section(
                "个人中心",
                [
                    _item("user_profile", "个人中心", "uim uim-user"),
                    _item("usercf_recommendations", "为您推荐", "uim uim-schedule"),
                    _item("change_password", "修改密码", "uim uim-lock"),
                    _item("recommendations:dashboard", "数据可视化", "uim uim-chart-pie"),
                ],
            ),
        )
    elif identity.is_yelp_demo_user:
        items.insert(
            1,
            _section(
                "演示入口",
                [
                    _item("recommendations:yelp_recommendations", "Yelp 为你推荐", "uim uim-thumbs-up"),
                    _item("recommendations:dashboard", "数据可视化", "uim uim-chart-pie"),
                ],
            ),
        )

    return items


def login_source_label(login_source: str | None) -> str:
    labels = {
        LOGIN_SOURCE_LOCAL: "本地用户",
        LOGIN_SOURCE_YELP_DEMO: "Yelp 演示",
        LOGIN_SOURCE_ADMIN_DEMO: "管理员演示",
    }
    return labels.get(login_source or "", "访客")


def _section(title: str, items: list[dict[str, str]]) -> dict[str, Any]:
    return {"title": title, "items": items}


def _item(url_name: str, label: str, icon: str) -> dict[str, str]:
    return {"url_name": url_name, "label": label, "icon": icon}
