"""
用户和菜品数据模型模块

本模块定义了系统的核心数据模型：
- User: 用户模型，处理用户认证和个人信息
- Foods: 菜品模型，管理餐厅菜品信息

依赖：
    - django.db.models: Django ORM 基础模型
    - django.utils.timezone: 时区感知的时间处理
    - django.contrib.auth.hashers: 密码加密工具

示例：
    from apps.users.models import User, Foods
    
    # 创建新用户
    user = User.objects.create(
        username="john_doe",
        password="secure_pass",
        phone="13800138000",
        email="john@example.com"
    )
    
    # 查询菜品
    foods = Foods.objects.filter(foodtype="dessert")
"""
from typing import TYPE_CHECKING, Any
from django.db import models
from django.db.models import Manager
from django.utils.timezone import now
from django.contrib.auth.hashers import make_password


class User(models.Model):
    """
    用户模型类
    
    管理用户的基本信息、认证凭证和个人资料。
    密码在保存时会自动使用 PBKDF2 算法加密。
    
    属性：
        id (AutoField): 用户唯一标识（自动创建）
        username (CharField): 用户名，最大长度255，唯一
        password (CharField): 密码，最大长度255，存储加密后的值
        email (CharField): 电子邮箱，唯一，最大长度100
        phone (CharField): 手机号码，唯一，11位数字
        info (TextField): 个人简介，最大长度255，可为空
        face (CharField): 头像URL，最大长度255，可为空
        regtime (DateTimeField): 注册时间，自动索引
    
    示例：
        # 创建用户（密码自动加密）
        user = User.objects.create(
            username="alice",
            password="my_password",
            phone="13912345678",
            email="alice@example.com"
        )
        
        # 验证密码
        from django.contrib.auth.hashers import check_password
        if check_password("my_password", user.password):
            print("密码正确")
        
        # 更新用户信息
        user.info = "热爱美食的程序员"
        user.save()
    """

    # 显式声明 objects 管理器
    if TYPE_CHECKING:
        objects: Manager['User']
        id: models.AutoField


    username = models.CharField(max_length=255, verbose_name="用户名", unique=True)
    password = models.CharField(max_length=255, verbose_name="密码")
    email = models.CharField(unique=True, max_length=100)
    phone = models.CharField(unique=True, max_length=11)
    info = models.TextField(max_length=255, null=True, blank=True)
    face = models.CharField(max_length=255, blank=True, null=True)
    regtime = models.DateTimeField(default=now, db_index=True)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        保存用户对象，自动加密密码
        
        重写 save 方法以在创建新用户时自动加密密码。
        只有新建用户（无主键）且密码未加密时才会执行加密。
        
        参数：
            *args: 可变位置参数，传递给父类 save 方法
            **kwargs: 可变关键字参数，传递给父类 save 方法
        
        返回：
            None
        
        示例：
            # 创建新用户 - 密码自动加密
            user = User(username="test", password="123456")
            user.save()  # 密码会被加密
            
            # 更新用户 - 不会重新加密已加密的密码
            user.info = "更新信息"
            user.save()  # 保持原有加密密码
        """

        # 自动加密密码
        if not self.pk and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username

    class Meta:
        db_table = "user"


class Foods(models.Model):
    """
    菜品模型类
    
    管理餐厅的菜品信息，包括名称、类型、价格等。
    
    属性：
        id (AutoField): 菜品唯一标识（自动创建）
        foodname (CharField): 菜品名称，最大长度70
        foodtype (CharField): 菜品类型，最大长度20（如：川菜、粤菜、甜品等）
        recommand (CharField): 推荐语，最大长度255，可为空
        imgurl (CharField): 菜品图片URL，最大长度255
        price (DecimalField): 菜品价格，5位数字，2位小数
    
    示例：
        # 创建新菜品
        food = Foods.objects.create(
            foodname="宫保鸡丁",
            foodtype="川菜",
            price=38.50,
            imgurl="/media/foods/gongbaojiding.jpg",
            recommand="经典川菜，麻辣鲜香"
        )
        
        # 查询特价菜品
        cheap_foods = Foods.objects.filter(price__lt=50)
        
        # 按类型统计数量
        from django.db.models import Count
        type_stats = Foods.objects.values('foodtype').annotate(
            count=Count('id')
        )
    """

    if TYPE_CHECKING:
        objects: Manager['Foods']
        id: models.AutoField

    foodname = models.CharField(max_length=70)
    foodtype = models.CharField(max_length=20)
    recommand = models.CharField(max_length=255, null=True, blank=True)
    imgurl = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self) -> str:
        return self.foodname

    class Meta:
        db_table = "foods"