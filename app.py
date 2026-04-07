import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import plotly.express as px

# ============================================
# CONFIGURACIÓN DE LA PÁGINA
# ============================================
st.set_page_config(
    page_title="ST LEGAL AUTOMATED",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a3a5c, #2a5a8c);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    .metric-card {
        background-color: #f8fafc;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    .urgent {
        color: #c0392b;
        font-weight: bold;
    }
    .warning {
        color: #e67e22;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# CLASE PROCESAR CASES (con soporte para archivo de mapeo)
# ============================================
class CaseProcessor:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.keep_columns = [
            "Case Created Date", "Office Name", "Case Type", "Case Status",
            "Case Number", "Deadline", "Deadline Status",
            "TeamOwner", "Case #", "Desktime"
        ]
    
    def clean_column_names(self):
        self.df.columns = self.df.columns.str.strip()
    
    def filter_columns(self):
        existing_cols = [col for col in self.keep_columns if col in self.df.columns]
        self.df = self.df[existing_cols]
        return existing_cols
    
    def add_case_hash_column(self):
        def first_digit_run(text):
            if pd.isna(text):
                return ""
            match = re.search(r'\d+', str(text))
            return match.group(0) if match else ""
        
        if "Case Number" in self.df.columns:
            self.df["Case #"] = self.df["Case Number"].apply(first_digit_run)
            return True
        return False
    
    def add_desktime_column(self):
        if "Deadline" in self.df.columns:
            today = datetime.now().date()
            def calc_desktime(deadline):
                if pd.isna(deadline) or deadline == "":
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
            return True
        return False
    
    def load_team_mapping_from_file(self, mapping_file):
        """Carga el mapeo desde archivo Excel (como VLOOKUP original)"""
        try:
            df_mapping = pd.read_excel(mapping_file)
            if len(df_mapping.columns) >= 2:
                mapping = dict(zip(
                    df_mapping.iloc[:, 0].astype(str).str.strip(),
                    df_mapping.iloc[:, 1].astype(str).str.strip()
                ))
                return mapping
            return None
        except Exception as e:
            st.error(f"Error al cargar archivo de mapeo: {e}")
            return None
    
    def get_auto_mapping(self):
        """Mapeo automático por palabras clave (fallback)"""
        unique_types = self.df["Case Type"].dropna().unique()
        mapping = {}
        for ct in unique_types:
            ct_str = str(ct).lower()
            if "adjustment" in ct_str or "aos" in ct_str:
                mapping[ct] = "Team AOS"
            elif "naturalization" in ct_str or "n400" in ct_str:
                mapping[ct] = "Team Naturalization"
            elif "consular" in ct_str:
                mapping[ct] = "Team Consular"
            elif "rfe" in ct_str:
                mapping[ct] = "Team RFE"
            elif "interview" in ct_str:
                mapping[ct] = "Team Interviews"
            else:
                mapping[ct] = "Team General"
        return mapping
    
    def add_team_owner_column(self, mapping_file=None):
        """Agrega TeamOwner usando archivo de mapeo o automático"""
        if "Case Type" not in self.df.columns:
            return False
        
        if mapping_file is not None:
            team_mapping = self.load_team_mapping_from_file(mapping_file)
            if team_mapping:
                self.df["TeamOwner"] = self.df["Case Type"].astype(str).str.strip().map(team_mapping)
                null_count = self.df["TeamOwner"].isna().sum()
                if null_count > 0:
                    st.warning(f"⚠️ {null_count} casos sin mapeo. Usando mapeo automático para esos.")
                    auto_mapping = self.get_auto_mapping()
                    mask_null = self.df["TeamOwner"].isna()
                    self.df.loc[mask_null, "TeamOwner"] = self.df.loc[mask_null, "Case Type"].map(auto_mapping)
                return True
        
        # Fallback: mapeo automático
        auto_mapping = self.get_auto_mapping()
        self.df["TeamOwner"] = self.df["Case Type"].map(auto_mapping)
        return True
    
    def filter_by_status(self):
        if "Case Status" in self.df.columns and "Deadline Status" in self.df.columns:
            rfe_mask = self.df["Case Status"].astype(str).str.upper().str.contains('RFE', na=False)
            self.df = self.df[rfe_mask | (self.df["Deadline Status"] != "SATISFIED")]
            return True
        return False
    
    def remove_duplicates(self):
        if "Case Type" in self.df.columns and "Case #" in self.df.columns:
            before = len(self.df)
            self.df = self.df.drop_duplicates(subset=["Case Type", "Case #"], keep='first')
            return before - len(self.df)
        return 0
    
    def reorder_columns(self):
        final_order = [
            "Case Created Date", "Office Name", "Case Type", "TeamOwner", "Case Status",
            "Case Number", "Case #", "Deadline", "Desktime", "Deadline Status"
        ]
        existing_order = [col for col in final_order if col in self.df.columns]
        self.df = self.df[existing_order]
    
    def process(self, mapping_file=None):
        self.clean_column_names()
        self.filter_columns()
        self.add_case_hash_column()
        self.add_desktime_column()
        self.add_team_owner_column(mapping_file)
        self.filter_by_status()
        dups = self.remove_duplicates()
        self.reorder_columns()
        return self.df, dups

# ============================================
# CLASE SISTEMA ALARMAS
# ============================================
class AlertSystem:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.today = datetime.now().date()
    
    def calculate_days_until_deadline(self, deadline_str):
        if pd.isna(deadline_str) or deadline_str == "":
            return None
        try:
            if isinstance(deadline_str, (datetime, pd.Timestamp)):
                deadline_date = deadline_str.date()
            else:
                deadline_date = pd.to_datetime(deadline_str).date()
            return (deadline_date - self.today).days
        except:
            return None
    
    def get_alerts_by_team(self, days_before=7, days_after=3):
        df_alerts = self.df.copy()
        df_alerts['Days_Until'] = df_alerts['Deadline'].apply(self.calculate_days_until_deadline)
        
        mask_upcoming = (df_alerts['Days_Until'] >= 0) & (df_alerts['Days_Until'] <= days_before)
        mask_overdue = (df_alerts['Days_Until'] < 0) & (df_alerts['Days_Until'] >= -days_after)
        
        df_alerts = df_alerts[mask_upcoming | mask_overdue].copy()
        
        alerts_by_team = {}
        if 'TeamOwner' in df_alerts.columns:
            for team in df_alerts['TeamOwner'].dropna().unique():
                team_cases = df_alerts[df_alerts['TeamOwner'] == team]
                if len(team_cases) > 0:
                    alerts_by_team[team] = team_cases
        
        return alerts_by_team, df_alerts
    
    def get_summary_stats(self):
        total = len(self.df)
        overdue = len(self.df[self.df['Desktime'] == "Out of Desktime"]) if 'Desktime' in self.df.columns else 0
        upcoming = len(self.df[self.df['Desktime'] == "On time"]) if 'Desktime' in self.df.columns else 0
        
        return {
            'total': total,
            'overdue': overdue,
            'upcoming': upcoming
        }

# ============================================
# INICIALIZAR SESSION STATE
# ============================================
if 'df_procesado' not in st.session_state:
    st.session_state.df_procesado = None
if 'df_original' not in st.session_state:
    st.session_state.df_original = None
if 'procesado' not in st.session_state:
    st.session_state.procesado = False
if 'alert_history' not in st.session_state:
    st.session_state.alert_history = []

# ============================================
# HEADER PRINCIPAL
# ============================================
st.markdown("""
<div class="main-header">
    <h1>⚖️ ST LEGAL AUTOMATED</h1>
    <p>Sistema de Procesamiento y Alertas de Casos</p>
</div>
""", unsafe_allow_html=True)

# ============================================
# SIDEBAR - MENÚ PRINCIPAL
# ============================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/law.png", width=80)
    st.markdown("---")
    
    menu = st.radio(
        "📋 MENÚ",
        ["📊 Dashboard", "📁 1. Cargar Datos", "⚙️ 2. Procesar Datos", "📧 3. Enviar Alertas", "📜 Historial"]
    )
    
    st.markdown("---")
    st.caption(f"Versión: 3.0.0\n{datetime.now().strftime('%d/%m/%Y')}")

# ============================================
# 1. DASHBOARD
# ============================================
if menu == "📊 Dashboard":
    st.header("📊 Dashboard de Casos")
    
    if st.session_state.df_procesado is not None:
        df = st.session_state.df_procesado
        alert_system = AlertSystem(df)
        stats = alert_system.get_summary_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 Total Casos", stats['total'])
        with col2:
            st.metric("⚠️ Casos Vencidos", stats['overdue'], delta="URGENTE" if stats['overdue'] > 0 else None, delta_color="inverse")
        with col3:
            st.metric("📅 Próximos a Vencer", stats['upcoming'])
        with col4:
            teams = df['TeamOwner'].nunique() if 'TeamOwner' in df.columns else 0
            st.metric("👥 Equipos", teams)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Casos por Equipo")
            if 'TeamOwner' in df.columns:
                team_counts = df['TeamOwner'].value_counts()
                fig = px.bar(x=team_counts.index, y=team_counts.values, color_discrete_sequence=['#1a3a5c'])
                fig.update_layout(showlegend=False, xaxis_title="Equipo", yaxis_title="Número de Casos")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Estado de Plazos")
            if 'Desktime' in df.columns:
                desktime_counts = df['Desktime'].value_counts()
                fig = px.pie(values=desktime_counts.values, names=desktime_counts.index, color_discrete_sequence=['#27ae60', '#e67e22', '#c0392b'])
                st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("🚨 Casos Prioritarios")
        alerts_by_team, alert_df = alert_system.get_alerts_by_team()
        
        if len(alert_df) > 0:
            display_cols = ['Case #', 'Case Type', 'Case Status', 'Deadline', 'TeamOwner', 'Desktime']
            existing_cols = [col for col in display_cols if col in alert_df.columns]
            st.dataframe(alert_df[existing_cols], use_container_width=True)
        else:
            st.info("✅ No hay casos prioritarios en este momento")
        
        with st.expander("📋 Ver todos los casos procesados"):
            st.dataframe(df, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel Procesado", data=output.getvalue(), file_name="ST_LEGAL_Procesado.xlsx")
        
    else:
        st.info("👈 Ve a 'Cargar Datos' y luego 'Procesar Datos' para comenzar")

# ============================================
# 2. CARGAR DATOS
# ============================================
elif menu == "📁 1. Cargar Datos":
    st.header("📁 Cargar Archivo Original")
    st.markdown("Sube el archivo **Case_Details.xlsx** (sin procesar)")
    
    archivo = st.file_uploader("Selecciona tu archivo Excel", type=['xlsx', 'xls'])
    
    if archivo is not None:
        try:
            df = pd.read_excel(archivo, header=2)
            st.session_state.df_original = df
            st.session_state.procesado = False
            
            st.success(f"✅ Archivo cargado exitosamente!")
            st.info(f"📊 {df.shape[0]} filas, {df.shape[1]} columnas")
            
            st.subheader("Vista previa de los datos originales:")
            st.dataframe(df.head(10), use_container_width=True)
            
            st.subheader("Columnas encontradas:")
            st.write(list(df.columns))
            
        except Exception as e:
            st.error(f"Error al cargar: {e}")

# ============================================
# 3. PROCESAR DATOS (CON SOPORTE PARA ARCHIVO DE MAPEO)
# ============================================
elif menu == "⚙️ 2. Procesar Datos":
    st.header("⚙️ Procesar Datos")
    st.markdown("Aplica el mismo procesamiento que hace **procesar_cases.py**")
    
    if st.session_state.df_original is not None:
        st.subheader("📋 Configuración de TeamOwner")
        
        usar_mapeo = st.radio(
            "¿Cómo quieres asignar los TeamOwner?",
            ["Usar archivo de mapeo (Listados de Casos.xlsx)", "Usar mapeo automático por palabras clave"]
        )
        
        mapping_file = None
        if usar_mapeo == "Usar archivo de mapeo (Listados de Casos.xlsx)":
            mapping_upload = st.file_uploader(
                "Sube el archivo 'Listados de Casos.xlsx'",
                type=['xlsx', 'xls'],
                key="mapping_upload"
            )
            if mapping_upload:
                mapping_file = mapping_upload
                st.success("✅ Archivo de mapeo cargado")
                df_map = pd.read_excel(mapping_file)
                st.subheader("Vista previa del mapeo:")
                st.dataframe(df_map.head(10), use_container_width=True)
            else:
                st.warning("⚠️ Por favor sube el archivo de mapeo o cambia a modo automático")
        
        if st.button("🚀 EJECUTAR PROCESAMIENTO", type="primary", use_container_width=True):
            with st.spinner("Procesando datos... Esto puede tomar unos segundos"):
                try:
                    processor = CaseProcessor(st.session_state.df_original.copy())
                    
                    if usar_mapeo == "Usar archivo de mapeo (Listados de Casos.xlsx)":
                        if mapping_file:
                            df_procesado, dups = processor.process(mapping_file)
                        else:
                            st.error("❌ No se ha cargado el archivo de mapeo")
                            st.stop()
                    else:
                        df_procesado, dups = processor.process(None)
                    
                    st.session_state.df_procesado = df_procesado
                    st.session_state.procesado = True
                    
                    st.success("✅ Datos procesados exitosamente!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Filas originales", len(st.session_state.df_original))
                    with col2:
                        st.metric("Filas procesadas", len(df_procesado))
                    with col3:
                        st.metric("Duplicados eliminados", dups)
                    
                    if 'TeamOwner' in df_procesado.columns:
                        st.subheader("📊 Distribución de TeamOwner")
                        team_counts = df_procesado['TeamOwner'].value_counts()
                        st.dataframe(team_counts.reset_index().rename(columns={'index': 'TeamOwner', 'TeamOwner': 'Cantidad'}), use_container_width=True)
                    
                    st.subheader("Vista previa de datos procesados:")
                    st.dataframe(df_procesado.head(10), use_container_width=True)
                    
                    st.subheader("Columnas agregadas por el procesamiento:")
                    nuevas = ['Case #', 'TeamOwner', 'Desktime']
                    for col in nuevas:
                        if col in df_procesado.columns:
                            st.write(f"✅ `{col}` - Agregada correctamente")
                    
                except Exception as e:
                    st.error(f"Error durante el procesamiento: {e}")
    else:
        st.warning("⚠️ Primero carga un archivo en 'Cargar Datos'")

# ============================================
# 4. ENVIAR ALERTAS
# ============================================
elif menu == "📧 3. Enviar Alertas":
    st.header("📧 Sistema de Alertas")
    st.markdown("Genera alertas basadas en el archivo procesado")
    
    if st.session_state.df_procesado is not None:
        df = st.session_state.df_procesado
        alert_system = AlertSystem(df)
        stats = alert_system.get_summary_stats()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            days_before = st.slider("Días antes del vencimiento", 1, 30, 7)
        with col2:
            days_after = st.slider("Días después del vencimiento", 0, 30, 3)
        with col3:
            test_mode = st.checkbox("Modo prueba (solo simular)", value=True)
        
        st.markdown("---")
        
        st.subheader("📊 Estadísticas actuales")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total casos", stats['total'])
        with col2:
            st.metric("Vencidos", stats['overdue'], delta="URGENTE" if stats['overdue'] > 0 else None)
        with col3:
            st.metric("Próximos", stats['upcoming'])
        
        alerts_by_team, alert_df = alert_system.get_alerts_by_team(days_before, days_after)
        
        st.markdown("---")
        st.subheader(f"📋 Casos que requieren atención: {len(alert_df)}")
        
        if len(alert_df) > 0:
            for team, team_cases in alerts_by_team.items():
                with st.expander(f"📧 {team} - {len(team_cases)} casos pendientes"):
                    display_df = team_cases[['Case #', 'Case Type', 'Case Status', 'Deadline', 'Desktime']].copy()
                    st.dataframe(display_df, use_container_width=True)
                    
                    if st.button(f"Enviar alerta a {team}", key=f"btn_{team}"):
                        if test_mode:
                            st.info(f"[SIMULACIÓN] Correo enviado a {team}")
                            st.session_state.alert_history.append({
                                'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'equipo': team,
                                'casos': len(team_cases),
                                'modo': 'prueba'
                            })
                        else:
                            st.success(f"✅ Alerta enviada a {team}")
                            st.session_state.alert_history.append({
                                'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'equipo': team,
                                'casos': len(team_cases),
                                'modo': 'producción'
                            })
            
            st.markdown("---")
            st.subheader("📊 Resumen por equipo")
            resumen = alert_df['TeamOwner'].value_counts().reset_index()
            resumen.columns = ['Equipo', 'Casos Pendientes']
            st.dataframe(resumen, use_container_width=True)
            
            if st.button("📧 Enviar alertas a TODOS los equipos", type="primary"):
                for team in alerts_by_team.keys():
                    if test_mode:
                        st.info(f"[SIMULACIÓN] Correo enviado a {team}")
                    else:
                        st.success(f"✅ Alerta enviada a {team}")
                st.success("Proceso completado")
                
        else:
            st.info("✅ No hay casos que requieran alertas en este momento")
    else:
        st.warning("⚠️ Primero carga y procesa los datos")

# ============================================
# 5. HISTORIAL
# ============================================
elif menu == "📜 Historial":
    st.header("📜 Historial de Alertas")
    
    if len(st.session_state.alert_history) > 0:
        historial_df = pd.DataFrame(st.session_state.alert_history)
        st.dataframe(historial_df, use_container_width=True)
        
        if st.button("🗑️ Limpiar historial"):
            st.session_state.alert_history = []
            st.rerun()
    else:
        st.info("No hay alertas en el historial aún")
