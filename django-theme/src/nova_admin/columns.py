"""Session-scoped presentation preferences for explicitly enabled ModelAdmins."""
import json

from django.conf import settings
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.utils import label_for_field
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from .preferences import selected_mode


class ColumnPreferencesMixin:
    """Hosts opt in by listing stable string identifiers from list_display."""

    nova_preference_columns = ()

    def _column_names(self, cl):
        display = [name for name in cl.list_display if name != "action_checkbox"]
        fixed = [*display[:1], *(cl.list_display_links or ()), *cl.list_editable]
        return [name for name in display if isinstance(name, str) and name not in fixed
                and name in self.nova_preference_columns and display.count(name) == 1]

    def _column_session_key(self, request):
        scope = [request.user._meta.label_lower, str(request.user.pk),
                 request.resolver_match.namespace, self.opts.label_lower]
        return "nova_columns:" + json.dumps(scope, separators=(",", ":"))

    def _column_rows(self, request, names):
        saved = request.session.get(self._column_session_key(request), {})
        if not isinstance(saved, dict):
            saved = {}
        order, hidden = saved.get("order", []), saved.get("hidden", [])
        if not isinstance(order, list) or not isinstance(hidden, list):
            order, hidden = [], []
        previous = [name for name in order if isinstance(name, str) and name in names]
        ordered = dict.fromkeys([*previous, *names])
        return [{"key": name, "label": label_for_field(name, self.model, model_admin=self),
                 "visible": name not in hidden, "default_index": names.index(name)}
                for name in ordered]

    def _save_columns(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        try:
            cl = self.get_changelist_instance(request)
        except IncorrectLookupParameters:
            return HttpResponseBadRequest()
        names = self._column_names(cl)
        if cl.is_popup or not names:
            return HttpResponseNotFound()
        key = self._column_session_key(request)
        action = request.POST.get("_nova_columns")
        if action == "reset":
            request.session.pop(key, None)
        elif action == "save":
            order, visible = request.POST.getlist("order"), request.POST.getlist("visible")
            if (len(order) != len(names) or set(order) != set(names)
                    or not set(visible).issubset(names) or len(set(visible)) != len(visible)):
                return HttpResponseBadRequest()
            request.session[key] = {"order": order, "hidden": [name for name in order if name not in visible]}
        else:
            return HttpResponseBadRequest()
        return JsonResponse({"saved": True})

    @method_decorator(csrf_protect)
    def changelist_view(self, request, extra_context=None):
        enabled = (self.nova_preference_columns and getattr(settings, "NOVA_ADMIN_ENABLED", True)
                   and selected_mode(request) != "native")
        if request.method == "POST" and "_nova_columns" in request.POST:
            if not enabled:
                return HttpResponseNotFound()
            return self._save_columns(request)
        response = super().changelist_view(request, extra_context)
        context = getattr(response, "context_data", None)
        cl = context.get("cl") if context else None
        if enabled and cl is not None and not cl.is_popup:
            names = self._column_names(cl)
            if names:
                context["nova_columns"] = self._column_rows(request, names)
        return response
