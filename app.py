"""
Entradas Mestalla - versión Flask de la tienda WordPress/WooCommerce.

Sigue la estructura vista en el seminario de Flask:
  - app.py      -> controlador (rutas con @app.route)
  - db.py       -> modelo (base de datos SQLite)
  - templates/  -> vistas (plantillas Jinja2)
  - static/     -> hojas de estilo e imágenes
"""
from functools import wraps

from flask import Flask
from flask import request
from flask import render_template
from flask import redirect
from flask import url_for
from flask import session
from flask import flash
from flask import abort
from flask import g
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_connection, init_db

# Creamos una instancia de Flask
app = Flask(__name__)

# Clave necesaria para usar sesiones (carrito y login). En producción debe
# cambiarse por un valor secreto y aleatorio.
app.secret_key = 'cambia-esta-clave-en-produccion'

SITIO = {
    'nombre': 'VALENCIA C.F.',
    'descripcion': 'Vive el fútbol en Mestalla',
    'whatsapp': '34600000000',
    'whatsapp_mensaje': 'Hola, tengo una consulta sobre entradas para Mestalla.',
}

# Métodos de envío configurados en WooCommerce (zonas "España peninsular" y
# "Baleares y Canarias").
ENVIOS = {
    'correos': {'nombre': 'Correos – Paq Estándar (3-5 días)', 'peninsula': 4.95, 'islas': 9.95},
    'seur': {'nombre': 'SEUR 24h', 'peninsula': 7.95, 'islas': 14.95},
    'mrw': {'nombre': 'MRW Urgente', 'peninsula': 8.50, 'islas': 15.50},
    'gratis': {'nombre': 'Envío gratuito (pedidos de 100 € o más)', 'peninsula': 0, 'islas': 0, 'minimo': 100},
    'taquilla': {'nombre': 'Recogida local – Taquillas de Mestalla', 'peninsula': 0, 'islas': 0},
    'email': {'nombre': 'Entrada electrónica por email', 'peninsula': 0, 'islas': 0},
}

# Métodos de pago configurados en WooCommerce (BACS renombrado a Bizum y COD
# renombrado a pago en taquilla).
PAGOS = {
    'bizum': {
        'nombre': 'Bizum',
        'descripcion': 'Paga cómodamente con Bizum.',
        'instrucciones': 'Envía el importe por Bizum al 600 000 000 indicando tu número de pedido. '
                         'Tu pedido se confirmará al recibir el pago.',
    },
    'taquilla': {
        'nombre': 'Pago en taquilla',
        'descripcion': 'Paga en efectivo o con tarjeta al recoger tus entradas en las taquillas de Mestalla.',
        'instrucciones': 'Recoge y paga tus entradas en las taquillas del estadio presentando tu número de pedido.',
    },
}

PROVINCIAS_ISLAS = ['Baleares', 'Las Palmas', 'Santa Cruz de Tenerife']
PROVINCIAS = sorted([
    'A Coruña', 'Álava', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Ávila', 'Badajoz', 'Barcelona',
    'Burgos', 'Cáceres', 'Cádiz', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Córdoba', 'Cuenca',
    'Girona', 'Granada', 'Guadalajara', 'Gipuzkoa', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'León',
    'Lleida', 'Lugo', 'Madrid', 'Málaga', 'Melilla', 'Murcia', 'Navarra', 'Ourense', 'Palencia',
    'Pontevedra', 'Salamanca', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo',
    'Valencia', 'Valladolid', 'Bizkaia', 'Zamora', 'Zaragoza'] + PROVINCIAS_ISLAS)

PARTIDOS_CONTACTO = ['Jornada 12 – Liga', 'Jornada 14 – Liga', 'Jornada 16 – Liga',
                     'Octavos Copa del Rey', 'Tour del estadio', 'Otro']

ROLES_GESTION = ('administrador', 'gestor')


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def get_db():
    """Abre una conexión por petición y la guarda en g."""
    if 'db' not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def cerrar_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.template_filter('euros')
def euros(valor):
    """Formatea un número como precio: 1234.5 -> 1.234,50 €"""
    texto = f'{valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{texto} €'


def usuario_actual():
    if 'usuario_id' not in session:
        return None
    return get_db().execute('SELECT * FROM usuarios WHERE id = ?', (session['usuario_id'],)).fetchone()


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            flash('Tienes que acceder a tu cuenta para continuar.', 'error')
            return redirect(url_for('mi_cuenta'))
        return vista(*args, **kwargs)
    return envoltura


def gestion_requerida(vista):
    """Solo administradores y gestores de la tienda (shop_manager en WooCommerce)."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        usuario = usuario_actual()
        if usuario is None or usuario['rol'] not in ROLES_GESTION:
            abort(403)
        return vista(*args, **kwargs)
    return envoltura


def consulta_productos(where='', params=()):
    """Productos con su categoría, rango de precios y valoración media."""
    sql = f"""
        SELECT p.*, c.nombre AS categoria, c.slug AS categoria_slug,
               COALESCE(p.precio, (SELECT MIN(precio) FROM variaciones v WHERE v.producto_id = p.id)) AS precio_min,
               COALESCE(p.precio, (SELECT MAX(precio) FROM variaciones v WHERE v.producto_id = p.id)) AS precio_max,
               (SELECT AVG(valoracion) FROM resenas r WHERE r.producto_id = p.id) AS valoracion,
               (SELECT COUNT(*) FROM resenas r WHERE r.producto_id = p.id) AS num_resenas
        FROM productos p JOIN categorias c ON c.id = p.categoria_id
        {where}
        ORDER BY p.id
    """
    return get_db().execute(sql, params).fetchall()


def obtener_resenas(limite=None):
    sql = """SELECT r.*, p.nombre AS producto, p.slug AS producto_slug, p.imagen
             FROM resenas r JOIN productos p ON p.id = r.producto_id
             ORDER BY r.fecha DESC"""
    if limite:
        sql += f' LIMIT {int(limite)}'
    return get_db().execute(sql).fetchall()


# ---------------------------------------------------------------------------
# Carrito (se guarda en la sesión: {"producto_id" o "producto_id-variacion_id": cantidad})
# ---------------------------------------------------------------------------
def obtener_carrito():
    db = get_db()
    lineas, subtotal = [], 0
    for clave, cantidad in session.get('carrito', {}).items():
        prod_id, _, var_id = clave.partition('-')
        producto = db.execute('SELECT * FROM productos WHERE id = ?', (prod_id,)).fetchone()
        if producto is None:
            continue
        nombre, precio, stock, variacion = producto['nombre'], producto['precio'], producto['stock'], None
        if var_id:
            variacion = db.execute('SELECT * FROM variaciones WHERE id = ? AND producto_id = ?',
                                   (var_id, prod_id)).fetchone()
            if variacion is None:
                continue
            nombre = f"{producto['nombre']} - {variacion['zona']}"
            precio, stock = variacion['precio'], variacion['stock']
        total = precio * cantidad
        subtotal += total
        lineas.append({'clave': clave, 'producto': producto, 'variacion': variacion, 'nombre': nombre,
                       'precio': precio, 'cantidad': cantidad, 'total': total, 'stock': stock})
    return lineas, subtotal


@app.context_processor
def contexto_global():
    """Variables disponibles en todas las plantillas."""
    return {
        'sitio': SITIO,
        'usuario': usuario_actual(),
        'num_carrito': sum(session.get('carrito', {}).values()),
        'roles_gestion': ROLES_GESTION,
    }


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    destacados = consulta_productos('WHERE p.destacado = 1')[:4]
    return render_template('index.html', productos=destacados, resenas=obtener_resenas(10))


@app.route('/entradas/')
def entradas():
    db = get_db()
    secciones = []
    for categoria in db.execute('SELECT * FROM categorias ORDER BY id').fetchall():
        secciones.append((categoria, consulta_productos('WHERE c.id = ?', (categoria['id'],))))
    return render_template('entradas.html', secciones=secciones)


@app.route('/tienda/')
def tienda():
    orden = request.args.get('orden', 'defecto')
    productos = list(consulta_productos())
    if orden == 'precio':
        productos.sort(key=lambda p: p['precio_min'])
    elif orden == 'precio-desc':
        productos.sort(key=lambda p: p['precio_max'], reverse=True)
    elif orden == 'valoracion':
        productos.sort(key=lambda p: p['valoracion'] or 0, reverse=True)
    return render_template('tienda.html', productos=productos, orden=orden,
                           categorias=get_db().execute('SELECT * FROM categorias').fetchall())


@app.route('/categoria/<string:slug>/')
def categoria(slug):
    cat = get_db().execute('SELECT * FROM categorias WHERE slug = ?', (slug,)).fetchone()
    if cat is None:
        abort(404)
    return render_template('categoria.html', categoria=cat,
                           productos=consulta_productos('WHERE c.id = ?', (cat['id'],)))


@app.route('/producto/<string:slug>/')
def producto(slug):
    resultado = consulta_productos('WHERE p.slug = ?', (slug,))
    if not resultado:
        abort(404)
    prod = resultado[0]
    db = get_db()
    variaciones = db.execute('SELECT * FROM variaciones WHERE producto_id = ? ORDER BY precio DESC',
                             (prod['id'],)).fetchall()
    resenas = db.execute('SELECT * FROM resenas WHERE producto_id = ? ORDER BY fecha DESC',
                         (prod['id'],)).fetchall()
    relacionados = consulta_productos('WHERE c.id = ? AND p.id != ?', (prod['categoria_id'], prod['id']))[:4]
    return render_template('producto.html', producto=prod, variaciones=variaciones,
                           resenas=resenas, relacionados=relacionados)


@app.route('/producto/<string:slug>/resena', methods=['POST'])
@login_requerido
def nueva_resena(slug):
    prod = get_db().execute('SELECT id FROM productos WHERE slug = ?', (slug,)).fetchone()
    if prod is None:
        abort(404)
    valoracion = request.form.get('valoracion', type=int)
    comentario = request.form.get('comentario', '').strip()
    # En WooCommerce la valoración es obligatoria (woocommerce_review_rating_required = yes)
    if not valoracion or not 1 <= valoracion <= 5 or not comentario:
        flash('Selecciona una valoración y escribe tu opinión.', 'error')
    else:
        usuario = usuario_actual()
        db = get_db()
        db.execute('INSERT INTO resenas (producto_id, usuario_id, autor, valoracion, comentario) '
                   'VALUES (?, ?, ?, ?, ?)', (prod['id'], usuario['id'], usuario['nombre'], valoracion, comentario))
        db.commit()
        flash('¡Gracias por tu valoración!', 'ok')
    return redirect(url_for('producto', slug=slug) + '#resenas')


@app.route('/estadio/')
def estadio():
    return render_template('estadio.html')


@app.route('/opiniones/')
def opiniones():
    return render_template('opiniones.html', resenas=obtener_resenas())


@app.route('/contacto/', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        # Obtenemos los parámetros del formulario (equivalente a Contact Form 7)
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip()
        partido = request.form.get('partido', '')
        mensaje = request.form.get('mensaje', '').strip()
        if not nombre or not email:
            flash('Uno o más campos tienen un error. Por favor, revísalos e inténtalo de nuevo.', 'error')
            return render_template('contacto.html', partidos=PARTIDOS_CONTACTO, datos=request.form)
        db = get_db()
        db.execute('INSERT INTO mensajes (nombre, email, partido, mensaje) VALUES (?, ?, ?, ?)',
                   (nombre, email, partido, mensaje))
        db.commit()
        flash('Gracias por tu mensaje. Ha sido enviado.', 'ok')
        return redirect(url_for('contacto'))
    return render_template('contacto.html', partidos=PARTIDOS_CONTACTO, datos={})


@app.route('/aviso-legal/')
def aviso_legal():
    return render_template('aviso_legal.html')


@app.route('/politica-de-privacidad/')
def politica_privacidad():
    return render_template('politica_privacidad.html')


# ---------------------------------------------------------------------------
# Carrito y compra
# ---------------------------------------------------------------------------
@app.route('/carrito/')
def carrito():
    lineas, subtotal = obtener_carrito()
    return render_template('carrito.html', lineas=lineas, subtotal=subtotal)


@app.route('/carrito/anadir', methods=['POST'])
def carrito_anadir():
    db = get_db()
    prod_id = request.form.get('producto_id', type=int)
    var_id = request.form.get('variacion_id', type=int)
    cantidad = max(1, request.form.get('cantidad', 1, type=int))
    producto = db.execute('SELECT * FROM productos WHERE id = ?', (prod_id,)).fetchone()
    if producto is None:
        abort(404)

    if producto['tipo'] == 'variable':
        variacion = db.execute('SELECT * FROM variaciones WHERE id = ? AND producto_id = ?',
                               (var_id, prod_id)).fetchone()
        if variacion is None:
            flash('Elige una zona antes de añadir la entrada al carrito.', 'error')
            return redirect(url_for('producto', slug=producto['slug']))
        clave, stock, nombre = f'{prod_id}-{var_id}', variacion['stock'], f"{producto['nombre']} - {variacion['zona']}"
    else:
        clave, stock, nombre = str(prod_id), producto['stock'], producto['nombre']

    carrito = session.get('carrito', {})
    nueva_cantidad = carrito.get(clave, 0) + cantidad
    if stock is not None and nueva_cantidad > stock:
        flash(f'No hay suficientes unidades de «{nombre}». Disponibles: {stock}.', 'error')
        return redirect(request.referrer or url_for('tienda'))
    carrito[clave] = nueva_cantidad
    session['carrito'] = carrito
    flash(f'«{nombre}» se ha añadido a tu carrito.', 'ok')
    return redirect(request.referrer or url_for('carrito'))


@app.route('/carrito/actualizar', methods=['POST'])
def carrito_actualizar():
    carrito = session.get('carrito', {})
    for clave in list(carrito):
        cantidad = request.form.get(f'cantidad_{clave}', type=int)
        if cantidad is None:
            continue
        if cantidad <= 0:
            carrito.pop(clave)
        else:
            carrito[clave] = cantidad
    session['carrito'] = carrito
    flash('Carrito actualizado.', 'ok')
    return redirect(url_for('carrito'))


@app.route('/carrito/eliminar/<string:clave>', methods=['POST'])
def carrito_eliminar(clave):
    carrito = session.get('carrito', {})
    carrito.pop(clave, None)
    session['carrito'] = carrito
    return redirect(url_for('carrito'))


def calcular_envio(metodo, provincia, subtotal):
    """Devuelve el coste del envío o None si el método no está disponible."""
    envio = ENVIOS.get(metodo)
    if envio is None:
        return None
    if subtotal < envio.get('minimo', 0):
        return None
    return envio['islas'] if provincia in PROVINCIAS_ISLAS else envio['peninsula']


@app.route('/finalizar-compra/', methods=['GET', 'POST'])
def finalizar_compra():
    lineas, subtotal = obtener_carrito()
    if not lineas:
        flash('Tu carrito está vacío.', 'error')
        return redirect(url_for('carrito'))

    usuario = usuario_actual()
    datos = dict(request.form) if request.method == 'POST' else {
        'nombre': usuario['nombre'] if usuario else '',
        'email': usuario['email'] if usuario else '',
        'provincia': 'Valencia',
        'envio': 'email',
        'pago': 'bizum',
    }

    if request.method == 'POST':
        errores = []
        for campo, etiqueta in [('nombre', 'Nombre'), ('email', 'Email'), ('provincia', 'Provincia')]:
            if not datos.get(campo, '').strip():
                errores.append(f'El campo «{etiqueta}» es obligatorio.')
        metodo_envio = datos.get('envio')
        coste_envio = calcular_envio(metodo_envio, datos.get('provincia'), subtotal)
        if coste_envio is None:
            errores.append('El método de envío seleccionado no está disponible.')
        if metodo_envio in ('correos', 'seur', 'mrw', 'gratis') and not datos.get('direccion', '').strip():
            errores.append('Indica una dirección para el envío a domicilio.')
        if datos.get('pago') not in PAGOS:
            errores.append('Selecciona un método de pago.')
        for linea in lineas:
            if linea['stock'] is not None and linea['cantidad'] > linea['stock']:
                errores.append(f"No hay suficientes unidades de «{linea['nombre']}».")

        if not errores:
            db = get_db()
            cursor = db.execute(
                'INSERT INTO pedidos (usuario_id, nombre, email, telefono, direccion, ciudad, cp, provincia, '
                'envio, coste_envio, pago, subtotal, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (usuario['id'] if usuario else None, datos['nombre'].strip(), datos['email'].strip(),
                 datos.get('telefono', ''), datos.get('direccion', ''), datos.get('ciudad', ''),
                 datos.get('cp', ''), datos['provincia'], ENVIOS[metodo_envio]['nombre'], coste_envio,
                 PAGOS[datos['pago']]['nombre'], subtotal, subtotal + coste_envio))
            pedido_id = cursor.lastrowid
            for linea in lineas:
                var_id = linea['variacion']['id'] if linea['variacion'] else None
                db.execute('INSERT INTO lineas_pedido (pedido_id, producto_id, variacion_id, nombre, cantidad, precio) '
                           'VALUES (?, ?, ?, ?, ?, ?)',
                           (pedido_id, linea['producto']['id'], var_id, linea['nombre'],
                            linea['cantidad'], linea['precio']))
                # Reducimos el inventario igual que hacía WooCommerce
                if var_id and linea['stock'] is not None:
                    db.execute('UPDATE variaciones SET stock = stock - ? WHERE id = ?', (linea['cantidad'], var_id))
                elif linea['stock'] is not None:
                    db.execute('UPDATE productos SET stock = stock - ? WHERE id = ?',
                               (linea['cantidad'], linea['producto']['id']))
            db.commit()
            session.pop('carrito', None)
            session.setdefault('pedidos', [])
            session['pedidos'] = session['pedidos'] + [pedido_id]
            return redirect(url_for('pedido_recibido', pedido_id=pedido_id))

        for error in errores:
            flash(error, 'error')

    return render_template('finalizar_compra.html', lineas=lineas, subtotal=subtotal, datos=datos,
                           envios=ENVIOS, pagos=PAGOS, provincias=PROVINCIAS, islas=PROVINCIAS_ISLAS)


@app.route('/pedido/<int:pedido_id>/')
def pedido_recibido(pedido_id):
    db = get_db()
    pedido = db.execute('SELECT * FROM pedidos WHERE id = ?', (pedido_id,)).fetchone()
    if pedido is None:
        abort(404)
    usuario = usuario_actual()
    es_suyo = pedido_id in session.get('pedidos', []) or (usuario and pedido['usuario_id'] == usuario['id'])
    if not es_suyo and not (usuario and usuario['rol'] in ROLES_GESTION):
        abort(403)
    lineas = db.execute('SELECT * FROM lineas_pedido WHERE pedido_id = ?', (pedido_id,)).fetchall()
    pago = next((p for p in PAGOS.values() if p['nombre'] == pedido['pago']), None)
    return render_template('pedido.html', pedido=pedido, lineas=lineas, pago=pago)


# ---------------------------------------------------------------------------
# Mi cuenta (acceso, registro y pedidos)
# ---------------------------------------------------------------------------
@app.route('/mi-cuenta/')
def mi_cuenta():
    usuario = usuario_actual()
    if usuario is None:
        return render_template('acceso.html')
    pedidos = get_db().execute('SELECT * FROM pedidos WHERE usuario_id = ? ORDER BY fecha DESC',
                               (usuario['id'],)).fetchall()
    return render_template('mi_cuenta.html', pedidos=pedidos)


@app.route('/mi-cuenta/acceder', methods=['POST'])
def acceder():
    identificador = request.form.get('usuario', '').strip()
    password = request.form.get('password', '')
    usuario = get_db().execute('SELECT * FROM usuarios WHERE usuario = ? OR email = ?',
                               (identificador, identificador)).fetchone()
    if usuario is None or not check_password_hash(usuario['password_hash'], password):
        flash('Usuario o contraseña incorrectos.', 'error')
        return redirect(url_for('mi_cuenta'))
    session['usuario_id'] = usuario['id']
    flash(f"Hola, {usuario['nombre']}.", 'ok')
    return redirect(request.form.get('siguiente') or url_for('mi_cuenta'))


@app.route('/mi-cuenta/registro', methods=['POST'])
def registro():
    usuario = request.form.get('usuario', '').strip()
    email = request.form.get('email', '').strip().lower()
    nombre = request.form.get('nombre', '').strip() or usuario
    password = request.form.get('password', '')
    if not usuario or not email or len(password) < 6:
        flash('Rellena todos los campos. La contraseña debe tener al menos 6 caracteres.', 'error')
        return redirect(url_for('mi_cuenta'))
    db = get_db()
    if db.execute('SELECT 1 FROM usuarios WHERE usuario = ? OR email = ?', (usuario, email)).fetchone():
        flash('Ya existe una cuenta con ese nombre de usuario o email.', 'error')
        return redirect(url_for('mi_cuenta'))
    cursor = db.execute('INSERT INTO usuarios (usuario, email, nombre, password_hash, rol) VALUES (?, ?, ?, ?, ?)',
                        (usuario, email, nombre, generate_password_hash(password), 'cliente'))
    db.commit()
    session['usuario_id'] = cursor.lastrowid
    flash('Tu cuenta se ha creado correctamente.', 'ok')
    return redirect(url_for('mi_cuenta'))


@app.route('/mi-cuenta/salir')
def salir():
    session.pop('usuario_id', None)
    flash('Has cerrado sesión.', 'ok')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Panel de gestión (administrador y gestor de la tienda)
# ---------------------------------------------------------------------------
@app.route('/gestion/')
@gestion_requerida
def gestion():
    db = get_db()
    return render_template(
        'gestion.html',
        pedidos=db.execute('SELECT * FROM pedidos ORDER BY fecha DESC').fetchall(),
        mensajes=db.execute('SELECT * FROM mensajes ORDER BY fecha DESC').fetchall(),
        productos=consulta_productos(),
        variaciones=db.execute('SELECT v.*, p.nombre AS producto FROM variaciones v '
                               'JOIN productos p ON p.id = v.producto_id').fetchall(),
        usuarios=db.execute('SELECT * FROM usuarios ORDER BY id').fetchall(),
        estados=['Pendiente de pago', 'En espera', 'Procesando', 'Completado', 'Cancelado'],
    )


@app.route('/gestion/pedido/<int:pedido_id>', methods=['POST'])
@gestion_requerida
def gestion_pedido(pedido_id):
    db = get_db()
    db.execute('UPDATE pedidos SET estado = ? WHERE id = ?', (request.form['estado'], pedido_id))
    db.commit()
    flash(f'Pedido #{pedido_id} actualizado.', 'ok')
    return redirect(url_for('gestion') + '#pedidos')


@app.route('/gestion/producto/<int:producto_id>', methods=['POST'])
@gestion_requerida
def gestion_producto(producto_id):
    db = get_db()
    precio = request.form.get('precio', type=float)
    stock = request.form.get('stock', type=int)
    destacado = 1 if request.form.get('destacado') else 0
    if request.form.get('variacion'):
        db.execute('UPDATE variaciones SET precio = ?, stock = ? WHERE id = ?', (precio, stock, producto_id))
    else:
        db.execute('UPDATE productos SET precio = COALESCE(?, precio), stock = ?, destacado = ? WHERE id = ?',
                   (precio, stock, destacado, producto_id))
    db.commit()
    flash('Producto actualizado.', 'ok')
    return redirect(url_for('gestion') + '#productos')


# ---------------------------------------------------------------------------
# Gestión de errores
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template('error.html', codigo=404,
                           mensaje='La página que buscas no existe.'), 404


@app.errorhandler(403)
def acceso_prohibido(error):
    return render_template('error.html', codigo=403,
                           mensaje='No tienes permiso para acceder a esta página.'), 403


# Creamos la base de datos (si no existe) al arrancar la aplicación
with app.app_context():
    init_db()

# Programa principal
if __name__ == '__main__':
    app.run(debug=True)
