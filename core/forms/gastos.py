from datetime import datetime, time

from django import forms
from django.utils import timezone

from core.forms.fields import EnteroMilesField
from core.models import CategoriaGasto, Gasto


class CategoriaGastoForm(forms.ModelForm):
    class Meta:
        model = CategoriaGasto
        fields = ["nombre"]


class GastoForm(forms.ModelForm):
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    valor = EnteroMilesField(min_value=0, required=True, label="Valor")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.fecha:
            self.initial["fecha"] = timezone.localtime(self.instance.fecha).date()
        elif not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()
        self.fields["valor"].help_text = "Sin decimales. Use punto para miles."

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha is None:
            return fecha
        if isinstance(fecha, datetime):
            return fecha
        return timezone.make_aware(datetime.combine(fecha, time.min))

    class Meta:
        model = Gasto
        fields = ["categoria_gasto", "fecha", "valor", "medio_pago", "descripcion"]
