from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from .media import MEDIA_CHOICES


class Category(models.Model):
    name = models.CharField("分类名称", max_length=80)
    slug = models.SlugField("分类标识", max_length=80, unique=True)

    class Meta:
        verbose_name = "分类"
        verbose_name_plural = "分类"
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField("标签名称", max_length=50)
    slug = models.SlugField("标签标识", max_length=50, unique=True)

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ACTIVE = "active", "已上架"
        ARCHIVED = "archived", "已归档"

    name = models.CharField("商品名称", max_length=120)
    sku = models.CharField("SKU", max_length=40, unique=True)
    price = models.DecimalField("价格", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    stock = models.PositiveIntegerField("库存", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT)
    image_key = models.CharField("商品图片", max_length=1, choices=MEDIA_CHOICES, blank=True, default="", help_text="仅选择内置合成图片；不接受网址或上传。")
    featured = models.BooleanField("精选推荐", default=False, help_text="勾选后需保存才会生效。列表中的开关也使用 Django 原生批量保存。")
    category = models.ForeignKey(
        Category, verbose_name="分类", on_delete=models.PROTECT,
        related_name="products", blank=True, null=True,
    )
    tags = models.ManyToManyField(Tag, verbose_name="标签", related_name="products", blank=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "商品"
        verbose_name_plural = "商品"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField("规格", max_length=80)
    value = models.CharField("规格值", max_length=80)

    class Meta:
        verbose_name = "商品规格"
        verbose_name_plural = "商品规格"

    def __str__(self):
        return f"{self.name}: {self.value}"


class MemberProfile(models.Model):
    """Fictional adult profile records, unrelated to Django authentication."""
    name = models.CharField("姓名", max_length=80)
    member_code = models.CharField("会员编号", max_length=24, unique=True)
    avatar_key = models.CharField("头像", max_length=1, choices=MEDIA_CHOICES, blank=True, default="")
    tier = models.CharField("会员等级", max_length=16, choices=[("standard", "普通会员"), ("premium", "高级会员")], default="standard")
    active = models.BooleanField("启用", default=True)
    joined_at = models.DateField("加入日期")

    class Meta:
        verbose_name = "会员资料"
        verbose_name_plural = "会员资料"
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class NewsItem(models.Model):
    """Small image-list example, not a CMS or public publishing backend."""
    title = models.CharField("标题", max_length=160)
    cover_key = models.CharField("新闻封面", max_length=1, choices=MEDIA_CHOICES, blank=True, default="")
    section = models.CharField("栏目", max_length=16, choices=[("design", "设计"), ("community", "社区"), ("places", "城市与自然")], default="design")
    status = models.CharField("状态", max_length=16, choices=[("draft", "草稿"), ("published", "已发布")], default="draft")
    published_on = models.DateField("发布日期", blank=True, null=True)

    class Meta:
        verbose_name = "新闻"
        verbose_name_plural = "新闻"
        ordering = ["-published_on", "pk"]

    def __str__(self):
        return self.title
