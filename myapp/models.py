from atexit import register
from django.db import models
from datetime import datetime 
# Create your models here.
class User(models.Model):
    username = models.CharField(max_length=255,verbose_name="用户名")
    password = models.CharField(max_length=255,verbose_name="密码")
    email = models.CharField(unique=True,max_length=100)
    #手机号
    phone = models.CharField(unique=True,max_length=11)
    #个人简介
    info = models.TextField(max_length=255,null=True)
    #头像
    face = models.CharField(max_length=255,blank=True,null=True)
    #注册时间
    regtime = models.DateTimeField(default=datetime.now,db_index=True )



    class Meta:
        db_table = "user"
    

# 菜品
class Foods(models.Model):
    foodname = models.CharField(max_length=70)
    foodtype = models.CharField(max_length=20)
    recommand = models.CharField(max_length=255,null=True)
    imgurl = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=5,decimal_places=2)
