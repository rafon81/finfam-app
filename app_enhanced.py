import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import altair as alt
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import json

# Importar nuestro módulo de base de datos mejorado
import database_enhanced as db

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVE ---
st.set_page_config(
    page_title="FinFam - Control Financiero", 
    layout="wide", 
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/tu-repo/finfam',
        'Report a bug': "https://github.com/tu-repo/finfam/issues",
        'About': "FinFam - Tu centro de control financiero familiar"
    }
)

# CSS para diseño responsive
st.markdown("""
<style>
    /* Responsive design */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            font-size: 0.8rem;
            padding: 0.5rem;
        }
        
        .metric-container {
            text-align: center;
            margin-bottom: 1rem;
        }
    }
    
    /* Mejoras visuales */
    .tutorial-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    
    .expense-split-card {
        background: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    
    .pending-payment {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
    
    .success-message {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- LÓGICA DE AUTENTICACIÓN ---
try:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    config = {
        'credentials': {
            'usernames': {
                username: dict(details)
                for username, details in st.secrets.credentials.usernames.items()
            }
        },
        'cookie': dict(st.secrets.cookie),
        'preauthorized': dict(st.secrets.preauthorized)
    }

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- PANTALLA DE LOGIN ---
authenticator.login()

if not st.session_state.get("authentication_status"):
    if st.session_state.get("authentication_status") is False:
        st.error("Usuario o contraseña incorrectos.")
    elif st.session_state.get("authentication_status") is None:
        st.warning("Por favor, ingresa tus credenciales.")
    st.stop()

# --- INICIALIZACIÓN DE USUARIO ---
current_username = st.session_state["username"]
current_name = st.session_state["name"]

# Asegurar que el usuario existe en la base de datos
db.add_user_if_not_exists(current_username, current_name)

# Verificar si es la primera vez del usuario
tutorial_progress = db.get_tutorial_progress(current_username)
is_first_time = len(tutorial_progress) == 0

# --- APLICACIÓN PRINCIPAL ---
with st.sidebar:
    st.title(f"Bienvenido, {current_name} 👋")
    
    # Mostrar progreso del tutorial si está en curso
    if not tutorial_progress.get('tutorial_completed', False):
        completed_steps = sum(1 for completed in tutorial_progress.values() if completed)
        total_steps = 5
        progress = completed_steps / total_steps
        st.progress(progress)
        st.caption(f"Tutorial: {completed_steps}/{total_steps} pasos completados")
    
    # Mostrar pagos pendientes
    pending_splits = db.get_pending_splits_for_user(current_username)
    if not pending_splits.empty:
        st.warning(f"💰 Tienes {len(pending_splits)} pagos pendientes")
    
    authenticator.logout("Salir", location='sidebar', key='unique_logout_key')

st.title("💰 FinFam: Tu Centro de Control Financiero")

# --- TUTORIAL INTERACTIVO ---
if is_first_time or not tutorial_progress.get('tutorial_completed', False):
    st.markdown("""
    <div class="tutorial-card">
        <h2>🎯 ¡Bienvenido a FinFam!</h2>
        <p>Te ayudaremos a configurar tu control financiero en 5 pasos simples.</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📚 Tutorial de Configuración Inicial", expanded=True):
        tutorial_tabs = st.tabs([
            "1️⃣ Datos Básicos",
            "2️⃣ Categorías",
            "3️⃣ Métodos de Pago", 
            "4️⃣ Primera Transacción",
            "5️⃣ Presupuesto"
        ])
        
        with tutorial_tabs[0]:
            st.subheader("Paso 1: Configuración Inicial")
            st.write("Vamos a crear tus categorías y métodos de pago por defecto.")
            
            if st.button("✅ Crear configuración por defecto"):
                db.create_default_categories_and_methods(current_username)
                db.update_tutorial_step(current_username, 'basic_setup', True)
                st.success("¡Configuración básica completada!")
                st.rerun()
        
        with tutorial_tabs[1]:
            st.subheader("Paso 2: Revisar Categorías")
            st.write("Estas son tus categorías por defecto. Puedes modificarlas en la pestaña Configuración.")
            
            categories = db.get_data_as_dataframe('categories', current_username)
            if not categories.empty:
                for _, cat in categories.iterrows():
                    st.write(f"{cat.get('icon', '📁')} {cat['name']} ({cat['type']})")
                
                if st.button("✅ Categorías revisadas"):
                    db.update_tutorial_step(current_username, 'categories_review', True)
                    st.success("¡Paso completado!")
        
        with tutorial_tabs[2]:
            st.subheader("Paso 3: Métodos de Pago")
            st.write("Revisa tus métodos de pago disponibles.")
            
            methods = db.get_data_as_dataframe('payment_methods', current_username)
            if not methods.empty:
                for _, method in methods.iterrows():
                    st.write(f"💳 {method['name']} ({method.get('type', 'N/A')})")
                
                if st.button("✅ Métodos revisados"):
                    db.update_tutorial_step(current_username, 'payment_methods_review', True)
                    st.success("¡Paso completado!")
        
        with tutorial_tabs[3]:
            st.subheader("Paso 4: Tu Primera Transacción")
            st.write("¡Registra tu primera transacción para familiarizarte con el sistema!")
            
            if tutorial_progress.get('first_transaction', False):
                st.success("✅ ¡Ya registraste tu primera transacción!")
            else:
                st.info("Ve a la pestaña 'Registrar Transacción' para completar este paso.")
        
        with tutorial_tabs[4]:
            st.subheader("Paso 5: Define tu Primer Presupuesto")
            st.write("Establece un presupuesto mensual para comenzar a controlar tus gastos.")
            
            if tutorial_progress.get('first_budget', False):
                st.success("✅ ¡Ya definiste tu primer presupuesto!")
            else:
                st.info("Ve a la pestaña 'Gestionar Presupuestos' para completar este paso.")

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_data():
    data = {
        'transactions': db.get_transactions_with_details(current_username),
        'categories': db.get_data_as_dataframe('categories', current_username),
        'payment_methods': db.get_data_as_dataframe('payment_methods', current_username),
        'budgets': db.get_budgets_with_details(),
        'pending_splits': db.get_pending_splits_for_user(current_username)
    }
    return data

app_data = load_data()

# --- PESTAÑAS PRINCIPALES ---
main_tabs = st.tabs([
    "📊 Dashboard",
    "💸 Registrar",
    "👥 Gastos Compartidos",
    "🎯 Presupuestos",
    "⚙️ Configuración"
])

# --- PESTAÑA 1: DASHBOARD ---
with main_tabs[0]:
    st.header("📊 Análisis Financiero")
    
    # Filtros responsive
    col_filt1, col_filt2, col_filt3 = st.columns([1, 1, 1])
    today = datetime.today()
    
    with col_filt1:
        years_with_data = app_data['transactions']['date'].dt.year.unique() if not app_data['transactions'].empty else []
        available_years = sorted(list(set(years_with_data) | {today.year}), reverse=True)
        selected_year = st.selectbox("📅 Año", available_years)
    
    with col_filt2:
        meses_es = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 
                   7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
        selected_month_num = st.selectbox("📅 Mes", meses_es.keys(), 
                                        index=today.month - 1, format_func=lambda x: meses_es[x])
    
    with col_filt3:
        view_mode = st.selectbox("👁️ Vista", ["Solo mis transacciones", "Incluir gastos compartidos"])

    # Filtrar transacciones
    transactions_df = app_data['transactions']
    if not transactions_df.empty:
        trans_mes = transactions_df[
            (transactions_df['date'].dt.year == selected_year) &
            (transactions_df['date'].dt.month == selected_month_num)
        ]
        
        if view_mode == "Solo mis transacciones":
            trans_mes = trans_mes[trans_mes['is_shared'] == False]
    else:
        trans_mes = pd.DataFrame()

    # Calcular métricas
    if not trans_mes.empty:
        ingresos_mes = trans_mes[trans_mes['type'] == 'Ingreso']
        gastos_mes = trans_mes[trans_mes['type'] == 'Gasto']
        
        total_ingresos = ingresos_mes['amount'].sum()
        total_gastos = gastos_mes['amount'].sum()
        balance = total_ingresos - total_gastos
        tasa_ahorro = (balance / total_ingresos) if total_ingresos > 0 else 0
    else:
        total_ingresos = total_gastos = balance = tasa_ahorro = 0

    # KPIs responsive
    st.subheader("💡 Indicadores del Mes")
    kpi_cols = st.columns(3)
    
    with kpi_cols[0]:
        st.metric("✅ Ingresos", f"${total_ingresos:,.0f}")
    with kpi_cols[1]:
        st.metric("❌ Gastos", f"${total_gastos:,.0f}")
    with kpi_cols[2]:
        st.metric("⚖️ Balance", f"${balance:,.0f}", delta=f"{tasa_ahorro:.1%}")

    st.markdown("---")

    # Visualizaciones responsive
    if not trans_mes.empty and not gastos_mes.empty:
        viz_cols = st.columns([1, 1])
        
        with viz_cols[0]:
            st.subheader("🥧 Gastos por Categoría")
            gastos_por_cat = gastos_mes.groupby('category')['amount'].sum().reset_index()
            
            chart = alt.Chart(gastos_por_cat).mark_arc(innerRadius=50, outerRadius=100).encode(
                theta=alt.Theta(field="amount", type="quantitative"),
                color=alt.Color(field="category", type="nominal", 
                              scale=alt.Scale(scheme='category20')),
                tooltip=['category:N', alt.Tooltip('amount:Q', format=',.0f')]
            ).properties(height=300)
            
            st.altair_chart(chart, use_container_width=True)
        
        with viz_cols[1]:
            st.subheader("📈 Tendencia Semanal")
            trans_mes_copy = trans_mes.copy()
            trans_mes_copy['week'] = trans_mes_copy['date'].dt.isocalendar().week
            weekly_data = trans_mes_copy.groupby(['week', 'type'])['amount'].sum().reset_index()
            
            line_chart = alt.Chart(weekly_data).mark_line(point=True).encode(
                x=alt.X('week:O', title='Semana'),
                y=alt.Y('amount:Q', title='Monto ($)'),
                color=alt.Color('type:N', title='Tipo'),
                tooltip=['week:O', 'type:N', alt.Tooltip('amount:Q', format=',.0f')]
            ).properties(height=300)
            
            st.altair_chart(line_chart, use_container_width=True)
    else:
        st.info("📝 Registra algunas transacciones para ver tus análisis aquí.")

# --- PESTAÑA 2: REGISTRAR TRANSACCIÓN ---
with main_tabs[1]:
    st.header("💸 Registrar Nueva Transacción")
    
    trans_type = st.radio("Tipo de Transacción", ["Gasto", "Ingreso"], horizontal=True)
    
    with st.form("form_transaction", clear_on_submit=True):
        if trans_type == "Gasto":
            col1, col2 = st.columns(2)
            with col1:
                gasto_categories = app_data['categories'][app_data['categories']['type'] == 'Gasto']
                if gasto_categories.empty:
                    st.error("No tienes categorías de gasto. Ve a Configuración para crearlas.")
                    st.stop()
                
                categoria = st.selectbox("🏷️ Categoría", gasto_categories['name'].unique())
                monto_total = st.number_input("💵 Monto total", min_value=0.0, format="%.2f")
                fecha = st.date_input("🗓️ Fecha", value=datetime.today())
            
            with col2:
                metodo = st.selectbox("💳 Método de pago", app_data['payment_methods']['name'].unique())
                cuotas = st.number_input("🔢 Cuotas", min_value=1, max_value=48, value=1)
            
            detalle = st.text_area("📝 Detalle (opcional)")
            
        else:  # Ingreso
            col1, col2 = st.columns(2)
            with col1:
                ingreso_categories = app_data['categories'][app_data['categories']['type'] == 'Ingreso']
                if ingreso_categories.empty:
                    st.error("No tienes categorías de ingreso. Ve a Configuración para crearlas.")
                    st.stop()
                
                categoria = st.selectbox("🏷️ Categoría", ingreso_categories['name'].unique())
                monto_total = st.number_input("💵 Monto", min_value=0.0, format="%.2f")
            
            with col2:
                fecha = st.date_input("🗓️ Fecha", value=datetime.today())
            
            detalle = st.text_area("📝 Detalle (opcional)")
            metodo = None
            cuotas = 1
        
        submitted = st.form_submit_button("✅ Registrar Transacción", use_container_width=True)
        
        if submitted:
            try:
                db.add_transaction(
                    user_username=current_username,
                    category_name=categoria,
                    amount=monto_total,
                    trans_type=trans_type,
                    date=fecha.strftime('%Y-%m-%d'),
                    payment_method_name=metodo,
                    details=detalle,
                    installments=cuotas,
                    total_amount=monto_total
                )
                
                st.success("✅ ¡Transacción registrada exitosamente!")
                
                # Marcar paso del tutorial como completado
                if not tutorial_progress.get('first_transaction', False):
                    db.update_tutorial_step(current_username, 'first_transaction', True)
                    st.balloons()
                    st.info("🎉 ¡Completaste el paso 4 del tutorial!")
                
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"❌ Error al registrar la transacción: {e}")

# --- PESTAÑA 3: GASTOS COMPARTIDOS ---
with main_tabs[2]:
    st.header("👥 Gestión de Gastos Compartidos")
    
    # Mostrar pagos pendientes
    if not app_data['pending_splits'].empty:
        st.subheader("💰 Pagos Pendientes")
        
        for _, split in app_data['pending_splits'].iterrows():
            with st.container():
                st.markdown(f"""
                <div class="pending-payment">
                    <strong>{split['payer_name']}</strong> pagó <strong>${split['amount']:,.0f}</strong><br>
                    <small>{split['category']} • {split['date']} • {split.get('group_name', 'Sin grupo')}</small><br>
                    <em>{split['details']}</em>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button(f"✅ Marcar como pagado", key=f"pay_{split['id']}"):
                        db.mark_split_as_paid(split['id'])
                        st.success("¡Pago registrado!")
                        st.rerun()
    
    st.markdown("---")
    
    # Registrar nuevo gasto compartido
    st.subheader("➕ Registrar Gasto Compartido")
    
    with st.form("shared_expense_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            gasto_categories = app_data['categories'][app_data['categories']['type'] == 'Gasto']
            categoria_compartida = st.selectbox("🏷️ Categoría", gasto_categories['name'].unique(), key="shared_cat")
            monto_compartido = st.number_input("💵 Monto total", min_value=0.0, format="%.2f", key="shared_amount")
            fecha_compartida = st.date_input("🗓️ Fecha", value=datetime.today(), key="shared_date")
        
        with col2:
            metodo_compartido = st.selectbox("💳 Método de pago", app_data['payment_methods']['name'].unique(), key="shared_method")
            detalle_compartido = st.text_area("📝 Descripción del gasto", key="shared_details")
        
        # Configuración de división
        st.subheader("⚖️ División del Gasto")
        
        # Por simplicidad, permitir división entre usuarios conocidos
        available_users = list(config['credentials']['usernames'].keys())
        selected_users = st.multiselect("👥 Seleccionar participantes", available_users, default=[current_username])
        
        if selected_users and monto_compartido > 0:
            division_method = st.radio("Método de división", ["Partes iguales", "Montos específicos"], horizontal=True)
            
            split_data = {}
            if division_method == "Partes iguales":
                amount_per_person = monto_compartido / len(selected_users)
                for user in selected_users:
                    split_data[user] = amount_per_person
                    st.write(f"👤 {user}: ${amount_per_person:,.2f}")
            else:
                st.write("Especifica el monto para cada persona:")
                total_specified = 0
                for user in selected_users:
                    amount = st.number_input(f"💵 {user}", min_value=0.0, format="%.2f", key=f"split_{user}")
                    split_data[user] = amount
                    total_specified += amount
                
                if abs(total_specified - monto_compartido) > 0.01:
                    st.warning(f"⚠️ La suma ({total_specified:.2f}) no coincide con el monto total ({monto_compartido:.2f})")
        
        submitted_shared = st.form_submit_button("✅ Registrar Gasto Compartido", use_container_width=True)
        
        if submitted_shared and selected_users and monto_compartido > 0:
            try:
                # Crear grupo temporal para este gasto
                group_id = db.create_expense_group(
                    name=f"Gasto {fecha_compartida.strftime('%d/%m/%Y')}",
                    description=detalle_compartido,
                    created_by=current_username,
                    members=selected_users
                )
                
                # Registrar el gasto compartido
                db.add_shared_expense(
                    payer_username=current_username,
                    category_name=categoria_compartida,
                    amount=monto_compartido,
                    date=fecha_compartida.strftime('%Y-%m-%d'),
                    details=detalle_compartido,
                    group_id=group_id,
                    split_method=division_method,
                    split_data=split_data,
                    payment_method_name=metodo_compartido
                )
                
                st.success("✅ ¡Gasto compartido registrado exitosamente!")
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"❌ Error al registrar el gasto compartido: {e}")

# --- PESTAÑA 4: PRESUPUESTOS ---
with main_tabs[3]:
    st.header("🎯 Gestión de Presupuestos")
    
    # Obtener presupuestos del usuario
    budgets_df = app_data['budgets']
    
    st.subheader("📊 Presupuestos Actuales")
    
    # Editor de presupuestos
    gasto_categories = app_data['categories'][app_data['categories']['type'] == 'Gasto']
    
    if gasto_categories.empty:
        st.warning("⚠️ Necesitas crear categorías de gasto primero. Ve a la pestaña Configuración.")
    else:
        edited_budgets = st.data_editor(
            budgets_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "id": None,
                "category": st.column_config.SelectboxColumn(
                    "Categoría", 
                    options=gasto_categories['name'].unique(), 
                    required=True
                ),
                "amount": st.column_config.NumberColumn(
                    "Presupuesto Mensual ($)", 
                    min_value=0, 
                    format="$ %.0f", 
                    required=True
                )
            },
            key="budget_editor"
        )
        
        if st.button("💾 Guardar Presupuestos", use_container_width=True):
            try:
                db.sync_budgets_from_dataframe(edited_budgets)
                st.success("✅ ¡Presupuestos guardados exitosamente!")
                
                # Marcar paso del tutorial como completado
                if not tutorial_progress.get('first_budget', False):
                    db.update_tutorial_step(current_username, 'first_budget', True)
                    db.update_tutorial_step(current_username, 'tutorial_completed', True)
                    st.balloons()
                    st.success("🎉 ¡Felicitaciones! Completaste el tutorial completo.")
                
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"❌ Error al guardar presupuestos: {e}")

# --- PESTAÑA 5: CONFIGURACIÓN ---
with main_tabs[4]:
    st.header("⚙️ Configuración")
    
    config_tabs = st.tabs(["📂 Categorías", "💳 Métodos de Pago", "📊 Historial", "🔧 Avanzado"])
    
    with config_tabs[0]:
        st.subheader("Administrar Categorías")
        edited_cats = st.data_editor(
            app_data['categories'], 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "id": None,
                "user_username": None,
                "is_default": None,
                "created_at": None,
                "icon": st.column_config.TextColumn("Icono", help="Emoji para la categoría"),
                "color": st.column_config.TextColumn("Color", help="Color en formato hex (#FF0000)"),
                "name": st.column_config.TextColumn("Nombre", required=True),
                "type": st.column_config.SelectboxColumn("Tipo", options=["Ingreso", "Gasto"], required=True)
            },
            key="cats_editor"
        )
        
        if st.button("💾 Guardar Categorías"):
            try:
                db.sync_from_dataframe(edited_cats, 'categories')
                st.success("✅ Categorías actualizadas.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    with config_tabs[1]:
        st.subheader("Administrar Métodos de Pago")
        edited_methods = st.data_editor(
            app_data['payment_methods'], 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "id": None,
                "user_username": None,
                "is_default": None,
                "created_at": None,
                "name": st.column_config.TextColumn("Nombre", required=True),
                "type": st.column_config.SelectboxColumn(
                    "Tipo", 
                    options=["Efectivo", "Tarjeta Débito", "Tarjeta Crédito", "Transferencia", "Billetera Digital"]
                )
            },
            key="methods_editor"
        )
        
        if st.button("💾 Guardar Métodos de Pago"):
            try:
                db.sync_from_dataframe(edited_methods, 'payment_methods')
                st.success("✅ Métodos de pago actualizados.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    with config_tabs[2]:
        st.subheader("📊 Historial Completo de Transacciones")
        
        # Filtros para el historial
        hist_col1, hist_col2, hist_col3 = st.columns(3)
        
        with hist_col1:
            date_from = st.date_input("Desde", value=datetime.today() - timedelta(days=30))
        with hist_col2:
            date_to = st.date_input("Hasta", value=datetime.today())
        with hist_col3:
            transaction_type_filter = st.selectbox("Tipo", ["Todos", "Ingreso", "Gasto"])
        
        # Filtrar historial
        filtered_transactions = app_data['transactions'].copy()
        if not filtered_transactions.empty:
            filtered_transactions = filtered_transactions[
                (filtered_transactions['date'].dt.date >= date_from) &
                (filtered_transactions['date'].dt.date <= date_to)
            ]
            
            if transaction_type_filter != "Todos":
                filtered_transactions = filtered_transactions[
                    filtered_transactions['type'] == transaction_type_filter
                ]
        
        st.dataframe(
            filtered_transactions.sort_values("date", ascending=False),
            use_container_width=True,
            column_config={
                "id": None,
                "date": st.column_config.DateColumn("Fecha"),
                "amount": st.column_config.NumberColumn("Monto", format="$ %.0f"),
                "type": "Tipo",
                "category": "Categoría",
                "payment_method": "Método",
                "details": "Detalles",
                "is_shared": st.column_config.CheckboxColumn("Compartido")
            }
        )
    
    with config_tabs[3]:
        st.subheader("🔧 Configuración Avanzada")
        
        # Reiniciar tutorial
        if st.button("🔄 Reiniciar Tutorial"):
            # Limpiar progreso del tutorial
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tutorial_progress WHERE user_username = ?", (current_username,))
            conn.commit()
            conn.close()
            st.success("✅ Tutorial reiniciado. Recarga la página para comenzar.")
        
        # Exportar datos
        if st.button("📥 Exportar Datos"):
            # Crear un archivo CSV con todas las transacciones del usuario
            export_data = app_data['transactions']
            if not export_data.empty:
                csv = export_data.to_csv(index=False)
                st.download_button(
                    label="⬇️ Descargar CSV",
                    data=csv,
                    file_name=f"finfam_export_{current_username}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay datos para exportar.")