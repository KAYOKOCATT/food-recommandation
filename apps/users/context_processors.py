
from typing import Any

from .navigation import build_navigation, login_source_label
from .session_auth import build_identity


def user_info(request) -> dict[str, Any]:
    """为模板提供当前用户和导航信息。"""
    identity = build_identity(request)
    current_user = identity.user

    return {
        "user_info": current_user,
        "current_user": current_user,
        "auth_role": identity.auth_role,
        "login_source": identity.login_source,
        "login_source_label": login_source_label(identity.login_source),
        "is_demo_login": identity.is_demo_login,
        "can_edit_profile": identity.is_local_user or identity.is_yelp_demo_user,
        "can_submit_interactions": identity.is_local_user or identity.is_yelp_demo_user,
        "can_view_yelp_recommendations": identity.is_authenticated and not identity.is_admin,
        "nav_menu": build_navigation(identity),
        "current_url_name": request.resolver_match.view_name if request.resolver_match else "",
    }
