import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import base64
from datetime import datetime, timedelta
import os
import json
import re
import requests  # Necesario para descargar la imagen desde GitHub

# ============================================================
# CONFIGURACIÓN
# ============================================================

# Configuración SMTP de Outlook
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

# URL del logo en GitHub (¡CAMBIA ESTA URL POR LA TUYA!)
URL_LOGO_GITHUB = "https://raw.githubusercontent.com/Iamnotmanolotaco/Inmigration-USCIS-Alerts-Automation/main/image.png"

DAYS_BEFORE = 7
DAYS_AFTER = 30

# ============================================================
# FUNCIÓN PARA OBTENER LOGO DESDE GITHUB
# ============================================================

def get_logo_from_github(url):
    """
    Descarga la imagen desde una URL de GitHub y la convierte a Base64.
    """
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            base64_string = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/png;base64,{base64_string}"
        else:
            st.error(f"No se pudo descargar el logo (código {response.status_code})")
    except Exception as e:
        st.error(f"Error al descargar el logo: {e}")
    return None

# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def formatear_mes(numero_mes):
    meses = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
             5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
             9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}
    return meses[numero_mes]

def calcular_dias_hasta_deadline(deadline_str, fecha_referencia):
    if pd.isna(deadline_str) or deadline_str == "":
        return None
    try:
        if isinstance(deadline_str, (datetime, pd.Timestamp)):
            deadline_date = deadline_str.date()
        else:
            deadline_date = pd.to_datetime(deadline_str).date()
        return (deadline_date - fecha_referencia).days
    except:
        return None

def is_rfe_case(case_status):
    if pd.isna(case_status):
        return False
    rfe_patterns = [
        'RFE_RECEIVED', 'RFE_RESPONSE_SENT', 'RFE SENT',
        'RFE RECEIVED', 'RFE RESPONSE SENT', 'RFE_RESPONSE',
        'RFE PENDING', 'RFE ISSUED', 'RFE RESPONSE RECEIVED'
    ]
    status_str = str(case_status).strip().upper()
    for pattern in rfe_patterns:
        if pattern.upper().replace('_', ' ') in status_str or pattern in status_str:
            return True
    return False

def get_days_style(days):
    if days <= 0:
        return "days-critical", f"{abs(days)} days overdue"
    elif days <= 2:
        return "days-critical", f"{days} days"
    elif days <= 5:
        return "days-warning", f"{days} days"
    else:
        return "days-info", f"{days} days"

def get_team_email(team_name):
    team_emails = {
        "Kia": "dataprojects@communitylawgroup.com",
        # Agregar más equipos según necesidad
    }
    return team_emails.get(team_name.strip(), None)

def get_cc_for_team(team_name):
    cc_by_team = {
        # "Kia": ["cc1@email.com", "cc2@email.com"],
    }
    default_cc = ["default_supervisor@communitylawgroup.com"]
    return cc_by_team.get(team_name.strip(), default_cc)

# ============================================================
# FUNCIÓN PARA GENERAR HTML DEL CORREO
# ============================================================

def generar_html_correo(team_cases, team_name, fecha_referencia, logo_base64=None):
    """Genera el HTML del correo con los casos"""
    
    # Filtrar RFE
    is_rfe = pd.Series([False] * len(team_cases), index=team_cases.index)
    if 'Case Status' in team_cases.columns:
        for idx, status in team_cases['Case Status'].items():
            if is_rfe_case(status):
                is_rfe.iloc[idx] = True
    
    team_cases_filtered = team_cases[~is_rfe].copy()
    
    if len(team_cases_filtered) == 0:
        return None
    
    team_cases_filtered['Days_Until'] = team_cases_filtered['Deadline'].apply(
        lambda x: calcular_dias_hasta_deadline(x, fecha_referencia)
    )
    
    overdue = team_cases_filtered[team_cases_filtered['Days_Until'] < 0].sort_values('Days_Until')
    upcoming = team_cases_filtered[team_cases_filtered['Days_Until'] >= 0].sort_values('Days_Until')
    
    total_cases = len(team_cases_filtered)
    urgent_count = len(overdue)
    upcoming_count = len(upcoming)
    
    rfe_excluded = is_rfe.sum()
    
    # Logo HTML
    logo_html = ""
    if logo_base64:
        logo_html = f"""
        <div class="footer-logo">
            <img src="{logo_base64}" alt="Community Law Group" style="max-width: 180px; height: auto; border: none; display: block; margin: 0 auto;">
        </div>
        """
    
    # Generar HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #e8eef2; padding: 20px; }}
            .email-container {{ max-width: 1100px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .email-header {{ background-color: #f0f4f8; padding: 28px 36px; border-bottom: 2px solid #d0d8e4; }}
            .logo {{ font-size: 28px; font-weight: 700; color: #1a2a3a; }}
            .logo span {{ font-weight: 400; color: #3a5a7a; }}
            .report-subtitle {{ font-size: 15px; color: #3a5a7a; margin-top: 6px; }}
            .greeting {{ background-color: #f8fafc; padding: 24px 36px; border-bottom: 1px solid #e2e8f0; }}
            .greeting h2 {{ font-size: 20px; font-weight: 600; color: #1a2a3a; margin-bottom: 8px; }}
            .greeting p {{ font-size: 14px; color: #4a6a8a; }}
            .urgent-alert {{ background-color: #c0392b; color: #ffffff; padding: 16px 24px; margin: 20px 36px 0 36px; border-radius: 10px; display: flex; align-items: center; gap: 15px; flex-wrap: wrap; }}
            .urgent-alert-icon {{ font-size: 32px; font-weight: 700; }}
            .urgent-alert-text {{ flex: 1; }}
            .urgent-alert-text h3 {{ font-size: 18px; font-weight: 700; }}
            .urgent-count {{ background-color: rgba(255,255,255,0.25); padding: 6px 16px; border-radius: 30px; font-size: 24px; font-weight: 700; }}
            .report-info {{ padding: 18px 36px; background-color: #ffffff; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 20px; }}
            .info-grid {{ display: flex; gap: 28px; flex-wrap: wrap; }}
            .info-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #6a7e9e; }}
            .info-value {{ font-size: 14px; font-weight: 500; color: #1a2a3a; }}
            .recipient-badge {{ background-color: #1a3a5c; color: #ffffff; padding: 6px 16px; border-radius: 30px; font-size: 13px; font-weight: 600; }}
            .stats-title {{ padding: 20px 36px 0 36px; }}
            .stats-title h3 {{ font-size: 16px; font-weight: 600; color: #1a2a3a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
            .stats-container {{ padding: 0 36px 28px 36px; }}
            .stats-grid {{ display: flex; gap: 20px; flex-wrap: wrap; }}
            .stat-card {{ background-color: #f8fafc; padding: 22px 28px; border-radius: 12px; border: 1px solid #e2e8f0; min-width: 160px; }}
            .stat-number {{ font-size: 36px; font-weight: 700; }}
            .stat-label {{ font-size: 12px; font-weight: 600; color: #6a7e9e; text-transform: uppercase; }}
            .text-urgent {{ color: #c0392b; }}
            .text-warning {{ color: #e67e22; }}
            .table-section {{ margin: 28px 36px; }}
            .section-header {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }}
            .section-title {{ font-size: 17px; font-weight: 700; color: #1a2a3a; }}
            .section-badge {{ background-color: #e8eef2; color: #3a5a7a; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
            .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }}
            .data-table th {{ background-color: #f0f4f8; color: #1a2a3a; font-weight: 700; padding: 12px 14px; text-align: left; border-bottom: 2px solid #e2e8f0; }}
            .data-table td {{ padding: 12px 14px; border-bottom: 1px solid #eef2f6; color: #2a3a4a; }}
            .data-table tr:last-child td {{ border-bottom: none; }}
            .days-critical {{ color: #c0392b; background-color: #fee2e2; padding: 4px 12px; border-radius: 20px; font-weight: 700; }}
            .days-warning {{ color: #92400e; background-color: #fef3c7; padding: 4px 12px; border-radius: 20px; font-weight: 700; }}
            .days-info {{ color: #1e40af; background-color: #dbeafe; padding: 4px 12px; border-radius: 20px; font-weight: 700; }}
            .rfe-note {{ background-color: #fef3c7; border-left: 4px solid #e67e22; padding: 12px 20px; margin: 20px 36px; border-radius: 8px; font-size: 12px; color: #92400e; }}
            .email-footer {{ background-color: #f0f4f8; padding: 20px 36px; border-top: 1px solid #e2e8f0; text-align: center; margin-top: 20px; }}
            .footer-text {{ font-size: 11px; color: #6a7e9e; margin-bottom: 5px; }}
            .footer-note {{ font-size: 10px; color: #8a9eb8; }}
            .footer-logo {{ margin: 10px 0 8px 0; }}
            @media (max-width: 700px) {{
                .email-header, .greeting, .report-info, .stats-title, .stats-container, .table-section, .email-footer {{
                    padding-left: 20px; padding-right: 20px;
                }}
                .urgent-alert {{ margin-left: 20px; margin-right: 20px; }}
                .stats-grid {{ gap: 12px; }}
                .stat-card {{ padding: 16px 20px; min-width: 130px; }}
                .data-table th, .data-table td {{ padding: 8px 10px; font-size: 11px; }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <div class="logo">LEGAL SUPPORT TEAM <span>ALERTING SYSTEM</span></div>
                <div class="report-subtitle">Deadline and Case Management System</div>
            </div>
            <div class="greeting">
                <h2>Hello, {team_name}</h2>
                <p>Below are the cases assigned to your team that require attention. Please review the information and take necessary actions.</p>
            </div>
    """
    
    if len(overdue) > 0:
        html += f"""
            <div class="urgent-alert">
                <div class="urgent-alert-icon">⚠️</div>
                <div class="urgent-alert-text">
                    <h3>PRIORITY ATTENTION REQUIRED</h3>
                    <p>There {'is' if len(overdue) == 1 else 'are'} {len(overdue)} case(s) that have passed their deadline.</p>
                </div>
                <div class="urgent-count">{len(overdue)}</div>
            </div>
        """
    
    html += f"""
            <div class="report-info">
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">DATE</span>
                        <span class="info-value">{fecha_referencia.strftime('%m/%d/%Y')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">ALERT PERIOD</span>
                        <span class="info-value">Next {DAYS_BEFORE} days</span>
                    </div>
                </div>
                <div class="recipient-badge">Responsible: {team_name}</div>
            </div>
            <div class="stats-title"><h3>Case Summary</h3></div>
            <div class="stats-container">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number"><strong>{total_cases}</strong></div>
                        <div class="stat-label">Total Cases</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number"><strong class="text-urgent">{urgent_count}</strong></div>
                        <div class="stat-label">Overdue Cases</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number"><strong class="text-warning">{upcoming_count}</strong></div>
                        <div class="stat-label">Upcoming Deadline</div>
                    </div>
                </div>
            </div>
    """
    
    if len(overdue) > 0:
        html += f"""
            <div class="table-section">
                <div class="section-header">
                    <div class="section-title">OVERDUE CASES</div>
                    <div class="section-badge">{len(overdue)} cases</div>
                </div>
                <table class="data-table">
                    <thead><tr><th>Case ID</th><th>Case Type</th><th>Current Status</th><th>Deadline</th><th>Status</th><th>Office</th></tr></thead>
                    <tbody>
        """
        for _, row in overdue.iterrows():
            days_overdue = abs(row['Days_Until'])
            style_class, days_text = get_days_style(-days_overdue)
            html += f"""
                <tr>
                    <td><strong>{row.get('Case #', 'N/A')}</strong></td>
                    <td>{row.get('Case Type', 'N/A')}</td>
                    <td>{row.get('Case Status', 'N/A')}</td>
                    <td>{row.get('Deadline', 'N/A')}</td>
                    <td><span class="{style_class}">{days_text}</span></td>
                    <td>{row.get('Office Name', 'N/A')}</td>
                </tr>
            """
        html += "</tbody></table></div>"
    
    if len(upcoming) > 0:
        html += f"""
            <div class="table-section">
                <div class="section-header">
                    <div class="section-title">UPCOMING DEADLINE CASES</div>
                    <div class="section-badge">{len(upcoming)} cases</div>
                </div>
                <table class="data-table">
                    <thead><tr><th>Case ID</th><th>Case Type</th><th>Current Status</th><th>Deadline</th><th>Days Remaining</th><th>Office</th></tr></thead>
                    <tbody>
        """
        for _, row in upcoming.iterrows():
            days_left = row['Days_Until']
            style_class, days_text = get_days_style(days_left)
            html += f"""
                <tr>
                    <td><strong>{row.get('Case #', 'N/A')}</strong></td>
                    <td>{row.get('Case Type', 'N/A')}</td>
                    <td>{row.get('Case Status', 'N/A')}</td>
                    <td>{row.get('Deadline', 'N/A')}</td>
                    <td><span class="{style_class}">{days_text}</span></td>
                    <td>{row.get('Office Name', 'N/A')}</td>
                </tr>
            """
        html += "</tbody></table></div>"
    
    if rfe_excluded > 0:
        html += f"""
            <div class="rfe-note">
                ℹ️ <strong>Note:</strong> {rfe_excluded} case(s) with RFE status have been excluded from this report.
            </div>
        """
    
    html += f"""
            <div class="email-footer">
                <div class="footer-text">Legal Support Team Alerting System - Automatically generated</div>
                {logo_html}
                <div class="footer-note">© {fecha_referencia.year} Community Law Group · All rights reserved</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

# ============================================================
# FUNCIÓN PARA ENVIAR CORREO VÍA SMTP
# ============================================================

def enviar_correo_smtp(smtp_server, smtp_port, username, password, to_emails, cc_emails,
                       subject, html_body, sender_name="Legal Support Team"):
    """Envía correo usando SMTP de Outlook"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = username
        msg['To'] = ", ".join(to_emails)
        if cc_emails:
            msg['CC'] = ", ".join(cc_emails)
        msg['X-Priority'] = '1'
        
        msg.attach(MIMEText(html_body, 'html'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(username, password)
            
            all_recipients = to_emails + (cc_emails if cc_emails else [])
            server.sendmail(username, all_recipients, msg.as_string())
        
        return True, "Correo enviado exitosamente"
    except Exception as e:
        return False, f"Error al enviar: {str(e)}"

# ============================================================
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# ============================================================

def procesar_alertas(df, fecha_referencia, smtp_username, smtp_password, 
                     test_email=None, enviar_reales=False):
    """Procesa las alertas y envía correos"""
    
    resultados = []
    errores = []
    
    # Validar columnas
    if 'TeamOwner' not in df.columns:
        return [], ["❌ Error: La columna 'TeamOwner' no existe en el archivo"]
    
    df['TeamOwner'] = df['TeamOwner'].astype(str).str.strip()
    df['TeamOwner'] = df['TeamOwner'].replace({'KIa': 'Kia', 'kia': 'Kia', 'KIA': 'Kia'})
    
    # Filtrar por fechas
    df_temp = df.copy()
    
    if 'Deadline' not in df_temp.columns:
        return [], ["❌ Error: La columna 'Deadline' no existe en el archivo"]
    
    df_temp['Days_Until'] = df_temp['Deadline'].apply(
        lambda x: calcular_dias_hasta_deadline(x, fecha_referencia)
    )
    
    mask_upcoming = (df_temp['Days_Until'] >= 0) & (df_temp['Days_Until'] <= DAYS_BEFORE)
    mask_overdue = (df_temp['Days_Until'] < 0) & (df_temp['Days_Until'] >= -DAYS_AFTER)
    df_alerts = df_temp[mask_upcoming | mask_overdue].copy()
    
    if len(df_alerts) == 0:
        return [], ["⚠️ No hay casos que requieran alerta en el período seleccionado"]
    
    # Agrupar por equipo
    alerts_by_team = {}
    for team in df_alerts['TeamOwner'].dropna().unique():
        team_cases = df_alerts[df_alerts['TeamOwner'] == team]
        if len(team_cases) > 0:
            alerts_by_team[team] = team_cases
    
    if not alerts_by_team:
        return [], ["⚠️ No se encontraron equipos con alertas"]
    
    # ============================================================
    # Cargar logo desde GitHub (REEMPLAZA LA CARGA LOCAL)
    # ============================================================
    logo_base64 = get_logo_from_github(URL_LOGO_GITHUB)
    
    # Procesar cada equipo
    for team_name, team_cases in alerts_by_team.items():
        html_body = generar_html_correo(team_cases, team_name, fecha_referencia, logo_base64)
        
        if html_body is None:
            resultados.append(f"⏭️ {team_name}: Todos los casos son RFE - omitido")
            continue
        
        if test_email:
            to_email = [test_email]
            cc_email = []
            subject = f"[TEST] ST LEGAL - Case Report - {team_name} - {fecha_referencia.strftime('%m/%d/%Y')}"
        else:
            to_email = [get_team_email(team_name)] if get_team_email(team_name) else []
            cc_email = get_cc_for_team(team_name)
            subject = f"ST LEGAL - Case Deadline Report - {team_name} - {fecha_referencia.strftime('%m/%d/%Y')}"
        
        if not to_email:
            resultados.append(f"❌ {team_name}: No hay email configurado")
            continue
        
        if enviar_reales and smtp_username and smtp_password:
            success, msg = enviar_correo_smtp(
                SMTP_SERVER, SMTP_PORT,
                smtp_username, smtp_password,
                to_email, cc_email,
                subject, html_body
            )
            if success:
                resultados.append(f"✅ {team_name}: Enviado a {', '.join(to_email)}")
            else:
                errores.append(f"❌ {team_name}: {msg}")
        else:
            resultados.append(f"📄 {team_name}: Correo listo (modo simulación)")
            # Guardar preview
            with open(f"preview_{team_name}.html", 'w', encoding='utf-8') as f:
                f.write(html_body)
            resultados.append(f"   📄 Preview guardado: preview_{team_name}.html")
    
    return resultados, errores

# ============================================================
# INTERFAZ STREAMLIT
# ============================================================

st.set_page_config(page_title="ST LEGAL Alert System", page_icon="⚖️", layout="wide")

st.title("⚖️ ST LEGAL - Alert System (Cloud Version)")
st.markdown("---")

# Sidebar con configuración
with st.sidebar:
    st.header("📧 Configuración SMTP")
    st.markdown("Ingresa tus credenciales de Outlook para enviar correos")
    
    smtp_username = st.text_input("Correo de Outlook", value="", placeholder="tu@email.com")
    smtp_password = st.text_input("Contraseña", type="password", placeholder="Contraseña de Outlook")
    
    st.markdown("---")
    st.header("📁 Archivo de Datos")
    uploaded_file = st.file_uploader("Carga el archivo Excel", type=['xlsx', 'xls'])
    
    st.markdown("---")
    st.header("⚙️ Configuración")
    fecha_referencia = st.date_input("Fecha de referencia", value=datetime.now().date())
    
    test_mode = st.checkbox("Modo prueba (enviar a un solo correo)")
    test_email = st.text_input("Correo de prueba") if test_mode else None
    
    st.markdown("---")
    enviar_reales = st.button("📨 Enviar Correos Reales", type="primary")
    simular = st.button("📄 Solo Simulación (sin enviar)")

# Área principal
col1, col2 = st.columns([2, 1])

with col1:
    if uploaded_file is not None:
        st.success(f"✅ Archivo cargado: {uploaded_file.name}")
        
        df = pd.read_excel(uploaded_file)
        st.info(f"📊 Registros cargados: {len(df)}")
        
        with st.expander("👁️ Vista previa de datos"):
            st.dataframe(df.head(10))
        
        if enviar_reales or simular:
            if enviar_reales and (not smtp_username or not smtp_password):
                st.error("❌ Por favor ingresa tus credenciales de Outlook para enviar correos reales")
            else:
                with st.spinner("Procesando alertas..."):
                    resultados, errores = procesar_alertas(
                        df, fecha_referencia, smtp_username, smtp_password,
                        test_email, enviar_reales
                    )
                
                st.markdown("---")
                st.subheader("📋 Resultados")
                
                if errores:
                    for err in errores:
                        st.error(err)
                
                for res in resultados:
                    if res.startswith("✅"):
                        st.success(res)
                    elif res.startswith("❌"):
                        st.error(res)
                    else:
                        st.info(res)
    else:
        st.info("📌 Carga un archivo Excel en la barra lateral para comenzar")

with col2:
    st.markdown("""
    ### 📋 Instrucciones
    
    1. **Configura tu correo** en la barra lateral
    2. **Carga el archivo Excel** con los datos
    3. **Selecciona la fecha de referencia**
    4. **Simula** para probar sin enviar
    5. **Envía** para enviar correos reales
    
    ### 📌 Columnas requeridas en el Excel
    - `TeamOwner`
    - `Deadline`
    - `Case #`
    - `Case Type`
    - `Case Status`
    - `Office Name`
    
    ### 🔒 Seguridad
    - Las credenciales no se guardan
    - La conexión SMTP usa TLS
    - Solo se usa durante la sesión
    """)

st.markdown("---")
st.caption("ST LEGAL Alert System - Versión Cloud | Desarrollado por Data & Efficiency Team")
