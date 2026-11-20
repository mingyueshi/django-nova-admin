from django.contrib import admin
from django.contrib.admin.models import LogEntry


class OperatorFilter(admin.RelatedOnlyFieldListFilter):
    def has_output(self):
        # Honor a bookmarked operator filter even if only one operator remains.
        return bool(self.lookup_val) or super().has_output()


@admin.register(LogEntry)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("action_time", "user", "action_flag", "content_type", "object_repr")
    list_filter = (("user", OperatorFilter), "action_flag", "action_time")
    list_select_related = ("user", "content_type")
    fields = (*list_display, "object_id", "change_details")
    readonly_fields = fields
    actions = None

    @admin.display(description="变更内容")
    def change_details(self, obj):
        return obj.get_change_message()

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("admin.view_logentry")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
