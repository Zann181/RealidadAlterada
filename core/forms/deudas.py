from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.utils import timezone

from core.forms.fields import EnteroMilesField
from core.models import (
    AbonoDeudaCliente,
    AbonoDeudaProveedor,
    DeudaCliente,
    DeudaClienteDetalle,
    DeudaProveedor,
    DeudaProveedorDetalle,
    Deudor,
)
from core.utils.numbers import format_miles


def _fecha_a_datetime(fecha):
    if fecha is None:
        return fecha
    if isinstance(fecha, datetime):
        return fecha
    return timezone.make_aware(datetime.combine(fecha, time.min))


class DeudorForm(forms.ModelForm):
    class Meta:
        model = Deudor
        fields = ["nombre", "telefono", "correo", "documento", "direccion"]


class DeudaAntiguaForm(forms.Form):
    fecha = forms.DateField(
        label="Fecha",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    descripcion = forms.CharField(required=False, label="Descripcion de la deuda")
    valor = EnteroMilesField(min_value=0, required=False, label="Valor")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()
        self.fields["valor"].help_text = "Sin decimales. Use punto para miles."

    def clean_fecha(self):
        return _fecha_a_datetime(self.cleaned_data.get("fecha"))


class AbonoClienteRapidoForm(forms.Form):
    deuda = forms.ModelChoiceField(queryset=DeudaCliente.objects.none(), label="Deuda")
    fecha = forms.DateField(
        label="Fecha",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    valor = EnteroMilesField(min_value=0, required=True, label="Valor")
    medio_pago = forms.ChoiceField(
        choices=AbonoDeudaCliente.MEDIO_PAGO_CHOICES,
        required=False,
        label="Medio de pago",
    )
    referencia = forms.CharField(required=False, label="Referencia")
    nota = forms.CharField(required=False, label="Nota")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()
        self.fields["valor"].help_text = "Sin decimales. Use punto para miles."

    def clean_fecha(self):
        return _fecha_a_datetime(self.cleaned_data.get("fecha"))


class DeudaClienteForm(forms.ModelForm):
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.fecha:
            self.initial["fecha"] = timezone.localtime(self.instance.fecha).date()
        elif not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()

    def clean_fecha(self):
        return _fecha_a_datetime(self.cleaned_data.get("fecha"))

    class Meta:
        model = DeudaCliente
        fields = ["deudor", "fecha", "descripcion"]


class DeudaClienteDetalleForm(forms.ModelForm):
    cantidad = EnteroMilesField(min_value=1, required=True, label="Cantidad")
    iva = EnteroMilesField(
        label="IVA (%)",
        min_value=0,
        max_value=100,
        required=False,
    )
    precio_unitario_inicial = EnteroMilesField(
        min_value=0,
        required=True,
        label="Precio inicial",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].help_text = "Solo numeros enteros."
        self.fields["iva"].help_text = "Ingrese el porcentaje, ej. 19"
        self.fields["precio_unitario_inicial"].help_text = "Sin decimales. Use punto para miles."
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
        model = DeudaClienteDetalle
        fields = ["producto", "cantidad", "precio_unitario_inicial", "iva"]

    def clean_iva(self):
        iva = self.cleaned_data.get("iva")
        if iva is None:
            return Decimal("0.000")
        return (Decimal(iva) / Decimal("100")).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )


class AbonoDeudaClienteForm(forms.ModelForm):
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
        return _fecha_a_datetime(self.cleaned_data.get("fecha"))

    class Meta:
        model = AbonoDeudaCliente
        fields = ["fecha", "valor", "medio_pago", "referencia", "nota"]


class DeudaProveedorForm(forms.ModelForm):
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.fecha:
            self.initial["fecha"] = timezone.localtime(self.instance.fecha).date()
        elif not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localdate()

    def clean_fecha(self):
        return _fecha_a_datetime(self.cleaned_data.get("fecha"))

    class Meta:
        model = DeudaProveedor
        fields = ["proveedor", "fecha", "numero_factura", "descripcion"]


class DeudaProveedorDetalleForm(forms.ModelForm):
    cantidad = EnteroMilesField(min_value=1, required=True, label="Cantidad")
    iva = EnteroMilesField(
        label="IVA (%)",
        min_value=0,
        max_value=100,
        required=False,
    )
    costo_unitario_inicial = EnteroMilesField(
        min_value=0,
        required=True,
        label="Costo inicial",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].help_text = "Solo numeros enteros."
        self.fields["iva"].help_text = "Ingrese el porcentaje, ej. 19"
        self.fields["costo_unitario_inicial"].help_text = "Sin decimales. Use punto para miles."
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
        model = DeudaProveedorDetalle
        fields = ["producto", "cantidad", "costo_unitario_inicial", "iva"]

    def clean_iva(self):
        iva = self.cleaned_data.get("iva")
        if iva is None:
            return Decimal("0.000")
        return (Decimal(iva) / Decimal("100")).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )


class AbonoDeudaProveedorForm(forms.ModelForm):
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
        return _fecha_a_datetime(self.cleaned_data.get("fecha"))

    class Meta:
        model = AbonoDeudaProveedor
        fields = ["fecha", "valor", "medio_pago", "referencia", "nota"]
