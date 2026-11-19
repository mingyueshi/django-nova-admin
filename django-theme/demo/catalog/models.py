from decimal import Decimal
from uuid import uuid4
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, router, transaction
from .media import MEDIA_CHOICES


class Category(models.Model):
    name = models.CharField("分类名称", max_length=80)
    slug = models.SlugField("分类标识", max_length=80, unique=True)

    parent = models.ForeignKey(
        "self", verbose_name="父分类", related_name="children", on_delete=models.PROTECT,
        null=True, blank=True, editable=False,
    )
    # Tree moves exchange these slots. New categories use their own unique PK as a slot.
    position = models.PositiveBigIntegerField("同级顺序", null=True, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=~models.Q(parent=models.F("pk")), name="catalog_category_not_self")]
        verbose_name = "分类"
        verbose_name_plural = "分类"
        ordering = ["name", "pk"]

    def clean(self):
        super().clean()
        self.validate_parent(self._state.db or router.db_for_read(Category, instance=self))

    def validate_parent(self, db):
        if self.parent_id is None:
            return
        seen = {self.pk}
        parents = dict(Category.objects.using(db).order_by().values_list("pk", "parent_id"))
        ancestor = self.parent_id
        while ancestor is not None:
            if ancestor in seen:
                raise ValidationError("分类不能位于自身或其下级分类之下。")
            seen.add(ancestor)
            ancestor = parents.get(ancestor)

    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        if ((self._state.adding and self.parent_id is None and self.position is None)
                or (fields is not None and {"parent", "parent_id", "position"}.isdisjoint(fields))):
            return super().save(*args, **kwargs)
        db = kwargs.get("using") or router.db_for_write(Category, instance=self)
        with transaction.atomic(using=db):
            # Normal ORM saves of structural fields share the admin's tree lock.
            states = CategoryTreeState.objects.using(db)
            if not states.filter(pk=1).update(version=uuid4()):
                states.get_or_create(pk=1)
            self.validate_parent(db)
            return super().save(*args, **kwargs)

    @property
    def tree_position(self):
        return self.pk if self.position is None else self.position

    def __str__(self):
        return self.name


class CategoryTreeState(models.Model):
    # A shared revision serializes structural edits, including moves between branches.
    version = models.UUIDField(default=uuid4, editable=False)

    class Meta:
        default_permissions = ()


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
        permissions = [
            ("export_product", "可导出按日期筛选的商品 CSV"),
            ("approve_product", "可审批商品上架"),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ProductPublicationRequest(models.Model):
    class Result(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="publication_requests")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=8, choices=Result.choices, default=Result.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True)
    reviewed_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-pk"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["product"], condition=models.Q(result="pending"),
                                    name="catalog_one_pending_publication"),
            models.CheckConstraint(
                condition=(models.Q(result="pending", reviewed_by__isnull=True, reviewed_at__isnull=True)
                           | models.Q(result__in=["approved", "rejected"], reviewed_by__isnull=False, reviewed_at__isnull=False)),
                name="catalog_publication_review_complete",
            ),
        ]


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
