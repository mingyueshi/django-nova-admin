"""Project-only Chinese form presentation; never patch Django's global classes."""
import re

from django.conf import settings
from django.forms import CheckboxInput
from django.forms.renderers import DjangoTemplates
from django.utils.safestring import SafeData, mark_safe
from django.utils.translation import get_language, gettext


def chinese_admin():
    return settings.USE_I18N and (get_language() or "").lower().replace("_", "-") in {"zh", "zh-hans", "zh-cn"}


def chinese_label(value):
    """One real fullwidth colon, preserving the original label's escaping status."""
    if not chinese_admin() or not value:
        return value
    text = re.sub(r"[\s:：]+$", "", str(value)) + "："
    return mark_safe(text) if isinstance(value, SafeData) else text


class ProjectAdminFormRenderer(DjangoTemplates):
    def render(self, template_name, context, request=None):
        if chinese_admin():
            if template_name == "django/forms/label.html":
                # BoundField has already selected label/legend, for/id and classes.
                # Checkbox action phrases keep Django's deliberate empty suffix.
                # This also leaves option captions inside radio groups untouched.
                if not isinstance(context["field"].field.widget, CheckboxInput):
                    context = {**context, "label": chinese_label(context["label"])}
            elif template_name == "django/forms/widgets/select.html":
                # 5.2/6.0 have a literal dashed blank label; 6.1 has a gettext ID.
                # Change only known default blank captions. Keep values, custom
                # captions, validation, selected flags and option attrs untouched.
                widget = context["widget"]
                groups = []
                for name, options, index in widget["optgroups"]:
                    options = [
                        {**option, "label": gettext("- Select an option -")}
                        if option["value"] == "" and str(option["label"]) in {
                            "---------", "- Select an option -"
                        } else option
                        for option in options
                    ]
                    groups.append((name, options, index))
                context = {**context, "widget": {**widget, "optgroups": groups}}
        return super().render(template_name, context, request=request)
