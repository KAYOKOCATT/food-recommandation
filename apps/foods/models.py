from enum import auto
from time import ctime
from typing import TYPE_CHECKING
from django.db import models
from django.db.models import Manager

class Foods(models.Model):
    """
    菜品模型类
    
    管理餐厅的菜品信息，包括名称、类型、价格等。
    
    属性：
        id (AutoField): 菜品唯一标识（自动创建）
        foodname (CharField): 菜品名称，最大长度70
        foodtype (CharField): 菜品类型，最大长度20（如：川菜、粤菜、甜品等）
        recommend (CharField): 推荐语，最大长度255，可为空
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
    recommend = models.CharField(max_length=255, null=True, blank=True)
    imgurl = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self) -> str:
        return self.foodname

    class Meta:
        db_table = "myapp_foods"

# 评论模型类
class Comment(models.Model):
    uid = models.IntegerField()
    fid = models.IntegerField()
    realname = models.CharField(max_length=11)
    content = models.TextField()
    ctime = models.DateTimeField(null=True)
    
# 收藏模型类
class Collect(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE) #用户外键
    food = models.ForeignKey("foods.Foods", on_delete=models.CASCADE) #菜品外键
    added_time = models.DateTimeField(auto_now_add=True) #收藏时间
    
    class Meta:
        unique_together = ("user", "food")
        
    def __str__(self):
        return f"{self.user.username} 收藏了 {self.food.foodname}"
