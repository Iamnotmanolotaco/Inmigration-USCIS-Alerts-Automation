# st_legal_alert_system.py
# Versión con modo oscuro y paleta de colores mejorada

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
import requests

# ============================================================
# CONFIGURACIÓN
# ============================================================

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

URL_LOGO_GITHUB = "https://raw.githubusercontent.com/Iamnotmanolotaco/Inmigration-USCIS-Alerts-Automation/main/logo.png"
URL_BANNER_GITHUB = "https://raw.githubusercontent.com/Iamnotmanolotaco/Inmigration-USCIS-Alerts-Automation/main/banner.png"

DAYS_BEFORE = 7
DAYS_AFTER = 30

# ============================================================
# FUNCIONES PARA OBTENER RECURSOS DESDE GITHUB
# ============================================================

def get_image_from_github(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            base64_string = base64.b64encode(response.content).decode('utf-8')
            content_type = response.headers.get('Content-Type', 'image/png')
            return f"data:{content_type};base64,{base64_string}"
        else:
            return None
    except Exception as e:
        return None

def get_logo_base64():
    return get_image_from_github(URL_LOGO_GITHUB)

def get_banner_base64():
    return get_image_from_github(URL_BANNER_GITHUB)

# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

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
    }
    return team_emails.get(team_name.strip(), None)

def get_cc_for_team(team_name):
    cc_by_team = {}
    default_cc = ["default_supervisor@communitylawgroup.com"]
    return cc_by_team.get(team_name.strip(), default_cc)

# ============================================================
# FUNCIÓN PARA GENERAR HTML DEL CORREO
# ============================================================

def generar_html_correo(team_cases, team_name, fecha_referencia, logo_base64=None):
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
    
    logo_html = ""
    if logo_base64:
        logo_html = f"""
        <div class="footer-logo">
            <img src="{logo_base64}" alt="Community Law Group" style="max-width: 180px; height: auto; border: none; display: block; margin: 0 auto;">
        </div>
        """
    
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
    resultados = []
    errores = []
    
    if 'TeamOwner' not in df.columns:
        return [], ["❌ Error: La columna 'TeamOwner' no existe en el archivo"]
    
    df['TeamOwner'] = df['TeamOwner'].astype(str).str.strip()
    df['TeamOwner'] = df['TeamOwner'].replace({'KIa': 'Kia', 'kia': 'Kia', 'KIA': 'Kia'})
    
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
    
    alerts_by_team = {}
    for team in df_alerts['TeamOwner'].dropna().unique():
        team_cases = df_alerts[df_alerts['TeamOwner'] == team]
        if len(team_cases) > 0:
            alerts_by_team[team] = team_cases
    
    if not alerts_by_team:
        return [], ["⚠️ No se encontraron equipos con alertas"]
    
    logo_base64 = get_logo_base64()
    
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
            with open(f"preview_{team_name}.html", 'w', encoding='utf-8') as f:
                f.write(html_body)
            resultados.append(f"   📄 Preview guardado: preview_{team_name}.html")
    
    return resultados, errores

# ============================================================
# INTERFAZ STREAMLIT - CON MODO OSCURO Y PALETA MEJORADA
# ============================================================

st.set_page_config(
    page_title="ST LEGAL Alert System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# PALETA DE COLORES (MODO CLARO / OSCURO)
# ============================================================

def get_colors(dark_mode=False):
    if dark_mode:
        return {
            "bg": "#0e1117",
            "card_bg": "#1c1c1e",
            "card_border": "#2c2c2e",
            "text_primary": "#e8edf2",
            "text_secondary": "#9aa4b8",
            "primary": "#4a7c9c",
            "primary_dark": "#1a3a5c",
            "secondary": "#6a9fc7",
            "accent": "#e67e22",
            "urgent": "#e74c3c",
            "success": "#2ecc71",
            "info": "#3498db",
            "warning": "#f39c12",
            "header_bg": "#1a1a1e",
            "banner_grad1": "#1a3a5c",
            "banner_grad2": "#4a7c9c",
            "metric_bg": "#252528",
            "shadow": "rgba(0,0,0,0.4)"
        }
    else:
        return {
            "bg": "#f0f4f8",
            "card_bg": "#ffffff",
            "card_border": "#e8edf2",
            "text_primary": "#1a2a3a",
            "text_secondary": "#4a6a8a",
            "primary": "#1a3a5c",
            "primary_dark": "#0d1f33",
            "secondary": "#4a7c9c",
            "accent": "#e67e22",
            "urgent": "#c0392b",
            "success": "#27ae60",
            "info": "#1e40af",
            "warning": "#e67e22",
            "header_bg": "#ffffff",
            "banner_grad1": "#1a3a5c",
            "banner_grad2": "#4a7c9c",
            "metric_bg": "#f0f4f8",
            "shadow": "rgba(0,0,0,0.08)"
        }

# ============================================================
# INICIALIZAR ESTADO DEL MODO OSCURO
# ============================================================

if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# ============================================================
# BANNER
# ============================================================

banner_base64 = get_banner_base64()
colors = get_colors(st.session_state.dark_mode)

# ============================================================
# CSS DINÁMICO (se adapta al modo oscuro/claro)
# ============================================================

st.markdown(f"""
<style>
    /* Ocultar elementos */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    
    /* Fondo general */
    .stApp {{
        background-color: {colors['bg']};
    }}
    
    /* Tarjetas */
    .card {{
        background-color: {colors['card_bg']};
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 2px 8px {colors['shadow']};
        border: 1px solid {colors['card_border']};
        margin-bottom: 16px;
    }}
    
    .card-title {{
        color: {colors['text_primary']};
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 8px;
    }}
    
    /* Métricas */
    .metric-container {{
        background-color: {colors['metric_bg']};
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
        border: 1px solid {colors['card_border']};
    }}
    
    .metric-value {{
        font-size: 28px;
        font-weight: 700;
        color: {colors['primary']};
    }}
    
    .metric-label {{
        font-size: 12px;
        color: {colors['text_secondary']};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }}
    
    /* Textos */
    .text-primary {{ color: {colors['text_primary']}; }}
    .text-secondary {{ color: {colors['text_secondary']}; }}
    
    /* Badges */
    .badge-active {{
        background-color: rgba(46, 204, 113, 0.15);
        color: {colors['success']};
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid rgba(46, 204, 113, 0.2);
    }}
    
    .badge-urgent {{
        background-color: rgba(192, 57, 43, 0.12);
        color: {colors['urgent']};
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }}
    
    .badge-warning {{
        background-color: rgba(230, 126, 34, 0.12);
        color: {colors['warning']};
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }}
    
    .badge-info {{
        background-color: rgba(52, 152, 219, 0.12);
        color: {colors['info']};
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }}
    
    /* Botones */
    .stButton > button {{
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        border: none !important;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    }}
    
    /* Resultados */
    .result-success {{
        background-color: rgba(46, 204, 113, 0.10);
        border-left: 4px solid {colors['success']};
        padding: 12px 16px;
        border-radius: 4px;
        margin: 4px 0;
        color: {colors['text_primary']};
    }}
    
    .result-error {{
        background-color: rgba(231, 76, 60, 0.10);
        border-left: 4px solid {colors['urgent']};
        padding: 12px 16px;
        border-radius: 4px;
        margin: 4px 0;
        color: {colors['text_primary']};
    }}
    
    .result-info {{
        background-color: rgba(52, 152, 219, 0.10);
        border-left: 4px solid {colors['info']};
        padding: 12px 16px;
        border-radius: 4px;
        margin: 4px 0;
        color: {colors['text_primary']};
    }}
    
    /* Sidebar */
    .css-1d391kg {{
        background-color: {colors['card_bg']} !important;
        border-right: 1px solid {colors['card_border']} !important;
    }}
    
    /* Upload */
    .upload-container {{
        border: 2px dashed {colors['card_border']};
        border-radius: 12px;
        padding: 40px;
        text-align: center;
        background-color: {colors['bg']};
        transition: all 0.3s ease;
    }}
    
    .upload-container:hover {{
        border-color: {colors['secondary']};
        background-color: {colors['metric_bg']};
    }}
    
    /* Footer */
    .footer {{
        text-align: center;
        padding: 16px;
        color: {colors['text_secondary']};
        font-size: 12px;
        border-top: 1px solid {colors['card_border']};
        margin-top: 30px;
    }}
    
    /* Headers */
    h1, h2, h3, h4 {{
        color: {colors['text_primary']} !important;
    }}
    
    /* Labels y texto de Streamlit */
    .stMarkdown, .stText, .stCaption, label {{
        color: {colors['text_secondary']} !important;
    }}
    
    /* Inputs */
    .stTextInput > div > div > input {{
        background-color: {colors['bg']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['card_border']} !important;
    }}
    
    .stDateInput > div > div > input {{
        background-color: {colors['bg']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['card_border']} !important;
    }}
    
    /* Checkbox */
    .stCheckbox label {{
        color: {colors['text_secondary']} !important;
    }}
    
    /* File uploader */
    .stFileUploader > div > button {{
        background-color: {colors['bg']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['card_border']} !important;
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# BANNER CON IMAGEN O RESPALDO
# ============================================================

if banner_base64:
    st.markdown(f"""
    <div style="width: 100%; margin-bottom: 20px; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px {colors['shadow']};">
        <img src="{banner_base64}" alt="ST LEGAL Alert System" style="width: 100%; height: auto; display: block;">
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {colors['banner_grad1']}, {colors['banner_grad2']});
        padding: 35px 45px;
        border-radius: 12px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px {colors['shadow']};
    ">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
            <div>
                <h1 style="color: white; font-size: 30px; font-weight: 700; margin: 0; letter-spacing: -0.5px;">
                    ⚖️ ST LEGAL
                </h1>
                <p style="color: rgba(255,255,255,0.9); font-size: 15px; margin: 4px 0 0 0;">
                    Deadline and Case Management System
                </p>
            </div>
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <span style="
                    background: rgba(255,255,255,0.2);
                    color: white;
                    padding: 6px 18px;
                    border-radius: 30px;
                    font-size: 13px;
                    font-weight: 600;
                ">v1.0</span>
                <span style="
                    background: rgba(46, 204, 113, 0.3);
                    color: #2ecc71;
                    padding: 6px 18px;
                    border-radius: 30px;
                    font-size: 13px;
                    font-weight: 600;
                    border: 1px solid rgba(46, 204, 113, 0.3);
                ">● Active</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# SIDEBAR - CON TOGGLE DE MODO OSCURO
# ============================================================

with st.sidebar:
    st.markdown(f"""
    <div style="text-align: center; padding: 4px 0 12px 0;">
        <div style="font-weight: 700; color: {colors['primary']}; font-size: 20px;">⚖️ ST LEGAL</div>
        <div style="font-size: 11px; color: {colors['text_secondary']}; letter-spacing: 0.5px;">ALERT SYSTEM</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ============================================================
    # Toggle de modo oscuro
    # ============================================================
    dark_mode_toggle = st.toggle("🌙 Modo oscuro", value=st.session_state.dark_mode)
    if dark_mode_toggle != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode_toggle
        st.rerun()
    
    st.markdown("---")
    
    st.markdown("### 📧 Correo")
    smtp_username = st.text_input("Usuario", value="", placeholder="tu@email.com", label_visibility="collapsed")
    st.caption("Correo de Outlook")
    
    smtp_password = st.text_input("Contraseña", type="password", placeholder="••••••••", label_visibility="collapsed")
    st.caption("Contraseña de Outlook")
    
    st.markdown("---")
    
    st.markdown("### 📁 Datos")
    uploaded_file = st.file_uploader("Archivo Excel", type=['xlsx', 'xls'], label_visibility="collapsed")
    st.caption("Carga tu archivo de casos")
    
    st.markdown("---")
    
    st.markdown("### ⚙️ Fecha")
    fecha_referencia = st.date_input("Referencia", value=datetime.now().date(), label_visibility="collapsed")
    
    st.markdown("---")
    
    test_mode = st.checkbox("Modo prueba", help="Envía a un solo correo de prueba")
    test_email = st.text_input("Correo de prueba", placeholder="test@email.com") if test_mode else None
    
    st.markdown("---")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        enviar_reales = st.button("📨 Enviar", type="primary", use_container_width=True)
    with col_btn2:
        simular = st.button("📄 Simular", use_container_width=True)
    
    st.markdown("---")
    st.caption("🔒 TLS seguro · Sin almacenamiento")

# ============================================================
# ÁREA PRINCIPAL
# ============================================================

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    
    # Métricas
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    
    with col_m1:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-value">{len(df)}</div>
            <div class="metric-label">Registros</div>
        </div>
        """, unsafe_allow_html=True)
    
    if 'TeamOwner' in df.columns:
        teams = df['TeamOwner'].dropna().unique()
        with col_m2:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{len(teams)}</div>
                <div class="metric-label">Equipos</div>
            </div>
            """, unsafe_allow_html=True)
    
    if 'Case Status' in df.columns:
        rfe_count = df['Case Status'].astype(str).str.upper().str.contains('RFE', na=False).sum()
        with col_m3:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{rfe_count}</div>
                <div class="metric-label">RFE</div>
            </div>
            """, unsafe_allow_html=True)
    
    if 'Desktime' in df.columns:
        on_time = len(df[df['Desktime'] == 'On time'])
        with col_m4:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{on_time}</div>
                <div class="metric-label">On Time</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Vista previa
    with st.expander("👁️ Vista previa de datos"):
        st.dataframe(df.head(10), use_container_width=True)
    
    # Procesar
    if enviar_reales or simular:
        if enviar_reales and (not smtp_username or not smtp_password):
            st.error("⚠️ Ingresa tus credenciales de Outlook para enviar correos reales")
        else:
            with st.spinner("⏳ Procesando alertas..."):
                resultados, errores = procesar_alertas(
                    df, fecha_referencia, smtp_username, smtp_password,
                    test_email, enviar_reales
                )
            
            st.markdown("---")
            st.markdown("### 📋 Resultados")
            
            if errores:
                for err in errores:
                    st.markdown(f'<div class="result-error">{err}</div>', unsafe_allow_html=True)
            
            if resultados:
                for res in resultados:
                    if res.startswith("✅"):
                        st.markdown(f'<div class="result-success">{res}</div>', unsafe_allow_html=True)
                    elif res.startswith("❌"):
                        st.markdown(f'<div class="result-error">{res}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="result-info">{res}</div>', unsafe_allow_html=True)
            
            if enviar_reales and not errores:
                st.balloons()
                st.success("🎉 Proceso completado exitosamente")

else:
    st.markdown(f"""
    <div style="
        text-align: center;
        padding: 80px 30px;
        background-color: {colors['card_bg']};
        border-radius: 12px;
        border: 1px solid {colors['card_border']};
    ">
        <div style="font-size: 64px; margin-bottom: 20px;">📂</div>
        <h2 style="color: {colors['text_primary']}; font-weight: 600; margin: 0;">Carga tu archivo Excel</h2>
        <p style="color: {colors['text_secondary']}; margin: 8px 0 0 0;">
            Sube un archivo con los casos para generar alertas de vencimiento
        </p>
        <div style="margin-top: 16px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
            <span style="background: {colors['metric_bg']}; padding: 4px 16px; border-radius: 20px; font-size: 12px; color: {colors['text_secondary']};">TeamOwner</span>
            <span style="background: {colors['metric_bg']}; padding: 4px 16px; border-radius: 20px; font-size: 12px; color: {colors['text_secondary']};">Deadline</span>
            <span style="background: {colors['metric_bg']}; padding: 4px 16px; border-radius: 20px; font-size: 12px; color: {colors['text_secondary']};">Case Status</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.markdown(f"""
<div class="footer">
    ST LEGAL Alert System · Data &amp; Efficiency Team
    <br>
    © {datetime.now().year} Community Law Group
</div>
""", unsafe_allow_html=True)
