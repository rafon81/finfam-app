import sqlite3
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import uuid
import json

DB_FILE = "database.db"

def get_db_connection():
    """Crea y retorna una conexión a la base de datos."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Crea las tablas de la base de datos con modelo relacional mejorado."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        tutorial_completed BOOLEAN DEFAULT 0
    )""")

    # Tabla de Categorías
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('Ingreso', 'Gasto')),
        icon TEXT,
        color TEXT,
        user_username TEXT,
        is_default BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_username) REFERENCES users (username),
        UNIQUE(name, user_username)
    )""")

    # Tabla de Métodos de Pago
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT CHECK(type IN ('Efectivo', 'Tarjeta Débito', 'Tarjeta Crédito', 'Transferencia', 'Billetera Digital')),
        user_username TEXT,
        is_default BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_username) REFERENCES users (username),
        UNIQUE(name, user_username)
    )""")

    # Tabla de Grupos (para gastos compartidos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expense_groups (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_by TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (created_by) REFERENCES users (username)
    )""")

    # Tabla de Miembros de Grupos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT NOT NULL,
        user_username TEXT NOT NULL,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (group_id) REFERENCES expense_groups (id),
        FOREIGN KEY (user_username) REFERENCES users (username),
        UNIQUE(group_id, user_username)
    )""")

    # Tabla de Transacciones Principal
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        user_username TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        payment_method_id INTEGER,
        date TEXT NOT NULL,
        amount REAL NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('Ingreso', 'Gasto')),
        details TEXT,
        installments_paid INTEGER DEFAULT 1,
        installments_total INTEGER DEFAULT 1,
        purchase_id TEXT,
        is_shared BOOLEAN DEFAULT 0,
        group_id TEXT,
        original_amount REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_username) REFERENCES users (username),
        FOREIGN KEY (category_id) REFERENCES categories (id),
        FOREIGN KEY (payment_method_id) REFERENCES payment_methods (id),
        FOREIGN KEY (group_id) REFERENCES expense_groups (id)
    )""")

    # Tabla de Divisiones de Gastos Compartidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expense_splits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL,
        user_username TEXT NOT NULL,
        amount REAL NOT NULL,
        percentage REAL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'cancelled')),
        paid_at TIMESTAMP,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id),
        FOREIGN KEY (user_username) REFERENCES users (username)
    )""")

    # Tabla de Presupuestos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_username TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        period TEXT DEFAULT 'monthly' CHECK(period IN ('weekly', 'monthly', 'yearly')),
        start_date TEXT,
        end_date TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_username) REFERENCES users (username),
        FOREIGN KEY (category_id) REFERENCES categories (id),
        UNIQUE(user_username, category_id, period)
    )""")

    # Tabla de Metas de Ahorro
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS savings_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_username TEXT NOT NULL,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        current_amount REAL DEFAULT 0,
        target_date TEXT,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_username) REFERENCES users (username)
    )""")

    # Tabla de Configuración de Usuario
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_username TEXT PRIMARY KEY,
        currency TEXT DEFAULT 'ARS',
        date_format TEXT DEFAULT 'DD/MM/YYYY',
        theme TEXT DEFAULT 'light',
        notifications_enabled BOOLEAN DEFAULT 1,
        budget_alerts BOOLEAN DEFAULT 1,
        settings_json TEXT,
        FOREIGN KEY (user_username) REFERENCES users (username)
    )""")

    # Tabla de Tutorial Steps
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tutorial_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_username TEXT NOT NULL,
        step_name TEXT NOT NULL,
        completed BOOLEAN DEFAULT 0,
        completed_at TIMESTAMP,
        FOREIGN KEY (user_username) REFERENCES users (username),
        UNIQUE(user_username, step_name)
    )""")

    # Crear índices para mejorar performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_username, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expense_splits_transaction ON expense_splits(transaction_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expense_splits_user ON expense_splits(user_username)")

    conn.commit()
    conn.close()

# --- Funciones para Tutorial ---

def get_tutorial_progress(username):
    """Obtiene el progreso del tutorial para un usuario."""
    conn = get_db_connection()
    query = "SELECT step_name, completed FROM tutorial_progress WHERE user_username = ?"
    try:
        df = pd.read_sql_query(query, conn, params=(username,))
        return df.set_index('step_name')['completed'].to_dict()
    finally:
        conn.close()

def update_tutorial_step(username, step_name, completed=True):
    """Actualiza el progreso de un paso del tutorial."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT OR REPLACE INTO tutorial_progress (user_username, step_name, completed, completed_at)
    VALUES (?, ?, ?, ?)
    """, (username, step_name, completed, datetime.now() if completed else None))
    
    conn.commit()
    conn.close()

# --- Funciones para Gastos Compartidos ---

def create_expense_group(name, description, created_by, members):
    """Crea un grupo para gastos compartidos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    group_id = str(uuid.uuid4())
    
    # Crear el grupo
    cursor.execute("""
    INSERT INTO expense_groups (id, name, description, created_by)
    VALUES (?, ?, ?, ?)
    """, (group_id, name, description, created_by))
    
    # Agregar miembros
    for member in members:
        cursor.execute("""
        INSERT INTO group_members (group_id, user_username)
        VALUES (?, ?)
        """, (group_id, member))
    
    conn.commit()
    conn.close()
    return group_id

def add_shared_expense(payer_username, category_name, amount, date, details, 
                      group_id, split_method, split_data, payment_method_name=None):
    """Añade un gasto compartido con sus divisiones."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener IDs necesarios
    category_id = cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,)).fetchone()[0]
    payment_method_id = None
    if payment_method_name:
        payment_method_id = cursor.execute("SELECT id FROM payment_methods WHERE name = ?", (payment_method_name,)).fetchone()
        if payment_method_id:
            payment_method_id = payment_method_id[0]
    
    # Crear la transacción principal
    transaction_id = str(uuid.uuid4())
    cursor.execute("""
    INSERT INTO transactions (id, user_username, category_id, payment_method_id, date, amount, type, details, is_shared, group_id, original_amount)
    VALUES (?, ?, ?, ?, ?, ?, 'Gasto', ?, 1, ?, ?)
    """, (transaction_id, payer_username, category_id, payment_method_id, date, amount, details, group_id, amount))
    
    # Crear las divisiones
    for username, split_amount in split_data.items():
        if username != payer_username:  # El pagador no se debe a sí mismo
            cursor.execute("""
            INSERT INTO expense_splits (transaction_id, user_username, amount, percentage, status)
            VALUES (?, ?, ?, ?, 'pending')
            """, (transaction_id, username, split_amount, (split_amount/amount)*100))
    
    conn.commit()
    conn.close()
    return transaction_id

def get_pending_splits_for_user(username):
    """Obtiene las divisiones pendientes de pago para un usuario."""
    conn = get_db_connection()
    query = """
    SELECT es.id, es.amount, es.percentage, t.details, t.date, 
           u.name as payer_name, c.name as category, eg.name as group_name
    FROM expense_splits es
    JOIN transactions t ON es.transaction_id = t.id
    JOIN users u ON t.user_username = u.username
    JOIN categories c ON t.category_id = c.id
    LEFT JOIN expense_groups eg ON t.group_id = eg.id
    WHERE es.user_username = ? AND es.status = 'pending'
    ORDER BY t.date DESC
    """
    try:
        return pd.read_sql_query(query, conn, params=(username,))
    finally:
        conn.close()

def mark_split_as_paid(split_id):
    """Marca una división como pagada."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    UPDATE expense_splits 
    SET status = 'paid', paid_at = ?
    WHERE id = ?
    """, (datetime.now(), split_id))
    
    conn.commit()
    conn.close()

# --- Funciones mejoradas existentes ---

def get_data_as_dataframe(table_name, user_username=None):
    """Obtiene datos filtrados por usuario cuando corresponde."""
    conn = get_db_connection()
    try:
        if user_username and table_name in ['categories', 'payment_methods', 'budgets']:
            query = f"SELECT * FROM {table_name} WHERE user_username = ? OR is_default = 1"
            df = pd.read_sql_query(query, conn, params=(user_username,))
        else:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        conn.close()

def get_transactions_with_details(user_username=None):
    """Obtiene transacciones con detalles, opcionalmente filtradas por usuario."""
    conn = get_db_connection()
    query = """
    SELECT 
        t.id, t.date, t.amount, t.type, t.details, 
        t.installments_paid, t.installments_total, t.purchase_id,
        t.is_shared, t.original_amount,
        u.name as user, 
        c.name as category, 
        p.name as payment_method,
        eg.name as group_name
    FROM transactions t
    JOIN users u ON t.user_username = u.username
    JOIN categories c ON t.category_id = c.id
    LEFT JOIN payment_methods p ON t.payment_method_id = p.id
    LEFT JOIN expense_groups eg ON t.group_id = eg.id
    """
    
    params = ()
    if user_username:
        query += " WHERE t.user_username = ?"
        params = (user_username,)
    
    query += " ORDER BY t.date DESC"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        conn.close()

def add_user_if_not_exists(username, name, email=None):
    """Añade un usuario si no existe."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT OR IGNORE INTO users (username, name, email)
    VALUES (?, ?, ?)
    """, (username, name, email))
    
    conn.commit()
    conn.close()

def create_default_categories_and_methods(username):
    """Crea categorías y métodos de pago por defecto para un nuevo usuario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Categorías por defecto
    default_categories = [
        ('Alimentación', 'Gasto', '🍽️', '#FF6B6B'),
        ('Transporte', 'Gasto', '🚗', '#4ECDC4'),
        ('Entretenimiento', 'Gasto', '🎬', '#45B7D1'),
        ('Salud', 'Gasto', '🏥', '#96CEB4'),
        ('Educación', 'Gasto', '📚', '#FFEAA7'),
        ('Hogar', 'Gasto', '🏠', '#DDA0DD'),
        ('Ropa', 'Gasto', '👕', '#98D8C8'),
        ('Sueldo', 'Ingreso', '💰', '#6C5CE7'),
        ('Freelance', 'Ingreso', '💻', '#A29BFE'),
        ('Inversiones', 'Ingreso', '📈', '#FD79A8')
    ]
    
    for name, type_, icon, color in default_categories:
        cursor.execute("""
        INSERT OR IGNORE INTO categories (name, type, icon, color, user_username, is_default)
        VALUES (?, ?, ?, ?, ?, 1)
        """, (name, type_, icon, color, username))
    
    # Métodos de pago por defecto
    default_methods = [
        ('Efectivo', 'Efectivo'),
        ('Tarjeta de Débito', 'Tarjeta Débito'),
        ('Tarjeta de Crédito', 'Tarjeta Crédito'),
        ('Transferencia', 'Transferencia'),
        ('MercadoPago', 'Billetera Digital')
    ]
    
    for name, type_ in default_methods:
        cursor.execute("""
        INSERT OR IGNORE INTO payment_methods (name, type, user_username, is_default)
        VALUES (?, ?, ?, 1)
        """, (name, type_, username))
    
    conn.commit()
    conn.close()

# Inicializar la base de datos
initialize_database()