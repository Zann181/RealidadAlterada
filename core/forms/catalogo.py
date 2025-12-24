from decimal import Decimal, ROUND_HALF_UP

from django import forms

from core.forms.fields import EnteroMilesField
from core.models import Categoria, Producto, Proveedor, Inventario


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre"]


class ProductoForm(forms.ModelForm):
    iva = EnteroMilesField(
        label="IVA (%)",
        min_value=0,
        max_value=100,
        required=False,
    )
    stock_minimo = EnteroMilesField(min_value=0, required=False, label="Stock minimo")
    stock_actual = EnteroMilesField(min_value=0, required=False, label="Stock disponible")
    costo_compra = EnteroMilesField(min_value=0, required=False, label="Costo compra")
    precio_venta = EnteroMilesField(min_value=0, required=False, label="Precio venta")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sku"].required = False
        self.fields["sku"].help_text = "Se genera automaticamente segun la categoria."
        self.fields["stock_minimo"].help_text = "Solo numeros enteros."
        self.fields["stock_actual"].help_text = "Solo numeros enteros."
        self.fields["costo_compra"].help_text = "Sin decimales. Use punto para miles."
        self.fields["precio_venta"].help_text = "Sin decimales. Use punto para miles."
        self.fields["iva"].help_text = "Ingrese el porcentaje, ej. 19"
        if self.instance and self.instance.pk:
            if self.instance.stock_minimo is not None:
                stock_minimo = Decimal(self.instance.stock_minimo)
                self.fields["stock_minimo"].initial = int(
                    stock_minimo.to_integral_value(rounding=ROUND_HALF_UP)
                )
            cantidad = (
                Inventario.objects.filter(producto=self.instance)
                .values_list("cantidad", flat=True)
                .first()
            )
            if cantidad is not None:
                self.fields["stock_actual"].initial = int(
                    Decimal(cantidad).to_integral_value(rounding=ROUND_HALF_UP)
                )
            if self.instance.iva is not None:
                iva_valor = Decimal(self.instance.iva) * Decimal("100")
                self.fields["iva"].initial = iva_valor.quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            if self.instance.costo_compra is not None:
                self.fields["costo_compra"].initial = int(
                    Decimal(self.instance.costo_compra).to_integral_value(rounding=ROUND_HALF_UP)
                )
            if self.instance.precio_venta is not None:
                self.fields["precio_venta"].initial = int(
                    Decimal(self.instance.precio_venta).to_integral_value(rounding=ROUND_HALF_UP)
                )

    class Meta:
        model = Producto
        fields = [
            "sku",
            "nombre",
            "descripcion",
            "categoria",
            "proveedor",
            "unidad",
            "iva",
            "stock_minimo",
            "costo_compra",
            "precio_venta",
            "imagen",
            "imagen_alt",
            "activo",
        ]

    def clean_iva(self):
        iva = self.cleaned_data.get("iva")
        if iva is None:
            return Decimal("0.000")
        return (Decimal(iva) / Decimal("100")).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )

    def clean_costo_compra(self):
        value = self.cleaned_data.get("costo_compra")
        if value is None:
            return Decimal("0.00")
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def clean_precio_venta(self):
        value = self.cleaned_data.get("precio_venta")
        if value is None:
            return Decimal("0.00")
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "telefono", "correo", "nit", "direccion"]
