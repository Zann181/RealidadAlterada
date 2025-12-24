from django.urls import path

from core.views import dashboard, catalogo, compras, ventas, gastos, reportes, clientes, deudas, tienda, referidos

app_name = "core"

urlpatterns = [
    path("", tienda.tienda_view, name="tienda_home"),
    path("tienda/", tienda.tienda_view, name="tienda"),
    path("tienda/producto/<int:pk>/", tienda.tienda_producto_detail, name="tienda_producto_detail"),
    path("panel/", dashboard.dashboard_view, name="dashboard"),
    path("panel/referidos-whatsapp/", referidos.referidos_whatsapp_view, name="referidos_whatsapp"),
    path(
        "panel/referidos-whatsapp/<int:pk>/convertir-borrador/",
        referidos.referidos_whatsapp_convertir_borrador,
        name="referidos_whatsapp_convertir_borrador",
    ),
    path("tienda/checkout/", tienda.tienda_checkout, name="tienda_checkout"),
    path("cliente/", clientes.cliente_dashboard, name="cliente_dashboard"),
    # Deudores
    path("deudores/", deudas.deudor_list, name="deudores_list"),
    path("deudores/nuevo/", deudas.deudor_create, name="deudores_create"),
    path("deudores/<int:pk>/editar/", deudas.deudor_update, name="deudores_update"),
    path("deudores/<int:pk>/", deudas.deudor_detail, name="deudores_detail"),
    path("deudores/<int:pk>/abonar/", deudas.deudor_add_abono, name="deudores_abonar"),
    path(
        "deudores/<int:deudor_id>/deudas/nueva/",
        deudas.deuda_cliente_create,
        name="deuda_cliente_create",
    ),
    # Deudas clientes
    path("deudas/clientes/<int:pk>/", deudas.deuda_cliente_detail, name="deuda_cliente_detail"),
    path(
        "deudas/clientes/<int:pk>/agregar-item/",
        deudas.deuda_cliente_add_item,
        name="deuda_cliente_add_item",
    ),
    path(
        "deudas/clientes/<int:pk>/abonar/",
        deudas.deuda_cliente_add_abono,
        name="deuda_cliente_add_abono",
    ),
    path(
        "deudas/clientes/<int:pk>/cerrar/",
        deudas.deuda_cliente_cerrar,
        name="deuda_cliente_cerrar",
    ),
    # Deudas proveedores
    path("deudas/proveedores/", deudas.deuda_proveedor_list, name="deuda_proveedor_list"),
    path("deudas/proveedores/nueva/", deudas.deuda_proveedor_create, name="deuda_proveedor_create"),
    path(
        "deudas/proveedores/<int:pk>/",
        deudas.deuda_proveedor_detail,
        name="deuda_proveedor_detail",
    ),
    path(
        "deudas/proveedores/<int:pk>/agregar-item/",
        deudas.deuda_proveedor_add_item,
        name="deuda_proveedor_add_item",
    ),
    path(
        "deudas/proveedores/<int:pk>/abonar/",
        deudas.deuda_proveedor_add_abono,
        name="deuda_proveedor_add_abono",
    ),
    path(
        "deudas/proveedores/<int:pk>/cerrar/",
        deudas.deuda_proveedor_cerrar,
        name="deuda_proveedor_cerrar",
    ),
    # Catalogo
    path("catalogo/categorias/", catalogo.categoria_list, name="categorias_list"),
    path("catalogo/categorias/nueva/", catalogo.categoria_create, name="categorias_create"),
    path("catalogo/categorias/<int:pk>/editar/", catalogo.categoria_update, name="categorias_update"),
    path("catalogo/categorias/<int:pk>/eliminar/", catalogo.categoria_delete, name="categorias_delete"),
    path("catalogo/productos/", catalogo.producto_list, name="productos_list"),
    path("catalogo/productos/nuevo/", catalogo.producto_create, name="productos_create"),
    path("catalogo/productos/<int:pk>/", catalogo.producto_detail, name="productos_detail"),
    path("catalogo/productos/<int:pk>/editar/", catalogo.producto_update, name="productos_update"),
    path("catalogo/productos/<int:pk>/eliminar/", catalogo.producto_delete, name="productos_delete"),
    path("catalogo/proveedores/", catalogo.proveedor_list, name="proveedores_list"),
    path("catalogo/proveedores/nuevo/", catalogo.proveedor_create, name="proveedores_create"),
    path("catalogo/proveedores/<int:pk>/", catalogo.proveedor_detail, name="proveedores_detail"),
    path("catalogo/proveedores/<int:pk>/editar/", catalogo.proveedor_update, name="proveedores_update"),
    path("catalogo/proveedores/<int:pk>/eliminar/", catalogo.proveedor_delete, name="proveedores_delete"),
    # Compras
    path("compras/", compras.compra_list, name="compras_list"),
    path("compras/nueva/", compras.compra_create, name="compras_create"),
    path("compras/<int:pk>/", compras.compra_detail, name="compras_detail"),
    path("compras/<int:pk>/agregar-item/", compras.compra_add_item, name="compras_add_item"),
    path("compras/<int:pk>/crear-deuda/", compras.compra_crear_deuda, name="compras_crear_deuda"),
    path("compras/<int:pk>/confirmar/", compras.compra_confirm, name="compras_confirm"),
    path("compras/<int:pk>/anular/", compras.compra_cancel, name="compras_cancel"),
    # Ventas
    path("ventas/", ventas.venta_list, name="ventas_list"),
    path("ventas/nueva/", ventas.venta_create, name="ventas_create"),
    path("ventas/<int:pk>/", ventas.venta_detail, name="ventas_detail"),
    path("ventas/<int:pk>/agregar-item/", ventas.venta_add_item, name="ventas_add_item"),
    path("ventas/<int:pk>/imprimir/", ventas.venta_print, name="ventas_print"),
    path(
        "ventas/<int:pk>/actualizar-descuento/",
        ventas.venta_update_descuento,
        name="ventas_update_descuento",
    ),
    path(
        "ventas/<int:pk>/actualizar-iva/",
        ventas.venta_update_iva,
        name="ventas_update_iva",
    ),
    path(
        "ventas/<int:pk>/actualizar/",
        ventas.venta_update_totales,
        name="ventas_update_totales",
    ),
    path("ventas/<int:pk>/eliminar/", ventas.venta_delete, name="ventas_delete"),
    path("ventas/<int:pk>/confirmar/", ventas.venta_confirm, name="ventas_confirm"),
    path("ventas/<int:pk>/anular/", ventas.venta_cancel, name="ventas_cancel"),
    # Gastos
    path("gastos/", gastos.gasto_list, name="gastos_list"),
    # Reportes
    path("reportes/ventas/", reportes.reporte_ventas, name="reportes_ventas"),
    path("reportes/ganancias/", reportes.reporte_ganancias, name="reportes_ganancias"),
    path("reportes/utilidad-neta/", reportes.reporte_utilidad_neta, name="reportes_utilidad_neta"),
]
