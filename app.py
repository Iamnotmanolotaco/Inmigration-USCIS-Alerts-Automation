import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
# FUNCIÓN PARA ENVIAR CORREOS REALES
# ============================================
def enviar_correo_real(destinatario, asunto, cuerpo_html, smtp_config):
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_config['sender']
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo_html, 'html'))
        
        server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
        server.starttls()
        server.login(smtp_config['sender'], smtp_config['password'])
        server.send_message(msg)
        server.quit()
        return True, "Correo enviado exitosamente"
    except Exception as e:
        return False, str(e)

def generar_cuerpo_correo(team_name, team_cases, days_before):
    today = datetime.now()
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background-color: #1a3a5c; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th {{ background-color: #2a5a8c; color: white; padding: 10px; text-align: left; }}
            td {{ border: 1px solid #ddd; padding: 8px; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .urgent {{ color: #c0392b; font-weight: bold; }}
            .warning {{ color: #e67e22; font-weight: bold; }}
            .footer {{ font-size: 11px; color: gray; text-align: center; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>ST LEGAL AUTOMATED</h2>
            <p>Sistema de Alertas de Casos</p>
        </div>
        <div class="content">
            <h3>Hola, {team_name}</h3>
            <p>Tienes <strong>{len(team_cases)} casos</strong> que requieren atención en los próximos {days_before} días.</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Case #</th>
                        <th>Case Type</th>
                        <th>Case Status</th>
                        <th>Deadline</th>
                        <th>Desktime</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for _, row in team_cases.iterrows():
        desktime = row.get('Desktime', 'N/A')
        color_class = 'urgent' if desktime == 'Out of Desktime' else 'warning' if desktime == 'On time' else ''
        html += f"""
                    <tr>
                        <td>{row.get('Case #', 'N/A')}</td>
                        <td>{row.get('Case Type', 'N/A')}</td>
                        <td>{row.get('Case Status', 'N/A')}</td>
                        <td>{row.get('Deadline', 'N/A')}</td>
                        <td class="{color_class}">{desktime}</td>
                    </tr>
        """
    
    html += f"""
                </tbody>
            </table>
            <p style="margin-top: 20px;">Por favor revisa estos casos y toma las acciones necesarias.</p>
        </div>
        <div class="footer">
            <p>ST LEGAL Automated System - Reporte generado automáticamente</p>
            <p>© {today.year} ST LEGAL - Todos los derechos reservados</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================
# CLASE PROCESAR CASES
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
if 'team_emails' not in st.session_state:
    st.session_state.team_emails = {}

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
# SIDEBAR - MENÚ PRINCIPAL Y CONFIGURACIÓN DE CORREO
# ============================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/law.png", width=80)
    st.markdown("---")
    
    menu = st.radio(
        "📋 MENÚ",
        ["📊 Dashboard", "📁 1. Cargar Datos", "⚙️ 2. Procesar Datos", "📧 3. Enviar Alertas", "📜 Historial"]
    )
    
    st.markdown("---")
    
    # CONFIGURACIÓN DE CORREO
    st.subheader("📧 Configuración de Correo")
    
    usar_correos_reales = st.checkbox("✅ Enviar correos REALES", value=False)
    
    smtp_config = {
        'server': None,
        'port': None,
        'sender': None,
        'password': None
    }
    
    if usar_correos_reales:
        st.warning("⚠️ Configura tu correo para enviar emails reales")
        smtp_config['server'] = st.text_input("Servidor SMTP", value="smtp.office365.com")
        smtp_config['port'] = st.number_input("Puerto SMTP", value=587)
        smtp_config['sender'] = st.text_input("Email remitente", value="alerts@stlegal.com")
        smtp_config['password'] = st.text_input("Contraseña", type="password")
        
        if smtp_config['sender'] and smtp_config['password']:
            st.success("✅ Configuración de correo lista")
        else:
            st.error("❌ Completa la configuración de correo")
    else:
        st.info("ℹ️ Modo simulación - No se enviarán correos reales")
    
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
# 3. PROCESAR DATOS
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
                    
                    # MOSTRAR LOS TEAMOWNER REALES
                    if 'TeamOwner' in df_procesado.columns:
                        st.subheader("📊 Equipos encontrados (TeamOwner)")
                        equipos_reales = df_procesado['TeamOwner'].dropna().unique()
                        st.write(f"**Equipos:** {', '.join(equipos_reales)}")
                        
                        # Distribución
                        team_counts = df_procesado['TeamOwner'].value_counts()
                        st.dataframe(team_counts.reset_index().rename(columns={'index': 'TeamOwner', 'TeamOwner': 'Cantidad'}), use_container_width=True)
                    
                    st.subheader("Vista previa de datos procesados:")
                    st.dataframe(df_procesado.head(10), use_container_width=True)
                    
                    st.subheader("Columnas agregadas por el procesamiento:")
                    nuevas = ['Case #', 'TeamOwner', 'Desktime']
                    for col in nuevas:
                        if col in df_procesado.columns:
                            st.write(f"✅ `{col}` - Agregada correctamente")
                    
                    # CONFIGURAR EMAILS POR TEAMOWNER REAL
                    st.subheader("📧 Configuración de emails por equipo")
                    st.info("Ingresa los correos electrónicos para cada TeamOwner")
                    
                    equipos_reales = df_procesado['TeamOwner'].dropna().unique()
                    for equipo in equipos_reales:
                        email_key = f"email_{equipo.replace(' ', '_').replace('#', '')}"
                        st.session_state.team_emails[equipo] = st.text_input(
                            f"Email para {equipo}", 
                            value=st.session_state.team_emails.get(equipo, ""),
                            key=email_key,
                            placeholder=f"correo@{equipo.replace(' ', '').lower()}.com"
                        )
                    
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
            st.write("")
            st.write("")
            enviar_reales = st.checkbox("📧 ENVIAR CORREOS REALES", value=False)
        
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
                    
                    email_destino = st.session_state.team_emails.get(team, "")
                    if email_destino:
                        st.info(f"📧 Email configurado: {email_destino}")
                    else:
                        st.warning(f"⚠️ No hay email configurado para {team}. Ve a 'Procesar Datos' y configura los emails.")
                    
                    if st.button(f"Enviar alerta a {team}", key=f"btn_{team}"):
                        if enviar_reales:
                            if email_destino:
                                if usar_correos_reales and smtp_config['sender'] and smtp_config['password']:
                                    cuerpo = generar_cuerpo_correo(team, team_cases, days_before)
                                    success, mensaje = enviar_correo_real(
                                        email_destino,
                                        f"ST LEGAL - Alerta de Casos - {team} - {datetime.now().strftime('%d/%m/%Y')}",
                                        cuerpo,
                                        smtp_config
                                    )
                                    if success:
                                        st.success(f"✅ Correo REAL enviado a {team} ({email_destino})")
                                        st.session_state.alert_history.append({
                                            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'equipo': team,
                                            'email': email_destino,
                                            'casos': len(team_cases),
                                            'modo': 'REAL'
                                        })
                                    else:
                                        st.error(f"❌ Error al enviar: {mensaje}")
                                else:
                                    st.error("❌ Configura el correo en el panel lateral (sidebar)")
                            else:
                                st.error(f"❌ No hay email configurado para {team}")
                        else:
                            st.info(f"[SIMULACIÓN] Correo enviado a {team} ({email_destino if email_destino else 'sin email configurado'})")
                            st.session_state.alert_history.append({
                                'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'equipo': team,
                                'email': email_destino if email_destino else 'no configurado',
                                'casos': len(team_cases),
                                'modo': 'SIMULACIÓN'
                            })
            
            st.markdown("---")
            st.subheader("📊 Resumen por equipo")
            resumen = alert_df['TeamOwner'].value_counts().reset_index()
            resumen.columns = ['Equipo', 'Casos Pendientes']
            resumen['Email'] = resumen['Equipo'].map(lambda x: st.session_state.team_emails.get(x, "No configurado"))
            st.dataframe(resumen, use_container_width=True)
            
            if st.button("📧 Enviar alertas a TODOS los equipos", type="primary"):
                for team, team_cases in alerts_by_team.items():
                    email_destino = st.session_state.team_emails.get(team, "")
                    if enviar_reales:
                        if email_destino and usar_correos_reales and smtp_config['sender'] and smtp_config['password']:
                            cuerpo = generar_cuerpo_correo(team, team_cases, days_before)
                            success, _ = enviar_correo_real(
                                email_destino,
                                f"ST LEGAL - Alerta de Casos - {team} - {datetime.now().strftime('%d/%m/%Y')}",
                                cuerpo,
                                smtp_config
                            )
                            if success:
                                st.success(f"✅ Enviado a {team}")
                            else:
                                st.error(f"❌ Error con {team}")
                        else:
                            st.warning(f"⚠️ No se pudo enviar a {team} - falta configuración")
                    else:
                        st.info(f"[SIMULACIÓN] Enviado a {team}")
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
        
        st.subheader("📊 Estadísticas de envíos")
        col1, col2 = st.columns(2)
        with col1:
            total_envios = len(historial_df)
            st.metric("Total de envíos", total_envios)
        with col2:
            reales = len(historial_df[historial_df['modo'] == 'REAL']) if 'modo' in historial_df.columns else 0
            st.metric("Correos reales enviados", reales)
        
        if st.button("🗑️ Limpiar historial"):
            st.session_state.alert_history = []
            st.rerun()
    else:
        st.info("No hay alertas en el historial aún")
