"""
用户视图模块

处理用户认证相关的HTTP请求，包括登录和注册功能。

功能：
    - 用户登录：验证用户名和密码，建立会话
    - 用户注册：创建新用户账号，自动加密密码

依赖：
    - django.shortcuts.render: 渲染HTML模板
    - django.http: HTTP响应类
    - django.contrib.auth.hashers: 密码验证工具

路由配置示例：
    # urls.py
    from django.urls import path
    from apps.users.views import login, register
    
    urlpatterns = [
        path('login/', login, name='login'),
        path('register/', register, name='register'),
    ]
"""
import json
import re
import os
from json import JSONDecodeError
from typing import Optional, Union

from django import forms
from django.contrib.auth.hashers import check_password
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.hashers import check_password, make_password
from config import settings

from apps.users.models import User


def login(request: HttpRequest) -> Union[JsonResponse, HttpResponse]:
    """
    用户登录视图

    处理用户登录请求，支持 GET 和 POST 方法：
    - GET: 显示登录页面
    - POST: 处理登录表单提交

    参数：
        request (HttpRequest): Django HTTP 请求对象
            - POST.username: 用户名
            - POST.password: 密码

    返回：
        Union[JsonResponse, HttpResponse]:
            - GET 请求: 返回登录页面 (HTML)
            - POST 成功: 返回包含 user_id 和 username 的 JSON
            - POST 失败: 返回错误信息的 JSON

    会话数据：
        - session['user_id']: 登录成功后保存用户ID

    示例：
        # 成功的登录请求
        POST /login/
        {
            "username": "john_doe",
            "password": "secret123"
        }

        响应：
        {
            "user_id": 1,
            "username": "john_doe"
        }

        # 失败的登录请求
        POST /login/
        {
            "username": "wrong_user",
            "password": "wrong_pass"
        }

        响应 (HTTP 401):
        {
            "error": "用户名或密码错误"
        }

    状态码：
        - 200: 成功或显示页面
        - 400: 参数验证失败
        - 401: 认证失败
    """

    if request.method == 'POST':
        try:
            data: dict[str, str] = json.loads(request.body)
        except JSONDecodeError:
            return api_response(code=4001, msg='请求体不是合法 JSON', data={}, status=400)

        username: Optional[str] = data.get('username')
        password: Optional[str] = data.get('password')
        if not username or not password:
            return api_response(code=4002, msg='用户名和密码不能为空', data={}, status=400)

        user: Optional[User] = User.objects.filter(username=username).first()

        if user and check_password(password, user.password):
            request.session['user_id'] = user.id
            return api_response(
                code=200,
                msg='登录成功',
                data={
                    'user_id': user.id,
                    'username': user.username,
                    'redirect': '/api/v1/user_index/',
                },
            )
        return api_response(code=4003, msg='用户名或密码错误', data={}, status=401)
    return render(request, 'auth/login-refactored.html')


# ---------- 辅助函数：构建统一响应 ----------
def api_response(code: int, msg: str, data=None, status: int = 200) -> JsonResponse:
    return JsonResponse({
        'code': code,
        'msg': msg,
        'data': data
    }, status=status)

# ---------- 表单验证器 ----------


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150, error_messages={'required': '用户名不能为空'})
    password = forms.CharField(min_length=6, widget=forms.PasswordInput, error_messages={
        'required': '密码不能为空',
        'min_length': '密码长度至少6位'
    })
    phone = forms.CharField(max_length=11, error_messages={
                            'required': '手机号不能为空'})
    email = forms.EmailField(
        error_messages={'required': '邮箱不能为空', 'invalid': '邮箱格式不正确'})

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('用户名已存在')
        return username

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not re.match(r'^1[3-9]\d{9}$', phone):
            raise forms.ValidationError('手机号格式不正确')
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('该手机号已被注册')
        return phone

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('该邮箱已被注册')
        return email

# ---------- 视图 ----------


def register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except JSONDecodeError:
            return api_response(code=4001, msg='请求体不是合法 JSON', data={}, status=400)

        form = RegisterForm(data)
        if not form.is_valid():
            first_error = next(iter(form.errors.values()))[0]
            return api_response(
                code=4002,
                msg=first_error,
                data=form.errors.get_json_data(),
                status=400,
            )

        # 3. 创建用户（密码自动哈希）
        user: User = User.objects.create(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
            email=form.cleaned_data['email'],
            phone=form.cleaned_data['phone'],
        )

        # 4. 成功响应
        return api_response(
            code=200,
            msg='注册成功',
            data={'user_id': user.id}
        )

    # GET 请求返回注册页面（保持原有逻辑）
    return render(request, 'auth/register-refactored.html')

def user_index(request):
    return render(request, 'auth/user_index.html')

def logout(request):
    request.session.flush()
    return redirect('login')

def user_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return HttpResponse('请先登录',status=401)
    
    user = get_object_or_404(User,id=user_id)
    
    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.phone = request.POST.get('phone')
        user.info = request.POST.get('info')
        
        avatar = request.FILES.get('avatar')
        if avatar:
            static_path = os.path.join(settings.BASE_DIR, 'static', 'image')
            os.makedirs(static_path,exist_ok=True)
            filename =os.path.join(static_path,avatar.name)
            
            with open(filename, 'wb+') as destination:
                for chunk in avatar.chunks():
                    destination.write(chunk)
            
            user.face ='/image/' + avatar.name
        user.save()
        return redirect('user_view')
    
    else:
        from_page =request.GET.get('fp',1)
        return render(request, 'auth/user_view.html',{'user':user,'from_page':from_page})

def change_password(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return HttpResponse('请先登录',status=401)
    
    user = get_object_or_404(User,id=user_id)
    error_message = None
    success_message = None
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not check_password(current_password, user.password):
            error_message = '当前密码错误'
        elif new_password != confirm_password:
            error_message = '新密码与确认密码不一致'
        else:
            user.password = make_password(new_password)
            user.save()
            success_message = '密码修改成功'
            return render(request,"auth/change_password.html",{'user':user,'success_message':success_message})
    return render(request,"auth/change_password.html",{'user':user,'error_message':error_message})