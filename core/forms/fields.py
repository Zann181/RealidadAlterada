from django import forms
from django.core.exceptions import ValidationError

from core.utils.numbers import format_miles, parse_miles


class EnteroMilesField(forms.IntegerField):
    def __init__(self, *args, **kwargs):
        widget = kwargs.pop("widget", None) or forms.TextInput()
        super().__init__(*args, widget=widget, **kwargs)
        self.widget.attrs.setdefault("inputmode", "numeric")
        self.widget.attrs.setdefault("pattern", "[0-9.]*")

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return parse_miles(value)
        except (TypeError, ValueError):
            raise ValidationError("Ingrese un numero entero.")

    def prepare_value(self, value):
        if value in self.empty_values:
            return ""
        return format_miles(value)
