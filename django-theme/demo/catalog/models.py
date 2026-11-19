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


class ProductQuerySet(models.QuerySet):
    def delete(self):
        self._not_support_combined_queries("delete")
        if self.query.is_sliced or self.query.distinct_fields or self._fields is not None:
            raise TypeError("Delete requires an unsliced queryset of product instances.")
        db = self._db or router.db_for_write(self.model, **self._hints)
        entries = ProductRecycleEntry.objects.using(db)
        count = 0
        with transaction.atomic(using=db):
            ids = self.using(db).filter(recycle_entry__isnull=True).order_by("pk").values_list("pk", flat=True).distinct()
            for pk in ids:
                _, created = entries.get_or_create(product_id=pk)
                count += created
        self._result_cache = None
        return count, {self.model._meta.label: count} if count else {}

    delete.alters_data = True
    delete.queryset_only = True


class LiveProductManager(models.Manager.from_queryset(ProductQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(recycle_entry__isnull=True)


class Product(models.Model):
    objects = LiveProductManager()
    all_objects = ProductQuerySet.as_manager()

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ACTIVE = "active", "已上架"
        ARCHIVED = "archived", "已归档"

    name = models.CharField("商品名称", max_length=120)
    name_en = models.CharField("英文名称", max_length=120, blank=True, default="")
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
            ("restore_product", "可从回收站还原商品"),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        # Django checks uniqueness through the live manager. A recycled SKU is still reserved.
        if exclude and "sku" in exclude:
            return
        recycled = Product.all_objects.filter(sku=self.sku, recycle_entry__isnull=False)
        if self.sku and recycled.exclude(pk=self.pk).exists():
            raise ValidationError({"sku": self.unique_error_message(Product, ("sku",))})

    def delete(self, using=None, keep_parents=False):
        if not self._is_pk_set():
            raise ValueError("Cannot delete a product without a primary key.")
        db = using or router.db_for_write(type(self), instance=self)
        return Product.all_objects.using(db).filter(pk=self.pk).delete()

    delete.alters_data = True


class ProductRecycleEntry(models.Model):
    # A new primary key for each deletion keeps old restore forms from reviving a later deletion.
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="recycle_entry")
    deleted_at = models.DateTimeField("删除时间", auto_now_add=True)

    class Meta:
        default_permissions = ()


class ProductPublicationRequest(models.Model):
    class Result(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="publication_requests")
    # Older pending applications acquire a site when their result is first recorded.
    site = models.CharField(max_length=100, blank=True, default="")
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


class ProductBatchTask(models.Model):
    class Operation(models.TextChoices):
        SUBMIT_PUBLICATION = "submit_publication", "批量提交上架审批"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    site = models.CharField(max_length=100)
    operation = models.CharField(max_length=32, choices=Operation.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        indexes = [models.Index(fields=["owner", "site", "-created_at"], name="catalog_batch_owner_site")]


class ProductBatchItem(models.Model):
    class Outcome(models.TextChoices):
        PENDING = "pending", "待处理"
        SUBMITTED = "submitted", "已提交上架审批"
        NOT_DRAFT = "not_draft", "商品不是草稿"
        CONFLICT = "conflict", "已有待审批申请，或商品、审批记录已变化"
        UNAVAILABLE = "unavailable", "商品不可用或修改权限已变化"
        INVALID = "invalid", "提交校验失败"

    task = models.ForeignKey(ProductBatchTask, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    product_updated_at = models.DateTimeField()
    previous_request_id = models.PositiveBigIntegerField(default=0)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, default=Outcome.PENDING)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["task", "product"], name="catalog_batch_unique_product")]
        indexes = [models.Index(fields=["task", "outcome", "id"], name="catalog_batch_pending")]


class ProductNotification(models.Model):
    # Each source has one recipient, one site, and at most one result notification.
    publication = models.OneToOneField(ProductPublicationRequest, null=True, on_delete=models.CASCADE, related_name="+")
    task = models.OneToOneField(ProductBatchTask, null=True, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(
            condition=(models.Q(publication__isnull=False, task__isnull=True)
                       | models.Q(publication__isnull=True, task__isnull=False)),
            name="catalog_notification_one_source",
        )]


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
