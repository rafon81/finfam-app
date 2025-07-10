import pandas as pd
import streamlit as st
from datetime import datetime
import altair as alt
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import copy # Importamos la librería para hacer copias

# Importar nuestro nuevo módulo de base de datos
import database as db

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="FinFam - Control Financiero", layout="wide", initial_sidebar_state="expanded")

# --- LÓGICA DE AUTENTICACIÓN (HÍBRIDA Y SEGURA) ---
# Intenta cargar la config desde el archivo local (para desarrollo)
try:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)
# Si no lo encuentra (en Streamlit Cloud), la carga desde los Secrets
except FileNotFoundError:
    # Usamos deepcopy para crear una copia mutable del diccionario de secretos
    # Esto evita el error "TypeError: Secrets does not support item assignment."
    config = copy.deepcopy({
        'credentials': st.secrets['credentials'],
        'cookie': st.secrets['cookie'],
        'preauthorized': st.secrets['preauthorized']
    })

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

# --- APLICACIÓN PRINCIPAL ---
with st.sidebar:
    st.title(f"Bienvenido, {st.session_state['name']} 👋")
    authenticator.logout("Salir", location='sidebar', key='unique_logout_key')

st.title("💰 FinFam: Tu Centro de Control Financiero")

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_data():
    data = {
        'transactions': db.get_transactions_with_details(),
        'categories': db.get_data_as_dataframe('categories'),
        'payment_methods': db.get_data_as_dataframe('payment_methods'),
        'budgets': db.get_budgets_with_details()
    }
    return data

app_data = load_data()

# --- PESTAÑAS ---
tabs = st.tabs([
    "📊 **Dashboard de Control**",
    "💸 **Registrar Transacción**",
    "🎯 **Gestionar Presupuestos**",
    "⚙️ **Configuración**"
])

# (El resto del código de las pestañas no necesita cambios)

# --- PESTAÑA 1: DASHBOARD ---
with tabs[0]:
    st.header("Análisis Mensual")
    # ... (código sin cambios)
    col_filt1, col_filt2, col_filt3 = st.columns(3)
    today = datetime.today()
    with col_filt1:
        years_with_data = app_data['transactions']['date'].dt.year.unique()
        available_years = sorted(list(set(years_with_data) | {today.year}) , reverse=True)
        selected_year = st.selectbox("Año", available_years)
    with col_filt2:
        meses_es = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
        selected_month_num = st.selectbox("Mes", meses_es.keys(), index=today.month - 1, format_func=lambda x: meses_es[x])
    with col_filt3:
        user_names = [d['name'] for d in config['credentials']['usernames'].values()]
        selected_person = st.selectbox("Persona", ["Ambos"] + user_names)

    transactions_df = app_data['transactions']
    trans_mes = transactions_df[
        (transactions_df['date'].dt.year == selected_year) &
        (transactions_df['date'].dt.month == selected_month_num)
    ]
    if selected_person != "Ambos":
        trans_mes = trans_mes[trans_mes['user'] == selected_person]

    ingresos_mes = trans_mes[trans_mes['type'] == 'Ingreso']
    gastos_mes = trans_mes[trans_mes['type'] == 'Gasto']

    total_ingresos = ingresos_mes['amount'].sum()
    total_gastos = gastos_mes['amount'].sum()
    balance = total_ingresos - total_gastos
    tasa_ahorro = (balance / total_ingresos) if total_ingresos > 0 else 0

    st.subheader("Indicadores Clave del Mes")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("✅ Ingresos", f"${total_ingresos:,.2f}".replace(",", "."))
    kpi2.metric("❌ Gastos", f"${total_gastos:,.2f}".replace(",", "."))
    kpi3.metric("⚖️ Balance", f"${balance:,.2f}".replace(",", "."), delta=f"{tasa_ahorro:.1%}")
    st.markdown("---")

    col_viz1, col_viz2 = st.columns([1, 2])
    with col_viz1:
        st.subheader("Gastos por Categoría")
        if not gastos_mes.empty:
            gastos_por_cat = gastos_mes.groupby('category')['amount'].sum().reset_index()
            chart = alt.Chart(gastos_por_cat).mark_arc(innerRadius=50, outerRadius=100).encode(
                theta=alt.Theta(field="amount", type="quantitative", stack=True),
                color=alt.Color(field="category", type="nominal", title="Categorías"),
                tooltip=['category', 'amount']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No hay gastos para mostrar.")
    with col_viz2:
        st.subheader("Progreso vs. Presupuesto")
        budgets_df = app_data['budgets']
        if not budgets_df.empty and not gastos_mes.empty:
            gastos_agg = gastos_mes.groupby('category')['amount'].sum().reset_index()
            data_merged = pd.merge(gastos_agg, budgets_df, on='category', how='left').fillna(0)
            data_merged['percentage'] = (data_merged['amount_x'] / data_merged['amount_y']).clip(0, 1) * 100 if data_merged['amount_y'].sum() > 0 else 0
            for _, row in data_merged.iterrows():
                if row['amount_y'] > 0:
                    st.write(f"**{row['category']}**")
                    st.write(f"${row['amount_x']:,.2f} / ${row['amount_y']:,.2f}".replace(",", "."))
                    st.progress(int(row['percentage']))
        else:
            st.info("Define presupuestos y registra gastos para ver el progreso.")

# --- PESTAÑA 2: REGISTRAR TRANSACCIÓN ---
with tabs[1]:
    st.header("Registrar Ingreso o Gasto")
    # ... (código sin cambios)
    trans_type = st.radio("Tipo de Transacción", ["Gasto", "Ingreso"], horizontal=True)
    with st.form("form_transaction", clear_on_submit=True):
        if trans_type == "Gasto":
            col1, col2 = st.columns(2)
            with col1:
                categoria = st.selectbox("🏷️ Categoría", app_data['categories'][app_data['categories']['type'] == 'Gasto']['name'].unique())
                monto_total = st.number_input("💵 Monto total de la compra", min_value=0.0, format="%.2f")
                fecha = st.date_input("🗓️ Fecha de la compra", value=datetime.today())
            with col2:
                metodo = st.selectbox("💳 Método de pago", app_data['payment_methods']['name'].unique())
                cuotas = st.number_input("🔢 Cantidad de cuotas", min_value=1, max_value=48, value=1)
            detalle = st.text_area("📝 Detalle (opcional)")
        else: # Ingreso
            col1, col2 = st.columns(2)
            with col1:
                categoria = st.selectbox("🏷️ Categoría", app_data['categories'][app_data['categories']['type'] == 'Ingreso']['name'].unique())
            with col2:
                monto_total = st.number_input("💵 Monto", min_value=0.0, format="%.2f")
            fecha = st.date_input("🗓️ Fecha", value=datetime.today())
            detalle = st.text_area("📝 Detalle (opcional)")
            metodo = None
            cuotas = 1
        
        submitted = st.form_submit_button("✅ Agregar Transacción")
        if submitted:
            try:
                db.add_transaction(
                    user_username=st.session_state["username"],
                    category_name=categoria,
                    amount=monto_total,
                    trans_type=trans_type,
                    date=fecha.strftime('%Y-%m-%d'),
                    payment_method_name=metodo,
                    details=detalle,
                    installments=cuotas,
                    total_amount=monto_total
                )
                st.success("Transacción registrada exitosamente.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al registrar la transacción: {e}")

# --- PESTAÑA 3: GESTIONAR PRESUPUESTOS ---
with tabs[2]:
    st.header("🎯 Definir Presupuestos Mensuales")
    # ... (código sin cambios)
    edited_budgets = st.data_editor(
        app_data['budgets'],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "id": None,
            "category": st.column_config.SelectboxColumn("Categoría de Gasto", options=app_data['categories'][app_data['categories']['type'] == 'Gasto']['name'].unique(), required=True),
            "amount": st.column_config.NumberColumn("Monto Presupuestado ($)", min_value=0, format="$ %.2f", required=True)
        },
        key="budget_editor"
    )
    if st.button("💾 Guardar Presupuestos"):
        db.sync_budgets_from_dataframe(edited_budgets)
        st.success("Presupuestos guardados.")
        st.cache_data.clear()

# --- PESTAÑA 4: CONFIGURACIÓN ---
with tabs[3]:
    st.header("⚙️ Configuración General")
    # ... (código sin cambios)
    st.subheader("Administrar Categorías")
    edited_cats = st.data_editor(app_data['categories'], num_rows="dynamic", use_container_width=True, key="cats_editor")
    if st.button("Guardar Categorías"):
        db.sync_from_dataframe(edited_cats, 'categories')
        st.success("Categorías actualizadas.")
        st.cache_data.clear()
    st.subheader("Administrar Métodos de Pago")
    edited_methods = st.data_editor(app_data['payment_methods'], num_rows="dynamic", use_container_width=True, key="methods_editor")
    if st.button("Guardar Métodos de Pago"):
        db.sync_from_dataframe(edited_methods, 'payment_methods')
        st.success("Métodos de pago actualizados.")
        st.cache_data.clear()
    st.subheader("Historial Completo de Transacciones")
    st.dataframe(app_data['transactions'].sort_values("date", ascending=False), use_container_width=True)
