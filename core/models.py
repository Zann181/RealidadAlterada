# core/models.py
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.text import slugify


# =========================
# CATÁLOGO
# =========================
class Categoria(models.Model):
    nombre = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField("SKU", max_length=60, unique=True, blank=True)
    nombre = models.CharField(max_length=180)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos", null=True, blank=True
    )
    proveedor = models.ForeignKey(
        "Proveedor",
        on_delete=models.PROTECT,
        related_name="productos",
        null=True,
        blank=True,
    )

    unidad = models.CharField(max_length=20, default="unidad")  # unidad, kg, caja...
    iva = models.DecimalField(max_digits=6, decimal_places=3, default=0.000)  # ej 0.190
    stock_minimo = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    costo_compra = models.DecimalField("Costo compra", max_digits=18, decimal_places=2, default=0)
    precio_venta = models.DecimalField("Precio venta", max_digits=18, decimal_places=2, default=0)

    # ✅ Imagen (RECOMENDADO: subir archivo)
    imagen = models.ImageField(upload_to="productos/", null=True, blank=True)
    imagen_alt = models.CharField(max_length=180, blank=True, default="")

    descripcion = models.TextField(blank=True, default="")

    # ✅ Alternativa si quieres EXACTO como DBML (URL/ruta):
    # imagen_url = models.URLField(max_length=500, blank=True, default="")

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    imagen_max_size = (1200, 1200)
    imagen_quality = 82

    def _generar_sku(self):
        # SKU: PREFIJO-CORRELATIVO, donde el prefijo se deriva de la categoria.
        if self.categoria:
            base = slugify(self.categoria.nombre, allow_unicode=False).replace("-", "").upper()
        else:
            base = "GEN"
        if not base:
            base = "GEN"
        prefijo = base[:8]
        token = f"{prefijo}-"
        existentes = Producto.objects.filter(sku__startswith=token).values_list("sku", flat=True)
        max_num = 0
        for sku in existentes:
            sufijo = sku[len(token):]
            if sufijo.isdigit():
                max_num = max(max_num, int(sufijo))
        return f"{prefijo}-{max_num + 1:04d}"

    def _imagen_debe_procesarse(self):
        if not self.imagen:
            return False
        if not self.pk:
            return True
        anterior = (
            Producto.objects.filter(pk=self.pk)
            .values_list("imagen", flat=True)
            .first()
        )
        return anterior != self.imagen.name

    def _procesar_imagen(self):
        if not self.imagen:
            return
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except Exception:
            return

        archivo = self.imagen
        try:
            archivo.seek(0)
        except Exception:
            pass

        try:
            imagen = Image.open(archivo)
        except UnidentifiedImageError:
            return

        imagen = ImageOps.exif_transpose(imagen)
        has_alpha = imagen.mode in ("RGBA", "LA") or (
            imagen.mode == "P" and "transparency" in imagen.info
        )
        if has_alpha:
            imagen = imagen.convert("RGBA")
        elif imagen.mode != "RGB":
            imagen = imagen.convert("RGB")

        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS

        imagen.thumbnail(self.imagen_max_size, resample)

        buffer = BytesIO()
        extension = "webp"
        try:
            imagen.save(buffer, format="WEBP", quality=self.imagen_quality, optimize=True)
        except OSError:
            buffer = BytesIO()
            extension = "jpg"
            if imagen.mode != "RGB":
                imagen = imagen.convert("RGB")
            imagen.save(
                buffer,
                format="JPEG",
                quality=self.imagen_quality,
                optimize=True,
                progressive=True,
            )
        buffer.seek(0)

        base_name = Path(archivo.name).stem
        nuevo_nombre = f"productos/{base_name}.{extension}"
        self.imagen.save(nuevo_nombre, ContentFile(buffer.read()), save=False)

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self._generar_sku()
        procesar_imagen = self._imagen_debe_procesarse()
        anterior = None
        if procesar_imagen and self.pk:
            anterior = (
                Producto.objects.filter(pk=self.pk)
                .values_list("imagen", flat=True)
                .first()
            )
        if procesar_imagen:
            self._procesar_imagen()
        super().save(*args, **kwargs)
        if anterior and anterior != self.imagen.name:
            try:
                self.imagen.storage.delete(anterior)
            except Exception:
                pass

    def __str__(self):
        return f"{self.sku} - {self.nombre}"


class ProductoImagen(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="imagenes",
    )
    imagen = models.ImageField(upload_to="productos/galeria/", null=True, blank=True)
    imagen_alt = models.CharField(max_length=180, blank=True, default="")
    orden = models.PositiveIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    imagen_max_size = (1200, 1200)
    imagen_quality = 82

    class Meta:
        ordering = ("orden", "id")

    def _imagen_debe_procesarse(self):
        if not self.imagen:
            return False
        if not self.pk:
            return True
        anterior = (
            ProductoImagen.objects.filter(pk=self.pk)
            .values_list("imagen", flat=True)
            .first()
        )
        return anterior != self.imagen.name

    def _procesar_imagen(self):
        if not self.imagen:
            return
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except Exception:
            return

        archivo = self.imagen
        try:
            archivo.seek(0)
        except Exception:
            pass

        try:
            imagen = Image.open(archivo)
        except UnidentifiedImageError:
            return

        imagen = ImageOps.exif_transpose(imagen)
        has_alpha = imagen.mode in ("RGBA", "LA") or (
            imagen.mode == "P" and "transparency" in imagen.info
        )
        if has_alpha:
            imagen = imagen.convert("RGBA")
        elif imagen.mode != "RGB":
            imagen = imagen.convert("RGB")

        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS

        imagen.thumbnail(self.imagen_max_size, resample)

        buffer = BytesIO()
        extension = "webp"
        try:
            imagen.save(buffer, format="WEBP", quality=self.imagen_quality, optimize=True)
        except OSError:
            buffer = BytesIO()
            extension = "jpg"
            if imagen.mode != "RGB":
                imagen = imagen.convert("RGB")
            imagen.save(
                buffer,
                format="JPEG",
                quality=self.imagen_quality,
                optimize=True,
                progressive=True,
            )
        buffer.seek(0)

        base_name = Path(archivo.name).stem
        nuevo_nombre = f"productos/galeria/{base_name}.{extension}"
        self.imagen.save(nuevo_nombre, ContentFile(buffer.read()), save=False)

    def save(self, *args, **kwargs):
        if not self.pk and (self.orden is None or self.orden <= 0):
            max_orden = (
                ProductoImagen.objects.filter(producto=self.producto)
                .aggregate(max=models.Max("orden"))
                .get("max")
                or 0
            )
            self.orden = int(max_orden) + 1

        procesar_imagen = self._imagen_debe_procesarse()
        anterior = None
        if procesar_imagen and self.pk:
            anterior = (
                ProductoImagen.objects.filter(pk=self.pk)
                .values_list("imagen", flat=True)
                .first()
            )
        if procesar_imagen:
            self._procesar_imagen()
        super().save(*args, **kwargs)
        if anterior and self.imagen and anterior != self.imagen.name:
            try:
                self.imagen.storage.delete(anterior)
            except Exception:
                pass

    def delete(self, *args, **kwargs):
        storage = self.imagen.storage if self.imagen else None
        name = self.imagen.name if self.imagen else None
        super().delete(*args, **kwargs)
        if storage and name:
            try:
                storage.delete(name)
            except Exception:
                pass

    def __str__(self):
        return f"Imagen #{self.id} - {self.producto_id}"


class ProductoResena(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="resenas",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="resenas_productos",
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=120, blank=True, default="")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-creado_en",)

    def __str__(self):
        return f"{self.producto_id} ({self.rating})"


class Proveedor(models.Model):
    nombre = models.CharField(max_length=160)
    telefono = models.CharField(max_length=40, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    nit = models.CharField(max_length=40, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


# =========================
# INVENTARIO (stock actual)
# =========================
class Inventario(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name="inventario")
    cantidad = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.producto.sku}: {self.cantidad}"


# =========================
# COMPRAS
# =========================
class Compra(models.Model):
    ESTADO_CHOICES = [
        ("BORRADOR", "Borrador"),
        ("CONFIRMADA", "Confirmada"),
        ("ANULADA", "Anulada"),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="compras")
    fecha = models.DateTimeField()
    numero_factura = models.CharField(max_length=80, blank=True, default="")

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    iva_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    otros_costos = models.DecimalField(max_digits=18, decimal_places=2, default=0)  # flete, transporte...
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="CONFIRMADA")

    def __str__(self):
        return f"Compra #{self.id} - {self.proveedor.nombre}"


class CompraDetalle(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="compras_detalle")

    cantidad = models.DecimalField(max_digits=18, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=6)  # costo real proveedor
    iva = models.DecimalField(max_digits=6, decimal_places=3, default=0.000)

    total_linea = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"{self.compra_id} - {self.producto.sku}"


# =========================
# VENTAS
# =========================
class Venta(models.Model):
    ESTADO_CHOICES = [
        ("BORRADOR", "Borrador"),
        ("CONFIRMADA", "Confirmada"),
        ("ANULADA", "Anulada"),
    ]

    CANAL_CHOICES = [
        ("TIENDA", "Tienda"),
        ("DOMICILIO", "Domicilio"),
        ("WHATSAPP", "WhatsApp"),
        ("ONLINE", "Online"),
    ]

    MEDIO_PAGO_CHOICES = [
        ("EFECTIVO", "Efectivo"),
        ("TRANSFERENCIA", "Transferencia"),
        ("TARJETA", "Tarjeta"),
        ("QR", "QR"),
        ("DEUDA", "Deuda"),
        ("OTRO", "Otro"),
    ]

    fecha = models.DateTimeField()

    canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default="TIENDA")
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, default="EFECTIVO")
    deudor = models.ForeignKey(
        "Deudor",
        on_delete=models.PROTECT,
        related_name="ventas",
        null=True,
        blank=True,
    )

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descuento_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    iva_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="CONFIRMADA")

    def __str__(self):
        return f"Venta #{self.id} - {self.fecha}"


class VentaDetalle(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="ventas_detalle")

    cantidad = models.DecimalField(max_digits=18, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=2)
    descuento_unitario = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=6, decimal_places=3, default=0.000)

    # 🔥 clave para ganancia real:
    costo_unitario_en_venta = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    total_linea = models.DecimalField(max_digits=18, decimal_places=2)
    ganancia_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.venta_id} - {self.producto.sku}"


# =========================
# GASTOS (utilidad neta)
# =========================
class CategoriaGasto(models.Model):
    nombre = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.nombre


class Gasto(models.Model):
    MEDIO_PAGO_CHOICES = [
        ("EFECTIVO", "Efectivo"),
        ("TRANSFERENCIA", "Transferencia"),
        ("TARJETA", "Tarjeta"),
        ("OTRO", "Otro"),
    ]

    categoria_gasto = models.ForeignKey(CategoriaGasto, on_delete=models.PROTECT, related_name="gastos")
    fecha = models.DateTimeField()
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, blank=True, default="OTRO")
    descripcion = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.categoria_gasto.nombre} - {self.valor}"


# =========================
# MOVIMIENTOS (Kardex simple / auditoría)
# =========================
class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ("COMPRA", "Compra"),
        ("VENTA", "Venta"),
        ("AJUSTE_POSITIVO", "Ajuste Positivo"),
        ("AJUSTE_NEGATIVO", "Ajuste Negativo"),
        ("DEVOLUCION", "Devolución"),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos")
    fecha = models.DateTimeField()

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    referencia = models.CharField(max_length=40, blank=True, default="")  # "compra", "venta", "ajuste"
    referencia_id = models.BigIntegerField(null=True, blank=True)

    entrada = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    salida = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    costo_unitario = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    saldo_cantidad = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    nota = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.producto.sku} {self.tipo} {self.fecha}"


# =========================
# CREDITOS (DEUDORES)
# =========================
class Deudor(models.Model):
    nombre = models.CharField(max_length=160)
    telefono = models.CharField(max_length=40, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    documento = models.CharField(max_length=40, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class DeudaCliente(models.Model):
    ESTADO_CHOICES = [
        ("ABIERTA", "Abierta"),
        ("CERRADA", "Cerrada"),
        ("ANULADA", "Anulada"),
    ]

    deudor = models.ForeignKey(Deudor, on_delete=models.PROTECT, related_name="deudas")
    venta = models.OneToOneField(
        "Venta",
        on_delete=models.PROTECT,
        related_name="deuda",
        null=True,
        blank=True,
    )
    fecha = models.DateTimeField()
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="ABIERTA")

    total_inicial = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    saldo_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descripcion = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Deuda #{self.id} - {self.deudor.nombre}"


class DeudaClienteDetalle(models.Model):
    deuda = models.ForeignKey(DeudaCliente, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="deudas_clientes_detalle"
    )

    cantidad = models.DecimalField(max_digits=18, decimal_places=3)
    precio_unitario_inicial = models.DecimalField(max_digits=18, decimal_places=2)
    iva = models.DecimalField(max_digits=6, decimal_places=3, default=0.000)
    total_linea = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"{self.deuda_id} - {self.producto.sku}"


class AbonoDeudaCliente(models.Model):
    MEDIO_PAGO_CHOICES = [
        ("EFECTIVO", "Efectivo"),
        ("TRANSFERENCIA", "Transferencia"),
        ("TARJETA", "Tarjeta"),
        ("OTRO", "Otro"),
    ]

    deuda = models.ForeignKey(DeudaCliente, on_delete=models.CASCADE, related_name="abonos")
    fecha = models.DateTimeField()
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, blank=True, default="OTRO")
    referencia = models.CharField(max_length=60, blank=True, default="")
    nota = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Abono #{self.id} - {self.deuda_id}"


# =========================
# CUENTAS POR PAGAR (PROVEEDORES)
# =========================
class DeudaProveedor(models.Model):
    ESTADO_CHOICES = [
        ("ABIERTA", "Abierta"),
        ("CERRADA", "Cerrada"),
        ("ANULADA", "Anulada"),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="deudas")
    fecha = models.DateTimeField()
    numero_factura = models.CharField(max_length=80, blank=True, default="")
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="ABIERTA")

    total_inicial = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    saldo_actual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descripcion = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Deuda Prov #{self.id} - {self.proveedor.nombre}"


class DeudaProveedorDetalle(models.Model):
    deuda = models.ForeignKey(DeudaProveedor, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="deudas_proveedor_detalle"
    )

    cantidad = models.DecimalField(max_digits=18, decimal_places=3)
    costo_unitario_inicial = models.DecimalField(max_digits=18, decimal_places=6)
    iva = models.DecimalField(max_digits=6, decimal_places=3, default=0.000)
    total_linea = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"{self.deuda_id} - {self.producto.sku}"


class AbonoDeudaProveedor(models.Model):
    MEDIO_PAGO_CHOICES = [
        ("EFECTIVO", "Efectivo"),
        ("TRANSFERENCIA", "Transferencia"),
        ("TARJETA", "Tarjeta"),
        ("OTRO", "Otro"),
    ]

    deuda = models.ForeignKey(DeudaProveedor, on_delete=models.CASCADE, related_name="abonos")
    fecha = models.DateTimeField()
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, blank=True, default="OTRO")
    referencia = models.CharField(max_length=60, blank=True, default="")
    nota = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Abono Prov #{self.id} - {self.deuda_id}"


# =========================
# VENTAS WEB (pasarela/tienda)
# =========================
class VentaWeb(models.Model):
    ESTADO_CHOICES = [
        ("EN_PROCESO", "En proceso"),
        ("ENVIADA", "Enviada"),
        ("CERRADA", "Cerrada"),
        ("ANULADA", "Anulada"),
    ]

    nombre = models.CharField(max_length=160, blank=True, default="")
    telefono = models.CharField(max_length=40, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    nota = models.CharField(max_length=255, blank=True, default="")
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="EN_PROCESO")
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Venta web #{self.id}"


class VentaWebItem(models.Model):
    venta = models.ForeignKey(VentaWeb, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="ventas_web")
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.venta_id} - {self.producto.sku}"
