"""
Modelo de datos (la "M" del patrón MVC).

Aquí se crea la base de datos SQLite y se cargan los datos que tenía la tienda
WordPress/WooCommerce original (sacados del backup de la base de datos):
categorías, productos, variaciones por zona, usuarios y la reseña existente.
"""
import os
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mestalla.db')

# Contraseña de demostración para los usuarios migrados. WordPress guarda las
# contraseñas cifradas con su propio algoritmo y no se pueden recuperar.
PASSWORD_DEMO = 'mestalla2026'

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario       TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    nombre        TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    rol           TEXT NOT NULL DEFAULT 'cliente'   -- administrador | gestor | cliente
);

CREATE TABLE IF NOT EXISTS categorias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS productos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL,
    slug              TEXT UNIQUE NOT NULL,
    descripcion       TEXT,
    descripcion_corta TEXT,
    precio            REAL,                 -- NULL en productos variables
    stock             INTEGER,              -- NULL = sin gestión de inventario
    imagen            TEXT,
    categoria_id      INTEGER REFERENCES categorias(id),
    destacado         INTEGER DEFAULT 0,
    tipo              TEXT DEFAULT 'simple' -- simple | variable
);

CREATE TABLE IF NOT EXISTS variaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER REFERENCES productos(id),
    zona        TEXT NOT NULL,
    precio      REAL NOT NULL,
    stock       INTEGER
);

CREATE TABLE IF NOT EXISTS resenas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER REFERENCES productos(id),
    usuario_id  INTEGER REFERENCES usuarios(id),
    autor       TEXT NOT NULL,
    valoracion  INTEGER NOT NULL CHECK (valoracion BETWEEN 1 AND 5),
    comentario  TEXT NOT NULL,
    fecha       TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS pedidos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER REFERENCES usuarios(id),
    nombre      TEXT NOT NULL,
    email       TEXT NOT NULL,
    telefono    TEXT,
    direccion   TEXT,
    ciudad      TEXT,
    cp          TEXT,
    provincia   TEXT,
    envio       TEXT NOT NULL,
    coste_envio REAL NOT NULL,
    pago        TEXT NOT NULL,
    subtotal    REAL NOT NULL,
    total       REAL NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'En espera',
    fecha       TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS lineas_pedido (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id    INTEGER REFERENCES pedidos(id),
    producto_id  INTEGER REFERENCES productos(id),
    variacion_id INTEGER REFERENCES variaciones(id),
    nombre       TEXT NOT NULL,
    cantidad     INTEGER NOT NULL,
    precio       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS mensajes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL,
    email   TEXT NOT NULL,
    partido TEXT,
    mensaje TEXT,
    fecha   TEXT DEFAULT (datetime('now', 'localtime'))
);
"""

# ---------------------------------------------------------------------------
# Datos migrados desde WordPress (tablas wp_terms, wp_posts, wp_postmeta...)
# ---------------------------------------------------------------------------
CATEGORIAS = [
    # (nombre, slug, descripción)
    ('Liga', 'liga', 'Entradas para los partidos de liga en Mestalla.'),
    ('Copa del Rey', 'copa-del-rey', 'Entradas para las eliminatorias de Copa del Rey.'),
    ('Abonos', 'abonos', 'Abonos de temporada y medios abonos.'),
    ('Tour del estadio', 'tour-del-estadio', 'Visitas guiadas por el estadio de Mestalla.'),
    ('Merchandising', 'merchandising', 'Productos oficiales de la tienda.'),
]

PRODUCTOS = [
    # (nombre, slug, descripción, descripción corta, precio, stock, imagen, categoría, destacado, tipo)
    ('Entrada Tribuna Central – Jornada 12', 'entrada-tribuna-central-jornada-12',
     'Asiento numerado en Tribuna Central con la mejor vista del campo.',
     'Asiento numerado en Tribuna Central con la mejor vista del campo.',
     85, 200, 'grada-de-la-mar.jpg', 'liga', 1, 'simple'),
    ('Entrada Grada Gol Norte – Jornada 12', 'entrada-grada-gol-norte-jornada-12',
     'Vive el partido desde la grada más animada del estadio.',
     'Vive el partido desde la grada más animada del estadio.',
     45, 196, 'mestalla-2.jpg', 'liga', 1, 'simple'),
    ('Entrada Anfiteatro – Jornada 14', 'entrada-anfiteatro-jornada-14',
     'Vista panorámica de todo el terreno de juego desde el anfiteatro.',
     'Vista panorámica de todo el terreno de juego desde el anfiteatro.',
     35, 200, 'mestalla-27.jpg', 'liga', 0, 'simple'),
    ('Entrada Tribuna – Octavos de final Copa del Rey', 'entrada-tribuna-octavos-de-final-copa-del-rey',
     'Partido de octavos de final de la Copa del Rey en Mestalla.',
     'Partido de octavos de final de la Copa del Rey en Mestalla.',
     60, 200, 'mestalla-4.jpg', 'copa-del-rey', 1, 'simple'),
    ('Medio abono temporada', 'medio-abono-temporada',
     'Acceso a la mitad de los partidos de liga de la temporada en tu asiento fijo.',
     'Acceso a la mitad de los partidos de liga de la temporada en tu asiento fijo.',
     290, 200, 'mestalla-5.jpg', 'abonos', 0, 'simple'),
    ('Visita guiada Mestalla – Adulto', 'visita-guiada-mestalla-adulto',
     'Recorrido por vestuarios, banquillo, túnel de vestuarios y sala de prensa. Duración 75 min.',
     'Recorrido por vestuarios, banquillo, túnel de vestuarios y sala de prensa. Duración 75 min.',
     15, 200, 'mestalla-6.jpg', 'tour-del-estadio', 0, 'simple'),
    ('Visita guiada Mestalla – Infantil', 'visita-guiada-mestalla-infantil',
     'Tour para menores de 14 años acompañados de un adulto.',
     'Tour para menores de 14 años acompañados de un adulto.',
     9, 200, 'mestalla-7.jpg', 'tour-del-estadio', 0, 'simple'),
    ('Bufanda blanquinegra', 'bufanda-blanquinegra',
     'Bufanda de punto en blanco y negro, 140 x 20 cm.',
     'Bufanda de punto en blanco y negro, 140 x 20 cm.',
     18, 49, 'grada-de-la-mar-2.jpg', 'merchandising', 0, 'simple'),
    ('Entrada Jornada 16 – Elige tu zona', 'entrada-jornada-16-elige-tu-zona',
     'Entrada para el partido de liga de la jornada 16 en Mestalla. Selecciona tu zona: '
     'Tribuna, Preferencia, Gol o Anfiteatro.',
     'Elige la zona del estadio que prefieras para el partido de la jornada 16.',
     None, None, 'mestalla-3.jpg', 'liga', 1, 'variable'),
]

# Variaciones del producto variable (atributo pa_zona)
VARIACIONES = [
    ('entrada-jornada-16-elige-tu-zona', 'Tribuna', 80, 100),
    ('entrada-jornada-16-elige-tu-zona', 'Preferencia', 65, 100),
    ('entrada-jornada-16-elige-tu-zona', 'Gol', 40, 100),
    ('entrada-jornada-16-elige-tu-zona', 'Anfiteatro', 30, 100),
]

USUARIOS = [
    # (usuario, email, nombre, rol)
    ('Youssef', 'yououaapa@alu.edu.gva.es', 'Youssef', 'administrador'),
    ('Youssef1', 'youssef1@entradasmestalla.com', 'Youssef Administrador', 'administrador'),
    ('Youssef2', 'youssef2@entradasmestalla.com', 'Youssef Gestor', 'gestor'),
    ('Youssef3', 'youssef3@entradasmestalla.com', 'Youssef Cliente', 'cliente'),
]

RESENAS = [
    # (slug producto, usuario, valoración, comentario, fecha)
    ('entrada-anfiteatro-jornada-14', 'Youssef3', 5, 'Servicio y gestión impecables', '2026-10-30 00:26:21'),
]


def get_connection():
    """Devuelve una conexión a la base de datos con acceso a columnas por nombre."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """Crea las tablas y carga los datos iniciales si la base de datos está vacía."""
    conn = get_connection()
    conn.executescript(ESQUEMA)

    if conn.execute('SELECT COUNT(*) FROM productos').fetchone()[0] == 0:
        for c in CATEGORIAS:
            conn.execute('INSERT INTO categorias (nombre, slug, descripcion) VALUES (?, ?, ?)', c)

        for (nombre, slug, desc, corta, precio, stock, img, cat, dest, tipo) in PRODUCTOS:
            cat_id = conn.execute('SELECT id FROM categorias WHERE slug = ?', (cat,)).fetchone()[0]
            conn.execute(
                'INSERT INTO productos (nombre, slug, descripcion, descripcion_corta, precio, stock, '
                'imagen, categoria_id, destacado, tipo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (nombre, slug, desc, corta, precio, stock, img, cat_id, dest, tipo))

        for (slug, zona, precio, stock) in VARIACIONES:
            prod_id = conn.execute('SELECT id FROM productos WHERE slug = ?', (slug,)).fetchone()[0]
            conn.execute('INSERT INTO variaciones (producto_id, zona, precio, stock) VALUES (?, ?, ?, ?)',
                         (prod_id, zona, precio, stock))

        for (usuario, email, nombre, rol) in USUARIOS:
            conn.execute('INSERT INTO usuarios (usuario, email, nombre, password_hash, rol) '
                         'VALUES (?, ?, ?, ?, ?)',
                         (usuario, email, nombre, generate_password_hash(PASSWORD_DEMO), rol))

        for (slug, usuario, val, comentario, fecha) in RESENAS:
            prod_id = conn.execute('SELECT id FROM productos WHERE slug = ?', (slug,)).fetchone()[0]
            user = conn.execute('SELECT id, nombre FROM usuarios WHERE usuario = ?', (usuario,)).fetchone()
            conn.execute('INSERT INTO resenas (producto_id, usuario_id, autor, valoracion, comentario, fecha) '
                         'VALUES (?, ?, ?, ?, ?, ?)', (prod_id, user['id'], user['nombre'], val, comentario, fecha))

        conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print(f'Base de datos creada en {DATABASE}')
