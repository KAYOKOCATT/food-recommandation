"""
URL configuration for Food project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from apps.users import views as user_views
from apps.foods import views as food_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/v1/users/",include('apps.users.urls')),
    path('api/v1/foods/',include('apps.foods.urls')),
    path('api/v1/', include('apps.recommendations.urls')),

    path('api/v1/user_index/',user_views.user_index,name='user_index'),
    path('api/v1/food_list/',food_views.food_list,name='food_list'),
    path('api/v1/logout/',user_views.logout,name='logout'),

    path('',user_views.login,name='login'),# 后期接登录要换

]
