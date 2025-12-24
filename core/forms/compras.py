from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.utils import timezone

from core.forms.fields import EnteroMilesField
from core.models import Compra, CompraDetalle
from core.utils.numbers import format_miles


class CompraForm(forms.ModelForm):
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    otros_costos = EnteroMilesField(min_value=0, required=False, label="Otros costos")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.fecha:
            self.initial["fecha"] = timezone.localtime(self.instance.fecha).date()
        elif not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()
        self.fields["otros_costos"].help_text = "Sin decimales. Use punto para miles."

    class Meta:
        model = Compra
        fields = ["proveedor", "fecha", "numero_factura", "otros_costos"]

    def clean_otros_costos(self):
        value = self.cleaned_data.get("otros_costos")
        return value or 0

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha is None:
            return fecha
        if isinstance(fecha, datetime):
            return fecha
        return timezone.make_aware(datetime.combine(fecha, time.min))


class CompraDetalleForm(forms.ModelForm):
    cantidad = EnteroMilesField(min_value=1, required=True, label="Cantidad")
    iva = EnteroMilesField(
        label="IVA (%)",
        min_value=0,
        max_value=100,
        required=False,
    )
    costo_unitario = EnteroMilesField(min_value=0, required=True, label="Costo unitario")
    total_linea = EnteroMilesField(min_value=0, required=False, label="Total linea")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].help_text = "Solo numeros enteros."
        self.fields["iva"].help_text = "Ingrese el porcentaje, ej. 19"
        self.fields["costo_unitario"].help_text = "Sin decimales. Use punto para miles."
        self.fields["total_linea"].help_text = "Se calcula automaticamente."
        self.fields["total_linea"].widget.attrs["readonly"] = True
        if self.instance and self.instance.pk and self.instance.iva is not None:
            iva_valor = Decimal(self.instance.iva) * Decimal("100")
            self.fields["iva"].initial = iva_valor.quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        if "producto" in self.fields:
            self.fields["producto"].label_from_instance = (
                lambda obj: f"{obj.nombre} - {format_miles(obj.costo_compra)}"
            )

    class Meta:
        model = CompraDetalle
        fields = ["producto", "cantidad", "costo_unitario", "iva", "total_linea"]

    def clean_iva(self):
        iva = self.cleaned_data.get("iva")
        if iva is None:
            return Decimal("0.000")
        return (Decimal(iva) / Decimal("100")).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )

    def clean_total_linea(self):
        value = self.cleaned_data.get("total_linea")
        return value or 0
