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
                    _item("admin_home", "后台首页", "uim uim-airplay"),  # 仪表盘标准图标
                    _item("admin_user_list", "用户与认证", "uim uim-lock-access"), # 模板中没有user，用lock-access代表权限与认证
                    _item("admin_food_list", "中文菜品", "uim uim-th-large"), # 用网格/列表形式代表菜品库
                    _item("admin_food_ingestion", "数据采集", "uim uim-process"), # 采集过程
                    _item("admin_yelp_business_list", "Yelp 数据", "uim uim-briefcase"), # 商业/商家数据
                    _item("recommendations:dashboard", "数据可视化", "uim uim-chart-pie"),
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
                _item("statistics_recommendations", "热门推荐", "uim uim-star"), # 热门、星标
                _item("food_list", "美食列表", "uim uim-list-ui-alt"), # 列表图标
                _item("recommendations:yelp_business_list", "Yelp 餐厅发现", "uim uim-scenery"), # 发现/风景/图像
                _item("recommendations:yelp_hot_recommendations", "Yelp 热门推荐", "uim uim-signal-alt-3"),
            ],
        ),
    ]

    if identity.is_local_user or identity.is_yelp_demo_user:
        items.insert(
            1,
            _section(
                "个人中心",
                [
                    _item("user_profile", "个人中心", "uim uim-document-layout-center"), # 类似个人信息卡片
                    _item("recommendations:yelp_recommendations", "Yelp 为你推荐", "uim uim-favorite"),
                    _item("recommendations:yelp_als_recommendations", "Yelp ALS 实验", "uim uim-graph-bar"),
                    _item("change_password", "修改密码", "uim uim-lock"), # 锁/密码
                ],
            ),
        )
    elif identity.is_yelp_demo_user:
        items.insert(
            1,
            _section(
                "演示入口",
                [
                    _item("recommendations:yelp_hot_recommendations", "Yelp 热门推荐", "uim uim-signal-alt-3"),
                    _item("recommendations:yelp_recommendations", "Yelp 为你推荐", "uim uim-favorite"), # 专属推荐
                    _item("recommendations:yelp_als_recommendations", "Yelp ALS 实验", "uim uim-graph-bar"),
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
