import streamlit as st
import pandas as pd
import re
from datetime import datetime
import plotly.express as px
import io
import os

# Configuración de la página
st.set_page_config(
    page_title="ST LEGAL AUTOMATED",
    page_icon="⚖️",
    layout="wide"
)

# ============================================
# CLASES Y FUNCIONES
# ============================================

class CaseProcessor:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.keep_columns = [
            "Case Created Date", "Office Name", "Case Type", "Case Status",
            "Case Number", "Deadline", "Deadline Status",
            "TeamOwner", "Case #", "Desktime"
        ]
    
    def process(self):
        # Limpiar nombres
        self.df.columns = self.df.columns.str.strip()
        
        # Filtrar columnas
        existing_cols = [col for col in self.keep_columns if col in self.df.columns]
        self.df = self.df[existing_cols]
        
        # Agregar Case #
        if "Case Number" in self.df.columns:
            def first_digit_run(text):
                if pd.isna(text):
                    return ""
                match = re.search(r'\d+', str(text))
                return match.group(0) if match else ""
            self.df["Case #"] = self.df["Case Number"].apply(first_digit_run)
        
        # Agregar Desktime
        if "Deadline" in self.df.columns:
            today = datetime.now().date()
            def calc_desktime(deadline):
                if pd.isna(deadline):
                    return "No Deadline"
                try:
                    deadline_date = pd.to_datetime(deadline).date()
                    if deadline_date > today:
                        return "On time"
                    else:
                        return "Out of Desktime"
                except:
                    return "No Deadline"
            self.df["Desktime"] = self.df["Deadline"].apply(calc_desktime)
        
        # Agregar TeamOwner
        if "Case Type" in self.df.columns:
            unique_types = self.df["Case Type"].dropna().unique()
            team_mapping = {}
            for ct in unique_types:
                ct_str = str(ct).lower()
                if "adjustment" in ct_str:
                    team_mapping[ct] = "Team AOS"
                elif "naturalization" in ct_str:
                    team_mapping[ct] = "Team Naturalization"
                elif "rfe" in ct_str:
                    team_mapping[ct] = "Team RFE"
                else:
                    team_mapping[ct] = "Team General"
            self.df["TeamOwner"] = self.df["Case Type"].map(team_mapping)
        
        # Filtrar por RFE
        if "Case Status" in self.df.columns and "Deadline Status" in self.df.columns:
            rfe_mask = self.df["Case Status"].astype(str).str.upper().str.contains('RFE', na=False)
            self.df = self.df[rfe_mask | (self.df["Deadline Status"] != "SATISFIED")]
        
        # Eliminar duplicados
        if "Case Type" in self.df.columns and "Case #" in self.df.columns:
            self.df = self.df.drop_duplicates(subset=["Case Type", "Case #"], keep='first')
        
        return self.df


class AlertSystem:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.today = datetime.now().date()
    
    def calculate_days(self, deadline_str):
        if pd.isna(deadline_str):
            return None
        try:
            deadline_date = pd.to_datetime(deadline_str).date()
            return (deadline_date - self.today).days
        except:
            return None
    
    def get_alerts(self, days_before=7):
        self.df['Days_Until'] = self.df['Deadline'].apply(self.calculate_days)
        mask = (self.df['Days_Until'] >= 0) & (self.df['Days_Until'] <= days_before)
        return self.df[mask].copy()


# ============================================
# INTERFAZ DE STREAMLIT
# ============================================

# Título principal
st.markdown("""
<div style='text-align: center; background: linear-gradient(135deg, #1a3a5c, #2a5a8c); padding: 2rem; border-radius: 10px; margin-bottom: 2rem;'>
    <h1 style='color: white; margin: 0;'>⚖️ ST LEGAL AUTOMATED</h1>
    <p style='color: #c8e0f5; margin: 0;'>Sistema de Gestión de Plazos y Vencimientos</p>
</div>
""", unsafe_allow_html=True)

# Menú lateral
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/law.png", width=80)
    st.markdown("---")
    menu = st.radio(
        "📋 MENÚ PRINCIPAL",
        ["📊 Dashboard", "📁 Cargar Datos", "⚙️ Procesar Datos", "📧 Alertas", "📜 Historial"]
    )
    st.markdown("---")
    st.caption(f"Versión: 2.0.0\nFecha: {datetime.now().strftime('%d/%m/%Y')}")

# Inicializar session state
if 'df_original' not in st.session_state:
    st.session_state.df_original = None
if 'df_procesado' not in st.session_state:
    st.session_state.df_procesado = None
if 'historial' not in st.session_state:
    st.session_state.historial = []

# ============================================
# 1. DASHBOARD
# ============================================
if menu == "📊 Dashboard":
    st.header("📊 Dashboard de Casos")
    
    if st.session_state.df_procesado is not None:
        df = st.session_state.df_procesado
        alert_system = AlertSystem(df)
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 Total Casos", len(df))
        with col2:
            overdue = len(df[df['Desktime'] == "Out of Desktime"])
            st.metric("⚠️ Casos Vencidos", overdue, delta="URGENTE" if overdue > 0 else None, delta_color="inverse")
        with col3:
            upcoming = len(df[df['Desktime'] == "On time"])
            st.metric("📅 Próximos a Vencer", upcoming)
        with col4:
            st.metric("👥 Equipos", df['TeamOwner'].nunique())
        
        st.markdown("---")
        
        # Gráficos
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Casos por Equipo")
            team_counts = df['TeamOwner'].value_counts()
            fig = px.bar(x=team_counts.index, y=team_counts.values, color_discrete_sequence=['#1a3a5c'])
            fig.update_layout(showlegend=False, xaxis_title="Equipo", yaxis_title="Número de Casos")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Casos por Estado")
            status_counts = df['Case Status'].value_counts().head(8)
            fig = px.pie(values=status_counts.values, names=status_counts.index)
            st.plotly_chart(fig, use_container_width=True)
        
        # Tabla de casos prioritarios
        st.subheader("🚨 Casos Prioritarios")
        alerts = alert_system.get_alerts()
        if len(alerts) > 0:
            st.dataframe(alerts[['Case #', 'Case Type', 'Case Status', 'Deadline', 'TeamOwner', 'Desktime']], use_container_width=True)
        else:
            st.info("✅ No hay casos prioritarios en este momento")
        
        # Tabla completa
        with st.expander("📋 Ver todos los casos"):
            st.dataframe(df, use_container_width=True)
        
        # Botón descargar
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name="casos_procesados.xlsx")
        
    else:
        st.info("👈 Ve a 'Cargar Datos' y 'Procesar Datos' primero")

# ============================================
# 2. CARGAR DATOS
# ============================================
elif menu == "📁 Cargar Datos":
    st.header("📁 Cargar Archivo")
    
    archivo = st.file_uploader("Selecciona tu archivo Excel", type=['xlsx', 'xls'])
    
    if archivo is not None:
        try:
            df = pd.read_excel(archivo, header=2)
            st.session_state.df_original = df
            st.success(f"✅ Archivo cargado exitosamente!")
            st.info(f"📊 {df.shape[0]} filas, {df.shape[1]} columnas")
            
            st.subheader("Vista previa:")
            st.dataframe(df.head(10), use_container_width=True)
            
            st.subheader("Columnas encontradas:")
            st.write(list(df.columns))
        except Exception as e:
            st.error(f"Error: {e}")

# ============================================
# 3. PROCESAR DATOS
# ============================================
elif menu == "⚙️ Procesar Datos":
    st.header("⚙️ Procesar Datos")
    
    if st.session_state.df_original is not None:
        if st.button("🚀 Procesar Datos", type="primary"):
            with st.spinner("Procesando..."):
                processor = CaseProcessor(st.session_state.df_original.copy())
                df_procesado = processor.process()
                st.session_state.df_procesado = df_procesado
                
                st.success("✅ Datos procesados exitosamente!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Filas originales", len(st.session_state.df_original))
                with col2:
                    st.metric("Filas procesadas", len(df_procesado))
                with col3:
                    st.metric("Reducción", f"{len(st.session_state.df_original) - len(df_procesado)} filas")
                
                st.subheader("Vista previa:")
                st.dataframe(df_procesado.head(10), use_container_width=True)
    else:
        st.warning("⚠️ Primero carga un archivo en 'Cargar Datos'")

# ============================================
# 4. ALERTAS
# ============================================
elif menu == "📧 Alertas":
    st.header("📧 Sistema de Alertas")
    
    if st.session_state.df_procesado is not None:
        df = st.session_state.df_procesado
        alert_system = AlertSystem(df)
        
        col1, col2 = st.columns(2)
        with col1:
            dias = st.slider("Días de anticipación", 1, 30, 7)
        with col2:
            modo_prueba = st.checkbox("Modo prueba (no enviar emails reales)", value=True)
        
        alerts = alert_system.get_alerts(dias)
        
        st.subheader(f"📋 Casos que vencen en {dias} días o menos: {len(alerts)}")
        
        if len(alerts) > 0:
            # Mostrar por equipo
            for team in alerts['TeamOwner'].unique():
                team_cases = alerts[alerts['TeamOwner'] == team]
                with st.expander(f"📧 {team} - {len(team_cases)} casos"):
                    st.dataframe(team_cases[['Case #', 'Case Type', 'Case Status', 'Deadline', 'Days_Until']], use_container_width=True)
                    
                    if st.button(f"Enviar a {team}", key=team):
                        if modo_prueba:
                            st.info(f"[SIMULACIÓN] Correo enviado a {team}")
                            st.session_state.historial.append({
                                'fecha': datetime.now(),
                                'equipo': team,
                                'casos': len(team_cases),
                                'modo': 'prueba'
                            })
                        else:
                            st.success(f"✅ Correo enviado a {team}")
            
            # Resumen
            st.subheader("📊 Resumen por equipo")
            resumen = alerts['TeamOwner'].value_counts().reset_index()
            resumen.columns = ['Equipo', 'Casos Pendientes']
            st.dataframe(resumen, use_container_width=True)
        else:
            st.info("✅ No hay casos que requieran alertas")
    else:
        st.warning("⚠️ Primero procesa los datos")

# ============================================
# 5. HISTORIAL
# ============================================
elif menu == "📜 Historial":
    st.header("📜 Historial de Alertas")
    
    if len(st.session_state.historial) > 0:
        historial_df = pd.DataFrame(st.session_state.historial)
        st.dataframe(historial_df, use_container_width=True)
        
        if st.button("🗑️ Limpiar historial"):
            st.session_state.historial = []
            st.rerun()
    else:
        st.info("No hay alertas enviadas aún")