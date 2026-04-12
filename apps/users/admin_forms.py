from __future__ import annotations

from django import forms
from django.contrib.auth.hashers import make_password

from apps.foods.models import Collect, Comment, Foods
from apps.recommendations.models import YelpBusiness, YelpReview
from apps.users.models import User


class FoodCrawlForm(forms.Form):
    source_url = forms.URLField(label="分类页 URL")
    page_count = forms.IntegerField(label="爬取页数", min_value=1, max_value=50, initial=3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)


class FoodImportForm(forms.Form):
    clear_existing = forms.BooleanField(
        label="导入前清空现有菜品表",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)


def _apply_bootstrap_classes(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = "form-check-input"
            continue
        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing} form-control".strip()


class UserAdminForm(forms.ModelForm):
    password = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="编辑时留空则保持原密码。",
        label="密码",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "email",
            "phone",
            "info",
            "face",
            "source",
            "external_user_id",
        ]
        labels = {
            "info": "个人简介",
            "face": "头像路径",
            "source": "来源",
            "external_user_id": "外部用户 ID",
        }
        widgets = {
            "info": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["password"].required = False
        else:
            self.fields["password"].required = True
            self.fields["password"].help_text = "新建用户时必填。"
        _apply_bootstrap_classes(self)

    def clean_password(self) -> str:
        password = self.cleaned_data.get("password", "")
        if not password and not self.instance.pk:
            raise forms.ValidationError("新建用户时必须填写密码。")
        return password

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        raw_password = self.cleaned_data.get("password", "")
        if raw_password:
            if raw_password.startswith("pbkdf2_") or raw_password.startswith("!"):
                user.password = raw_password
            else:
                user.password = make_password(raw_password)

        if commit:
            user.save()
        return user


class FoodsAdminForm(forms.ModelForm):
    class Meta:
        model = Foods
        fields = [
            "foodname",
            "foodtype",
            "recommend",
            "imgurl",
            "price",
            "collect_count",
            "comment_count",
        ]
        labels = {
            "foodname": "菜品名称",
            "foodtype": "菜品分类",
            "recommend": "推荐语",
            "imgurl": "图片路径",
            "price": "价格",
            "collect_count": "收藏数",
            "comment_count": "评论数",
        }
        widgets = {
            "recommend": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)


class CommentAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.order_by("id"),
        label="用户",
    )
    food = forms.ModelChoiceField(
        queryset=Foods.objects.order_by("id"),
        label="菜品",
    )

    class Meta:
        model = Comment
        fields = ["user", "food", "realname", "content", "ctime"]
        labels = {
            "realname": "展示昵称",
            "content": "评论内容",
            "ctime": "评论时间",
        }
        widgets = {
            "content": forms.Textarea(attrs={"rows": 4}),
            "ctime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["user"].initial = self.instance.uid
            self.fields["food"].initial = self.instance.fid
        _apply_bootstrap_classes(self)

    def save(self, commit: bool = True) -> Comment:
        comment = super().save(commit=False)
        comment.uid = self.cleaned_data["user"].id
        comment.fid = self.cleaned_data["food"].id
        if commit:
            comment.save()
        return comment


class CollectAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.order_by("id"),
        label="用户",
    )
    food = forms.ModelChoiceField(
        queryset=Foods.objects.order_by("id"),
        label="菜品",
    )

    class Meta:
        model = Collect
        fields = ["user", "food"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        user = cleaned_data.get("user")
        food = cleaned_data.get("food")
        if user and food:
            queryset = Collect.objects.filter(user=user, food=food)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError("该用户已收藏该菜品。")
        return cleaned_data


class YelpBusinessAdminForm(forms.ModelForm):
    class Meta:
        model = YelpBusiness
        fields = [
            "business_id",
            "name",
            "categories",
            "stars",
            "review_count",
            "city",
            "state",
            "latitude",
            "longitude",
            "is_open",
            "aggregated_review_count",
        ]
        labels = {
            "business_id": "业务 ID",
            "name": "名称",
            "categories": "分类",
            "stars": "评分",
            "review_count": "评论数",
            "city": "城市",
            "state": "州",
            "latitude": "纬度",
            "longitude": "经度",
            "is_open": "营业中",
            "aggregated_review_count": "聚合评论数",
        }
        widgets = {
            "categories": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)


class YelpReviewAdminForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.order_by("id"),
        label="用户",
    )
    business = forms.ModelChoiceField(
        queryset=YelpBusiness.objects.order_by("name"),
        label="商家",
    )

    class Meta:
        model = YelpReview
        fields = ["review_id", "business", "user", "stars", "text", "source", "review_date"]
        labels = {
            "review_id": "评论 ID",
            "stars": "评分",
            "text": "评论内容",
            "source": "来源",
            "review_date": "评论时间",
        }
        widgets = {
            "text": forms.Textarea(attrs={"rows": 4}),
            "review_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self)
