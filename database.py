import sqlite3
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import uuid

DB_FILE = "database.db"

def get_db_connection():
    """Crea y retorna una conexión a la base de datos."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    return conn

def initialize_database():
    """Crea las tablas de la base de datos si no existen."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios (para futuras ampliaciones)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )""")

    # Tabla de Categorías
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        type TEXT NOT NULL CHECK(type IN ('Ingreso', 'Gasto'))
    )""")

    # Tabla de Métodos de Pago
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )""")

    # Tabla de Transacciones (unifica gastos e ingresos)
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
        installments_paid INTEGER,
        installments_total INTEGER,
        purchase_id TEXT,
        FOREIGN KEY (user_username) REFERENCES users (username),
        FOREIGN KEY (category_id) REFERENCES categories (id),
        FOREIGN KEY (payment_method_id) REFERENCES payment_methods (id)
    )""")

    # Tabla de Presupuestos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL UNIQUE,
        amount REAL NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )""")

    conn.commit()
    conn.close()

# --- Funciones para obtener datos (Lectura) ---

def get_data_as_dataframe(table_name):
    """Obtiene todos los datos de una tabla y los devuelve como DataFrame."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        conn.close()

def get_transactions_with_details():
    """Obtiene todas las transacciones con nombres de categoría y método."""
    conn = get_db_connection()
    query = """
    SELECT 
        t.id, t.date, t.amount, t.type, t.details, 
        t.installments_paid, t.installments_total, t.purchase_id,
        u.name as user, 
        c.name as category, 
        p.name as payment_method
    FROM transactions t
    JOIN users u ON t.user_username = u.username
    JOIN categories c ON t.category_id = c.id
    LEFT JOIN payment_methods p ON t.payment_method_id = p.id
    """
    try:
        df = pd.read_sql_query(query, conn)
        df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        conn.close()

def get_budgets_with_details():
    """Obtiene los presupuestos con el nombre de la categoría."""
    conn = get_db_connection()
    query = """
    SELECT b.id, c.name as category, b.amount
    FROM budgets b
    JOIN categories c ON b.category_id = c.id
    """
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

# --- Funciones para modificar datos (Escritura) ---

def add_transaction(user_username, category_name, amount, trans_type, date, 
                    payment_method_name=None, details=None, installments=1, total_amount=None):
    """Añade una o más transacciones (maneja cuotas)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener IDs de tablas relacionadas
    category_id = cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,)).fetchone()[0]
    payment_method_id = None
    if payment_method_name:
        payment_method_id = cursor.execute("SELECT id FROM payment_methods WHERE name = ?", (payment_method_name,)).fetchone()
        if payment_method_id:
            payment_method_id = payment_method_id[0]

    purchase_id = str(uuid.uuid4()) # ID único para agrupar cuotas
    installment_amount = (total_amount or amount) / installments

    for i in range(installments):
        transaction_id = str(uuid.uuid4())
        transaction_date = (datetime.strptime(date, '%Y-%m-%d') + relativedelta(months=i)).strftime('%Y-%m-%d')
        
        cursor.execute("""
        INSERT INTO transactions (id, user_username, category_id, payment_method_id, date, amount, type, details, installments_paid, installments_total, purchase_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (transaction_id, user_username, category_id, payment_method_id, transaction_date, installment_amount, trans_type, details, i + 1, installments, purchase_id))

    conn.commit()
    conn.close()

def sync_from_dataframe(df, table_name, unique_column='name'):
    """Sincroniza una tabla (categorias, metodos) desde un DataFrame de Streamlit."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener IDs existentes
    existing_items = {row[unique_column] for row in cursor.execute(f"SELECT {unique_column} FROM {table_name}").fetchall()}
    
    # Borrar los que ya no están en el DataFrame
    items_in_df = set(df[unique_column].dropna())
    to_delete = existing_items - items_in_df
    if to_delete:
        cursor.executemany(f"DELETE FROM {table_name} WHERE {unique_column} = ?", [(item,) for item in to_delete])

    # Insertar o ignorar los nuevos
    for _, row in df.iterrows():
        if pd.notna(row[unique_column]):
            if table_name == 'categories':
                cursor.execute(f"INSERT OR IGNORE INTO {table_name} ({unique_column}, type) VALUES (?, ?)", (row[unique_column], row['type']))
            else:
                cursor.execute(f"INSERT OR IGNORE INTO {table_name} ({unique_column}) VALUES (?)", (row[unique_column],))
    
    conn.commit()
    conn.close()

def sync_budgets_from_dataframe(df):
    """Sincroniza la tabla de presupuestos desde un DataFrame."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Borrar todos los presupuestos existentes para simplificar la sincronización
    cursor.execute("DELETE FROM budgets")

    for _, row in df.iterrows():
        if pd.notna(row['category']) and pd.notna(row['amount']):
            # Obtener el ID de la categoría
            category_id_row = cursor.execute("SELECT id FROM categories WHERE name = ?", (row['category'],)).fetchone()
            if category_id_row:
                category_id = category_id_row[0]
                cursor.execute("INSERT INTO budgets (category_id, amount) VALUES (?, ?)", (category_id, row['amount']))

    conn.commit()
    conn.close()

# Inicializa la base de datos al arrancar
initialize_database()
