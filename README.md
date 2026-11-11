# Entradas Mestalla – Flask

Migración a [Flask](https://flask.palletsprojects.com/) de la tienda WordPress + WooCommerce
[entradas-mestalla-wordpress](https://github.com/youachi/entradas-mestalla-wordpress), siguiendo la
estructura del [seminario de Flask](https://github.com/josejuansanchez/seminario-flask).

Los contenidos (páginas, productos, precios, stock, categorías, variaciones, usuarios, reseñas,
métodos de envío y de pago, colores del tema) se han sacado del **backup de la base de datos de
WordPress** (`backup_...-db.gz`) y de las imágenes de `uploads.zip`.

## Estructura (patrón MVC)

```
entradas-mestalla-flask/
├── app.py              # Controlador: rutas (@app.route), formularios, sesiones, errores
├── db.py               # Modelo: esquema SQLite + datos migrados de WordPress
├── requirements.txt
├── templates/          # Vistas: plantillas Jinja2
│   ├── base.html       # Cabecera, menú, pie y botón de WhatsApp (herencia de plantillas)
│   ├── _macros.html    # Tarjeta de producto, estrellas, reseñas, mapa
│   ├── index.html, entradas.html, tienda.html, categoria.html, producto.html
│   ├── estadio.html, opiniones.html, contacto.html, aviso_legal.html, politica_privacidad.html
│   ├── carrito.html, finalizar_compra.html, pedido.html
│   ├── acceso.html, mi_cuenta.html, gestion.html, error.html
└── static/
    ├── css/styles.css  # Colores blanco, negro y naranja (#EE7814) del tema
    └── img/            # Imágenes originales de wp-content/uploads
```

## Instalación y ejecución

**Linux y macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

**Windows**

```bash
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py app.py
```

En Windows también puedes hacer doble clic en `run.bat`: crea el entorno, instala Flask y arranca la web.

Abre `http://localhost:5000`. La base de datos `mestalla.db` se crea automáticamente la primera
vez (para empezar de cero basta con borrar ese archivo).

## Usuarios

WordPress guarda las contraseñas con su propio cifrado y no se pueden recuperar, así que los
usuarios migrados usan la contraseña de prueba **`mestalla2026`**:

| Usuario  | Rol en WordPress   | Rol en Flask  | Qué puede hacer |
|----------|--------------------|---------------|-----------------|
| Youssef  | Administrador      | administrador | Panel de gestión completo (cuenta con la que se instaló WordPress) |
| Youssef1 | Administrador      | administrador | Panel de gestión completo (pedidos, productos, mensajes, usuarios) |
| Youssef2 | Gestor de la tienda| gestor        | Panel de gestión sin la lista de usuarios |
| Youssef3 | Cliente            | cliente       | Comprar, ver sus pedidos, valorar productos |

Cualquiera puede registrarse desde **Mi cuenta** (se crea como cliente).

## Equivalencias WordPress → Flask

| WordPress / plugin | Flask |
|---|---|
| Páginas Inicio, Entradas, Estadio, Opiniones, Contacto, Aviso legal, Política de privacidad | Una ruta y una plantilla por página |
| WooCommerce: productos, categorías (`product_cat`) | Tablas `productos` y `categorias`, rutas `/tienda/`, `/categoria/<slug>/`, `/producto/<slug>/` |
| Producto variable “Elige tu zona” (`pa_zona`) | Tabla `variaciones` + selector de zona |
| Carrito y finalizar compra | Carrito en `session`, rutas `/carrito/` y `/finalizar-compra/` |
| Zonas de envío (España peninsular / Baleares y Canarias): Correos, SEUR, MRW, envío gratis ≥ 100 €, recogida en taquilla, entrada por email | Diccionario `ENVIOS` y función `calcular_envio()` |
| Pagos: Bizum (BACS) y Pago en taquilla (COD) | Diccionario `PAGOS` |
| Control de inventario | Se descuenta el stock al hacer el pedido |
| Reseñas con estrellas (valoración obligatoria) | Tabla `resenas`, formulario en cada producto (requiere login) |
| Mi cuenta (acceso y registro) | `/mi-cuenta/` con `werkzeug.security` para las contraseñas |
| Roles administrator / shop_manager / customer | Campo `rol` + decorador `gestion_requerida` que hace `abort(403)` |
| Contact Form 7 | Formulario `POST` en `/contacto/`; los mensajes se guardan en la tabla `mensajes` |
| Joinchat (WhatsApp) | Botón flotante que abre `wa.me` |
| Google Maps embebido | Mismo `iframe` en Estadio y Contacto |
| Escritorio de WordPress (pedidos, productos) | `/gestion/`: cambiar estado de pedidos, precio, stock y destacados |
| Página 404 del tema | `@app.errorhandler(404)` y `@app.errorhandler(403)` |

## Conceptos del seminario que se usan

- `@app.route` con barra final (`/entradas/`) y secciones variables (`<string:slug>`, `<int:pedido_id>`).
- Métodos `GET` y `POST` con `request.form` y `request.args`.
- `redirect()`, `url_for()`, `abort()` y `@app.errorhandler`.
- Plantillas Jinja2 con herencia (`{% extends %}`), bloques, macros, bucles, condicionales y filtros propios (`euros`).
- Archivos estáticos con `url_for('static', ...)`.
- Además: `session` para el carrito y el login, `flash()` para los avisos y SQLite (`sqlite3`, incluido en Python).

## Producción

Cambia `app.secret_key` en `app.py` por un valor aleatorio y usa un servidor WSGI como Gunicorn:

```bash
pip install gunicorn
gunicorn app:app
```
