from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_deudacliente_deudor_producto_proveedor_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="producto",
            name="costo_compra",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name="Costo compra"),
        ),
        migrations.AddField(
            model_name="producto",
            name="precio_venta",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name="Precio venta"),
        ),
    ]
