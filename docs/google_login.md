# Login con Google + verificación de email (django-allauth)

Este proyecto tiene soporte **opcional** para Google Login con `django-allauth`, pero está **desactivado por defecto**.

Para activarlo cuando lo necesites:

- Define `ALLAUTH_ENABLED=1` en variables de entorno.
- Instala dependencias (incluye `requests`).

## 1) Instalar dependencias

En tu entorno virtual:

```bash
pip install django-allauth
pip install requests
```

## 2) Migraciones

```bash
python manage.py migrate
```

Esto crea tablas de `django.contrib.sites` y las de `allauth`.

## 3) Configurar el sitio (Django Sites)

1. Entra al admin: `http://127.0.0.1:8000/admin/`
2. Ve a **Sites** → edita el `SITE_ID=1`
3. Pon:
   - **Domain**: `127.0.0.1:8000` (o tu dominio real en producción)
   - **Display name**: `Realidad Alterada`

> Si usas `localhost:8000`, agrega un Site con ese dominio también o cambia el dominio según el que uses.

## 4) Crear credenciales OAuth en Google Cloud

En Google Cloud Console:

1. **APIs & Services** → **Credentials**
2. **Create credentials** → **OAuth client ID**
3. Tipo: **Web application**
4. Agrega los **Authorized redirect URIs**:
   - `http://127.0.0.1:8000/accounts/google/login/callback/`
   - (opcional) `http://localhost:8000/accounts/google/login/callback/`
   - En producción: `https://TU-DOMINIO/accounts/google/login/callback/`

Guarda el **Client ID** y **Client Secret**.

## 5) Configurar Google en Django (SocialApp)

En el admin:

1. Ve a **Social applications**
2. **Add social application**
3. Provider: **Google**
4. Name: por ejemplo `Google`
5. Client id / Secret: los de Google Cloud
6. En **Sites**, añade tu Site (el de `SITE_ID=1`)

## 6) Verificación por email (confirmación)

En `config/settings.py` ya está configurado:

- `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`
- `ACCOUNT_EMAIL_REQUIRED = True`

### En desarrollo

Se usa:

- `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`

Esto imprime el email en la consola del servidor (verás el link de confirmación).

### En producción (para que llegue al Gmail del usuario)

Configura SMTP, por ejemplo con Gmail (requiere **App Password** si tienes 2FA):

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "tu_correo@gmail.com"
EMAIL_HOST_PASSWORD = "tu_app_password"
DEFAULT_FROM_EMAIL = "Realidad Alterada <tu_correo@gmail.com>"
```

## Notas importantes

- Si el usuario inicia sesión con Google, el email normalmente ya viene verificado por Google. `allauth` puede marcarlo como verificado automáticamente y **puede que no envíe** un correo de confirmación adicional.
- Si quieres **enviar un correo sí o sí** (bienvenida/confirmación propia), lo ideal es enviar un email propio al crear el usuario (por señal `user_signed_up` de allauth o una señal post-save).
