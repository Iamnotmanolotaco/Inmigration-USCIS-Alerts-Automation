import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="ST LEGAL", layout="wide")

st.title("⚖️ ST LEGAL AUTOMATED")
st.markdown("---")

# Inicializar session state
if 'df' not in st.session_state:
    st.session_state.df = None

# Sidebar
with st.sidebar:
    st.header("📋 Menú")
    opcion = st.radio("Selecciona:", ["Dashboard", "Cargar Datos", "Procesar", "Alertas"])

# ============================================
# DASHBOARD
# ============================================
if opcion == "Dashboard":
    st.header("📊 Dashboard")
    
    if st.session_state.df is not None:
        df = st.session_state.df
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Casos", len(df))
        with col2:
            st.metric("Columnas", len(df.columns))
        with col3:
            teams = df['TeamOwner'].nunique() if 'TeamOwner' in df.columns else 0
            st.metric("Equipos", teams)
        
        st.dataframe(df.head(20))
    else:
        st.info("👈 Ve a 'Cargar Datos' primero")

# ============================================
# CARGAR DATOS
# ============================================
elif opcion == "Cargar Datos":
    st.header("📁 Cargar archivo")
    
    archivo = st.file_uploader("Sube tu archivo Excel", type=['xlsx', 'xls'])
    
    if archivo is not None:
        try:
            df = pd.read_excel(archivo, header=2)
            st.session_state.df = df
            st.success(f"✅ Cargado: {len(df)} filas, {len(df.columns)} columnas")
            st.subheader("Vista previa:")
            st.dataframe(df.head(10))
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

# ============================================
# PROCESAR
# ============================================
elif opcion == "Procesar":
    st.header("⚙️ Procesar datos")
    
    if st.session_state.df is not None:
        if st.button("🚀 Procesar datos", type="primary"):
            try:
                df = st.session_state.df.copy()
                
                # Limpiar nombres
                df.columns = df.columns.str.strip()
                
                # Agregar TeamOwner si no existe
                if 'TeamOwner' not in df.columns and 'Case Type' in df.columns:
                    df['TeamOwner'] = "Team " + df['Case Type'].astype(str).str[:15]
                
                st.session_state.df = df
                st.success("✅ Datos procesados correctamente")
                st.subheader("Vista previa:")
                st.dataframe(df.head(10))
            except Exception as e:
                st.error(f"Error al procesar: {e}")
    else:
        st.warning("⚠️ Primero carga un archivo en 'Cargar Datos'")

# ============================================
# ALERTAS
# ============================================
elif opcion == "Alertas":
    st.header("📧 Alertas")
    
    if st.session_state.df is not None:
        if st.button("📧 Generar alertas", type="primary"):
            try:
                df = st.session_state.df
                if 'TeamOwner' in df.columns:
                    equipos = df['TeamOwner'].dropna().unique()
                    for equipo in equipos:
                        casos = len(df[df['TeamOwner'] == equipo])
                        st.info(f"📧 {equipo}: {casos} casos pendientes")
                    st.success("✅ Alertas generadas")
                else:
                    st.warning("Procesa los datos primero para tener la columna TeamOwner")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("⚠️ Primero carga y procesa los datos")
