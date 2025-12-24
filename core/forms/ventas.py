from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.utils import timezone

from core.forms.fields import EnteroMilesField
from core.models import Deudor, Venta, VentaDetalle
from core.utils.numbers import format_miles


class VentaForm(forms.ModelForm):
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    descuento_total = EnteroMilesField(
        min_value=0,
        max_value=100,
        required=False,
        label="Descuento (%)",
    )
    nuevo_deudor_nombre = forms.CharField(required=False, label="Nombre del deudor")
    nuevo_deudor_telefono = forms.CharField(required=False, label="Telefono")
    nuevo_deudor_correo = forms.EmailField(required=False, label="Correo")
    nuevo_deudor_documento = forms.CharField(required=False, label="Documento")
    nuevo_deudor_direccion = forms.CharField(required=False, label="Direccion")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descuento_total"].help_text = "Ej. 10 para 10%."
        if "deudor" in self.fields:
            self.fields["deudor"].queryset = Deudor.objects.order_by("nombre")
        if self.instance and self.instance.pk and self.instance.fecha:
            self.initial["fecha"] = timezone.localtime(self.instance.fecha).date()
        elif not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()

    class Meta:
        model = Venta
        fields = ["fecha", "canal", "medio_pago", "deudor", "descuento_total"]

    def clean_descuento_total(self):
        value = self.cleaned_data.get("descuento_total")
        return value or 0

    def clean(self):
        cleaned = super().clean()
        medio_pago = cleaned.get("medio_pago")
        deudor = cleaned.get("deudor")
        nuevo_nombre = (cleaned.get("nuevo_deudor_nombre") or "").strip()
        cleaned["nuevo_deudor_nombre"] = nuevo_nombre
        if medio_pago == "DEUDA" and not deudor and not nuevo_nombre:
            raise forms.ValidationError("Debe seleccionar o registrar un deudor.")
        return cleaned

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha is None:
            return fecha
        if isinstance(fecha, datetime):
            return fecha
        return timezone.make_aware(datetime.combine(fecha, time.min))


class VentaDetalleForm(forms.ModelForm):
    cantidad = EnteroMilesField(min_value=1, required=True, label="Cantidad")
    iva = EnteroMilesField(
        label="IVA (%)",
        min_value=0,
        max_value=100,
        required=False,
    )
    precio_unitario = EnteroMilesField(min_value=0, required=True, label="Precio unitario")
    descuento_unitario = EnteroMilesField(min_value=0, required=False, label="Descuento unitario")
    costo_unitario_en_venta = EnteroMilesField(
        min_value=0,
        required=False,
        label="Costo unitario",
    )
    total_linea = EnteroMilesField(min_value=0, required=False, label="Total linea")
    ganancia_linea = EnteroMilesField(min_value=0, required=False, label="Ganancia linea")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].help_text = "Solo numeros enteros."
        self.fields["iva"].help_text = "Ingrese el porcentaje, ej. 19"
        self.fields["precio_unitario"].help_text = "Sin decimales. Use punto para miles."
        self.fields["descuento_unitario"].help_text = "Sin decimales. Use punto para miles."
        self.fields["costo_unitario_en_venta"].help_text = "Sin decimales. Use punto para miles."
        self.fields["total_linea"].help_text = "Sin decimales. Use punto para miles."
        self.fields["ganancia_linea"].help_text = "Sin decimales. Use punto para miles."
        if self.instance and self.instance.pk and self.instance.iva is not None:
            iva_valor = Decimal(self.instance.iva) * Decimal("100")
            self.fields["iva"].initial = iva_valor.quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        if "producto" in self.fields:
            self.fields["producto"].label_from_instance = (
                lambda obj: f"{obj.nombre} - {format_miles(obj.precio_venta)}"
            )

    class Meta:
        model = VentaDetalle
        fields = [
            "producto",
            "cantidad",
            "precio_unitario",
            "descuento_unitario",
            "iva",
            "costo_unitario_en_venta",
            "total_linea",
            "ganancia_linea",
        ]

    def clean_iva(self):
        iva = self.cleaned_data.get("iva")
        if iva is None:
            return Decimal("0.000")
        return (Decimal(iva) / Decimal("100")).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )

    def clean_descuento_unitario(self):
        value = self.cleaned_data.get("descuento_unitario")
        return value or 0

    def clean_costo_unitario_en_venta(self):
        value = self.cleaned_data.get("costo_unitario_en_venta")
        return value or 0

    def clean_total_linea(self):
        value = self.cleaned_data.get("total_linea")
        return value or 0

    def clean_ganancia_linea(self):
        value = self.cleaned_data.get("ganancia_linea")
        return value or 0
