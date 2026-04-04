from django.shortcuts import render
from .models import *
from django.http import JsonResponse
# Create your views here.
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
    
        if username == '' or password == '':
            return JsonResponse({'error':'用户名和密码不能为空'})
    
        user = User.objects.filter(username=username).first()
        
        if user is not None and user.password == password:
            request.session['user_id'] = user.id
            return JsonResponse({'user_id':user.id})
        else:
            return JsonResponse({'error':'用户名或密码错误'})
    return render(request,'auth-login.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        
        if User.objects.filter(phone=phone).exists():
            return JsonResponse({'error':'该手机号已被注册'})
        
        User.objects.create(username=username,password=password,phone=phone,email=email)
        return JsonResponse({'success':'注册成功'})
        
    return render(request,'auth-register.html')