from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect

from apps.users.models import User

AUTH_ROLE_USER = "user"
AUTH_ROLE_ADMIN = "admin"

LOGIN_SOURCE_LOCAL = "local"
LOGIN_SOURCE_YELP_DEMO = "yelp_demo"
LOGIN_SOURCE_ADMIN_DEMO = "admin_demo"


@dataclass(frozen=True)
class SessionIdentity:
    user: User | None
    auth_role: str | None
    login_source: str | None
    is_demo_login: bool

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None

    @property
    def is_local_user(self) -> bool:
        return self.auth_role == AUTH_ROLE_USER and self.login_source == LOGIN_SOURCE_LOCAL

    @property
    def is_yelp_demo_user(self) -> bool:
        return self.auth_role == AUTH_ROLE_USER and self.login_source == LOGIN_SOURCE_YELP_DEMO

    @property
    def is_admin(self) -> bool:
        return self.auth_role == AUTH_ROLE_ADMIN


def build_identity(request: HttpRequest) -> SessionIdentity:
    user_id = request.session.get("user_id")
    user = User.objects.filter(id=user_id).first() if user_id else None
    auth_role = request.session.get("auth_role")
    login_source = request.session.get("login_source")
    is_demo_login = bool(request.session.get("is_demo_login", False))

    if user is None:
        return SessionIdentity(
            user=None,
            auth_role=None,
            login_source=None,
            is_demo_login=False,
        )

    if not auth_role:
        auth_role = AUTH_ROLE_USER
    if not login_source:
        login_source = LOGIN_SOURCE_LOCAL
    if login_source in {LOGIN_SOURCE_YELP_DEMO, LOGIN_SOURCE_ADMIN_DEMO}:
        is_demo_login = True

    return SessionIdentity(
        user=user,
        auth_role=auth_role,
        login_source=login_source,
        is_demo_login=is_demo_login,
    )


def login_local_user(request: HttpRequest, user: User) -> None:
    _set_session(
        request,
        user=user,
        auth_role=AUTH_ROLE_USER,
        login_source=LOGIN_SOURCE_LOCAL,
        is_demo_login=False,
    )


def login_yelp_demo_user(request: HttpRequest, user: User) -> None:
    _set_session(
        request,
        user=user,
        auth_role=AUTH_ROLE_USER,
        login_source=LOGIN_SOURCE_YELP_DEMO,
        is_demo_login=True,
    )


def login_admin_user(request: HttpRequest, user: User) -> None:
    _set_session(
        request,
        user=user,
        auth_role=AUTH_ROLE_ADMIN,
        login_source=LOGIN_SOURCE_ADMIN_DEMO,
        is_demo_login=True,
    )


def _set_session(
    request: HttpRequest,
    *,
    user: User,
    auth_role: str,
    login_source: str,
    is_demo_login: bool,
) -> None:
    request.session.flush()
    request.session["user_id"] = user.id
    request.session["auth_role"] = auth_role
    request.session["login_source"] = login_source
    request.session["is_demo_login"] = is_demo_login


def require_identity(
    request: HttpRequest,
    *,
    allow_local_user: bool = False,
    allow_yelp_demo_user: bool = False,
    allow_admin: bool = False,
    api: bool = False,
) -> SessionIdentity | HttpResponse:
    identity = build_identity(request)
    if not identity.is_authenticated:
        return _auth_error("请先登录", status=401, api=api)

    allowed = (
        (allow_local_user and identity.is_local_user)
        or (allow_yelp_demo_user and identity.is_yelp_demo_user)
        or (allow_admin and identity.is_admin)
    )
    if allowed:
        return identity

    return _auth_error("当前身份无权访问该功能", status=403, api=api)


def _auth_error(message: str, *, status: int, api: bool) -> HttpResponse:
    if api:
        return JsonResponse({"code": status, "msg": message, "data": {}}, status=status)
    if status == 401:
        response: HttpResponse | HttpResponseRedirect = redirect("login")
        response.status_code = 302
        return response
    return HttpResponse(message, status=status)
