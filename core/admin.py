from django.contrib import admin

from core import models


@admin.register(models.Deudor)
class DeudorAdmin(admin.ModelAdmin):
    search_fields = ("nombre", "telefono", "documento", "correo")
    list_display = ("nombre", "telefono", "correo", "documento")


@admin.register(models.Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "canal", "medio_pago", "deudor", "total", "estado")
    list_filter = ("estado", "medio_pago", "canal")
    search_fields = ("id", "deudor__nombre", "deudor__documento")
    autocomplete_fields = ("deudor",)


@admin.register(models.DeudaCliente)
class DeudaClienteAdmin(admin.ModelAdmin):
    list_display = ("id", "deudor", "venta", "fecha", "estado", "total_inicial", "saldo_actual")
    list_filter = ("estado",)
    search_fields = ("id", "deudor__nombre", "venta__id")
    autocomplete_fields = ("deudor", "venta")


class VentaWebItemInline(admin.TabularInline):
    model = models.VentaWebItem
    extra = 0
    readonly_fields = ("producto", "cantidad", "precio_unitario", "total_linea")


@admin.register(models.VentaWeb)
class VentaWebAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "telefono", "total", "estado", "creado_en")
    list_filter = ("estado",)
    search_fields = ("id", "nombre", "telefono", "correo")
    inlines = (VentaWebItemInline,)


admin.site.register(models.Categoria)
admin.site.register(models.Producto)
admin.site.register(models.Proveedor)
admin.site.register(models.Inventario)
admin.site.register(models.Compra)
admin.site.register(models.CompraDetalle)
admin.site.register(models.VentaDetalle)
admin.site.register(models.CategoriaGasto)
admin.site.register(models.Gasto)
admin.site.register(models.MovimientoInventario)
admin.site.register(models.DeudaClienteDetalle)
admin.site.register(models.AbonoDeudaCliente)
admin.site.register(models.DeudaProveedor)
admin.site.register(models.DeudaProveedorDetalle)
admin.site.register(models.AbonoDeudaProveedor)
admin.site.register(models.VentaWebItem)
