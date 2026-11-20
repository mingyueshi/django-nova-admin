from datetime import timedelta

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class AuditViewerTests(TestCase):
    def test_real_event_filters_and_read_only_permissions(self):
        User = get_user_model()
        operator = User.objects.create_superuser("operator", password="test")
        reviewer = User.objects.create_user("reviewer", is_staff=True)
        self.client.force_login(operator)
        added = self.client.post(reverse("admin:catalog_tag_add"), {"name": "审计样例", "slug": "audit-example"})
        self.assertEqual(added.status_code, 302)
        entry = LogEntry.objects.get()
        self.assertEqual(entry.action_flag, ADDITION)
        listing = reverse("admin:admin_logentry_changelist")
        self.assertEqual(self.client.get(listing, {"user__id__exact": reviewer.pk}).context["cl"].result_count, 0)
        second = User.objects.create_superuser("second", password="test")
        self.client.force_login(second)
        changed = self.client.post(reverse("admin:catalog_tag_change", args=[entry.object_id]),
                                   {"name": "另一条记录", "slug": "audit-example"})
        self.assertEqual(changed.status_code, 302)
        LogEntry.objects.exclude(pk=entry.pk).update(action_time=timezone.now() - timedelta(days=3))
        detail = reverse("admin:admin_logentry_change", args=[entry.pk])
        self.client.force_login(reviewer)
        reviewer.user_permissions.add(Permission.objects.get(codename="change_logentry"))
        self.assertEqual(self.client.get(listing).status_code, 403)
        self.assertEqual(self.client.get(detail).status_code, 403)
        reviewer.user_permissions.add(Permission.objects.get(codename="view_logentry"))
        filters = {"user__id__exact": operator.pk, "action_flag__exact": ADDITION,
                   "action_time__gte": (timezone.now() - timedelta(days=1)).isoformat()}
        self.assertContains(self.client.get(listing, filters), "审计样例")
        for exclude in ({"user__id__exact": second.pk}, {"action_flag__exact": 2},
                        {"action_time__gte": (timezone.now() + timedelta(days=1)).isoformat()}):
            with self.subTest(exclude=exclude):
                rows = self.client.get(listing, {**filters, **exclude}).context["cl"].result_list
                self.assertEqual(len(rows), 0)
        self.assertContains(self.client.get(detail), "审计样例")
        self.client.force_login(operator)
        for url in (detail, reverse("admin:admin_logentry_add"), reverse("admin:admin_logentry_delete", args=[entry.pk])):
            self.assertEqual(self.client.post(url, {"object_repr": "changed"}).status_code, 403)
        self.client.post(listing, {"action": "delete_selected", "_selected_action": entry.pk, "post": "yes"})
        self.assertEqual(LogEntry.objects.get(pk=entry.pk).object_repr, "审计样例")
        self.assertEqual(LogEntry.objects.count(), 2)
