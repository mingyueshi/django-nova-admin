"""Copy a product name through the native admin change form."""
import json

from django import forms
from django.contrib.admin.widgets import AdminTextInputWidget
from django.core.exceptions import PermissionDenied
from django.core.signing import Signer
from django.utils.crypto import constant_time_compare

from .models import Product


class ProductNameConflict(Exception):
    """The source or translation changed after form validation."""


class EnglishNameWidget(AdminTextInputWidget):
    template_name = "catalog/widgets/english_name.html"
    copy_selected = False
    confirmation = None

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["stored"] = self.stored
        context["copy_selected"] = self.copy_selected
        context["confirmation"] = self.confirmation
        return context


class ProductNameForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.copy_name = self.data.get("_copy_name") == "1"
        editable = all(name in self.fields and not self.fields[name].disabled for name in ("name", "name_en"))
        if self.instance._state.adding or not editable:
            if self.copy_name:
                raise PermissionDenied
            return

        field = self.fields["name_en"]
        field.widget = widget = EnglishNameWidget(attrs=field.widget.attrs)
        stored = widget.stored = self.initial["name_en"]
        if not self.is_bound:
            return

        key = self.add_prefix("name_en")
        if key not in self.data or (not self.copy_name and self.data[key] == self.data.get("_initial_name_en")):
            # An omitted or untouched translation must survive a save from an older tab.
            self.data = self.data.copy()
            self.data[key] = stored

    def clean(self):
        cleaned = super().clean()
        field = self.fields.get("name_en")
        if not field or not isinstance(field.widget, EnglishNameWidget):
            return cleaned
        widget = field.widget
        source = cleaned.get("name")
        target = cleaned.get("name_en")
        if source and target == source and widget.stored and widget.stored != target:
            # Typing the same copy directly must respect an existing translation too.
            self.copy_name = True
        widget.copy_selected = self.copy_name
        if not self.copy_name or not source or target is None:
            return cleaned

        if any(value and value != source for value in (widget.stored, target)):
            reviewed = json.dumps([self.instance.pk, widget.stored, target, source])
            token = Signer(salt="catalog.product-name-copy").signature(reviewed)
            confirmed = constant_time_compare(self.data.get("_confirm_name_copy", ""), token)
            widget.confirmation = {"token": token, "source": source, "confirmed": confirmed}
            if not confirmed:
                self.add_error("name_en", "英文名称已有内容，请核对并确认覆盖。")
                return cleaned
        cleaned["name_en"] = source
        # The copy checkbox changes the model field even if the text input was untouched.
        self.changed_data = [name for name in self.changed_data if name != "name_en"]
        if source != widget.stored:
            self.changed_data.append("name_en")
        return cleaned
