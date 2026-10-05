"""Optional host-project pagination example; never imported by nova_admin.

Use BoundedPaginationAdminMixin only on ModelAdmins that opt in. Keep this file
in the host project so its paging policy remains a project decision.
"""

import re

from django.contrib.admin.views.main import ALL_VAR, ERROR_FLAG, PAGE_VAR
from django.core.exceptions import ImproperlyConfigured


PAGE_SIZE_PARAM = "_nova_page_size"
PAGE_SIZES = (10, 20, 50, 100)
_PAGE_NUMBER = re.compile(r"[1-9][0-9]{0,8}\Z", re.ASCII)


class BoundedPaginationChangeListMixin:
    def get_filters_params(self, params=None):
        # Keep the parameter in native navigation URLs, but never treat it as
        # an ORM lookup or bypass validation for any other query parameter.
        result = super().get_filters_params(params)
        result.pop(PAGE_SIZE_PARAM, None)
        return result

    def get_results(self, request):
        # ChangeList is instantiated per request; ModelAdmin is shared.
        # Never assign request-dependent values to self.model_admin.
        if self.list_per_page not in PAGE_SIZES:
            raise ImproperlyConfigured(
                "BoundedPaginationAdminMixin requires list_per_page to be "
                "one of 10, 20, 50, 100."
            )
        requested_sizes = request.GET.getlist(PAGE_SIZE_PARAM)
        allowed = {str(size): size for size in PAGE_SIZES}
        if len(requested_sizes) == 1 and requested_sizes[0] in allowed:
            self.list_per_page = allowed[requested_sizes[0]]

        requested_pages = request.GET.getlist(PAGE_VAR)
        if len(requested_pages) != 1 or not _PAGE_NUMBER.fullmatch(requested_pages[0]):
            self.page_num = 1

        # Preserve Django's queryset, paginator, native Show all limit and
        # invalid-page rejection. A valid-looking page beyond the available
        # range follows the native IncorrectLookupParameters / ?e=1 path.
        super().get_results(request)
        if not self.multi_page or (self.show_all and self.can_show_all):
            self.page_num = 1

        # Both query mappings are request-local. Canonical values survive
        # native sort, search, filter, and pagination links.
        self.params[PAGE_SIZE_PARAM] = str(self.list_per_page)
        self.filter_params[PAGE_SIZE_PARAM] = [str(self.list_per_page)]
        self.nova_page_sizes = PAGE_SIZES
        self.nova_page_size_param = PAGE_SIZE_PARAM
        self.nova_page_param = PAGE_VAR
        self.nova_showing_all = self.show_all and self.can_show_all
        self.nova_preserved_params = tuple(
            (name, value)
            for name, values in request.GET.lists()
            if name not in (PAGE_VAR, PAGE_SIZE_PARAM, ERROR_FLAG)
            for value in values
        )
        self.nova_paginated_url = self.get_query_string(
            {ALL_VAR: None, PAGE_VAR: 1, PAGE_SIZE_PARAM: self.list_per_page}
        )


class BoundedPaginationAdminMixin:
    """Put before the project's existing ModelAdmin base classes to opt in.

    An existing custom ChangeList is composed rather than discarded. Projects
    that customize get_results/get_filters_params should test the combination.
    No ModelAdmin, AdminSite, or paginator is modified globally.
    """

    change_list_template = "project_admin/pagination_change_list.html"

    def get_changelist(self, request, **kwargs):
        base = super().get_changelist(request, **kwargs)
        if issubclass(base, BoundedPaginationChangeListMixin):
            return base
        return type("BoundedPaginationChangeList", (BoundedPaginationChangeListMixin, base), {})
