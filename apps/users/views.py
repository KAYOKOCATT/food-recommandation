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
from django.shortcuts import render
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.contrib.auth.hashers import check_password
from typing import Union, Optional

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
        username: Optional[str] = request.POST.get('username')
        password: Optional[str] = request.POST.get('password')
    
        if not username or not password:
            return JsonResponse({'error': '用户名和密码不能为空'}, status=400)
    
        user: Optional[User] = User.objects.filter(username=username).first()
        
        if user and check_password(password, user.password):
            request.session['user_id'] = user.id
            return JsonResponse({'user_id': user.id, 'username': user.username})
        else:
            return JsonResponse({'error': '用户名或密码错误'}, status=401)
    
    return render(request, 'auth-login.html')

def register(request: HttpRequest) -> Union[JsonResponse, HttpResponse]:
    """
    用户注册视图
    
    处理用户注册请求，支持 GET 和 POST 方法：
    - GET: 显示注册页面
    - POST: 处理注册表单提交，创建新用户
    
    参数：
        request (HttpRequest): Django HTTP 请求对象
            - POST.username: 用户名（必填，唯一）
            - POST.password: 密码（必填）
            - POST.phone: 手机号（必填，唯一，11位）
            - POST.email: 电子邮箱（必填，唯一）
    
    返回：
        Union[JsonResponse, HttpResponse]:
            - GET 请求: 返回注册页面 (HTML)
            - POST 成功: 返回成功信息和 user_id 的 JSON
            - POST 失败: 返回错误信息的 JSON
    
    安全性：
        - 密码在保存时自动加密（参见 User.save() 方法）
        - 所有唯一字段都会检查重复
    
    示例：
        # 成功的注册请求
        POST /register/
        {
            "username": "alice123",
            "password": "secure_pass",
            "phone": "13812345678",
            "email": "alice@example.com"
        }
        
        响应：
        {
            "success": "注册成功",
            "user_id": 2
        }
        
        # 失败的注册请求（手机号已存在）
        POST /register/
        {
            "username": "bob456",
            "password": "pass123",
            "phone": "13812345678",  # 已存在的手机号
            "email": "bob@example.com"
        }
        
        响应 (HTTP 400):
        {
            "error": "该手机号已被注册"
        }
    
    状态码：
        - 200: 成功或显示页面
        - 400: 参数验证失败或唯一性冲突
    
    注意事项：
        - 所有字段都会进行存在性检查
        - 用户名、手机号、邮箱必须唯一
        - 密码建议前端先进行强度验证
    """

    if request.method == 'POST':
        username: str | None = request.POST.get('username')
        password: str | None = request.POST.get('password')
        phone: str | None = request.POST.get('phone')
        email: str | None = request.POST.get('email')
        
        # 验证必填字段
        if not username or not password or not phone or not email:
            return JsonResponse({'error': '所有字段都不能为空'}, status=400)
        
        # 这里 username, password 等已经确认不是 None，可以直接使用
        # 检查唯一性
        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': '用户名已存在'}, status=400)
        
        if User.objects.filter(phone=phone).exists():
            return JsonResponse({'error': '该手机号已被注册'}, status=400)
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': '该邮箱已被注册'}, status=400)
        
        # 创建用户（密码会自动加密）
        user: User = User.objects.create(
            username=username,
            password=password,
            phone=phone,
            email=email
        )
        
        return JsonResponse({
            'success': '注册成功', 
            'user_id': user.id
        })
        
    return render(request, 'auth-register.html')
