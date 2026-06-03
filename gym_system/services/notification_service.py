import os
import ssl
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database.models.notifications import Notification
from database.db import db
import pytz
from datetime import datetime
 
BOGOTA = pytz.timezone('America/Bogota')
logger = logging.getLogger(__name__)
 
 
def _send_smtp(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """
    Envía email por SMTP leyendo las variables de entorno en cada llamada
    (no al importar el módulo) para que Render las inyecte correctamente.
    
    Soporta dos modos según MAIL_USE_SSL:
      - False (default): puerto 587 con STARTTLS  → outlook.com / office365
      - True:            puerto 465 con SSL directo → Gmail y otros
    """
    mail_server = os.environ.get('MAIL_SERVER', 'smtp.office365.com')
    mail_port   = int(os.environ.get('MAIL_PORT', 587))
    mail_user   = os.environ.get('MAIL_USERNAME', '').strip()
    mail_pass   = os.environ.get('MAIL_PASSWORD', '').strip()
    mail_from   = os.environ.get('MAIL_FROM', mail_user).strip() or mail_user
    use_ssl     = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
 
    # Guard: sin credenciales no hay nada que hacer
    if not mail_user or not mail_pass:
        msg = 'MAIL_USERNAME o MAIL_PASSWORD vacíos en variables de entorno.'
        logger.error(f'[EMAIL] {msg}')
        return False, msg
 
    try:
        mime = MIMEMultipart('alternative')
        mime['Subject'] = subject
        mime['From']    = mail_from          # igual a la cuenta autenticada
        mime['To']      = to_email
        mime.attach(MIMEText(html_body, 'html', 'utf-8'))
 
        if use_ssl:
            # Puerto 465 — SSL directo (Gmail, etc.)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(mail_server, mail_port, context=context, timeout=20) as server:
                server.login(mail_user, mail_pass)
                server.sendmail(mail_user, to_email, mime.as_string())
        else:
            # Puerto 587 — STARTTLS (Outlook / Office 365)
            with smtplib.SMTP(mail_server, mail_port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(mail_user, mail_pass)
                server.sendmail(mail_user, to_email, mime.as_string())
 
        logger.info(f'[EMAIL OK] {subject} → {to_email}')
        return True, ''
 
    except smtplib.SMTPAuthenticationError as exc:
        err = (
            'Error de autenticación SMTP. '
            'Para Outlook/Hotmail personal debes usar una Contraseña de Aplicación '
            '(Microsoft cuenta → Seguridad → Contraseñas de aplicación). '
            f'Detalle: {str(exc)[:150]}'
        )
        logger.error(f'[EMAIL AUTH] {err}')
        return False, err
 
    except Exception as exc:
        err = str(exc)[:200]
        logger.error(f'[EMAIL ERROR] {subject} → {to_email}: {err}')
        return False, err
 
 
def _log_notification(client_id, channel, message, success, error=''):
    try:
        status = 'enviado' if success else f'error: {error[:100]}'
        notif = Notification(
            client_id=client_id,
            channel=channel,
            message=message[:255],
            status=status,
            sent_at=datetime.now(BOGOTA) if success else None,
        )
        db.session.add(notif)
        db.session.commit()
    except Exception as exc:
        logger.error(f'[EMAIL LOG] No se pudo guardar notificación en BD: {exc}')
        try:
            db.session.rollback()
        except Exception:
            pass
    return success
 
 
# ── Templates ────────────────────────────────────────────────
 
def _base_template(titulo: str, contenido: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">
            <tr><td style="background:#1a1a2e;padding:24px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;letter-spacing:1px;">💪 BODY-FIT GYM</h1>
            </td></tr>
            <tr><td style="background:#e63946;padding:16px 32px;">
              <h2 style="margin:0;color:#ffffff;font-size:18px;">{titulo}</h2>
            </td></tr>
            <tr><td style="padding:32px;">{contenido}</td></tr>
            <tr><td style="background:#f8f8f8;padding:16px 32px;border-top:1px solid #eeeeee;">
              <p style="margin:0;color:#999999;font-size:12px;text-align:center;">
                Este es un mensaje automático de Body-Fit Gym.<br>
                Por favor no respondas a este correo.
              </p>
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
 
 
class NotificationService:
 
    @staticmethod
    def send_welcome(client):
        if not client.email:
            return False
        contenido = f"""
        <p style="color:#333;font-size:16px;">Hola <strong>{client.full_name}</strong>,</p>
        <p style="color:#555;">¡Bienvenido(a) a <strong>Body-Fit Gym</strong>! 🎉</p>
        <p style="color:#555;">Tu registro ha sido completado exitosamente.</p>
        <table style="background:#f8f8f8;border-radius:6px;padding:16px;width:100%;margin:16px 0;">
          <tr><td style="color:#666;padding:4px 0;"><strong>Nombre:</strong></td><td style="color:#333;">{client.full_name}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Documento:</strong></td><td style="color:#333;">{client.document_type} {client.document_number}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Teléfono:</strong></td><td style="color:#333;">{client.phone or '—'}</td></tr>
        </table>
        <p style="color:#555;">Ya puedes acercarte al gimnasio y activar tu membresía. ¡Nos vemos! 💪</p>
        """
        html = _base_template('¡Bienvenido a Body-Fit!', contenido)
        ok, err = _send_smtp(client.email, '¡Bienvenido a Body-Fit Gym! 💪', html)
        return _log_notification(client.id, 'email', f'Bienvenida: {client.full_name}', ok, err)
 
    @staticmethod
    def send_payment_confirmation(payment):
        client = payment.client
        if not client or not client.email:
            return False
        contenido = f"""
        <p style="color:#333;font-size:16px;">Hola <strong>{client.full_name}</strong>,</p>
        <p style="color:#555;">Tu pago ha sido registrado. ¡Tu membresía está activa! ✅</p>
        <table style="background:#f8f8f8;border-radius:6px;padding:16px;width:100%;margin:16px 0;">
          <tr><td style="color:#666;padding:4px 0;"><strong>Plan:</strong></td><td style="color:#333;">{payment.membership.name}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Monto:</strong></td><td style="color:#333;font-weight:bold;">${'{:,.0f}'.format(payment.amount)} COP</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Método:</strong></td><td style="color:#333;">{payment.payment_method}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Válido desde:</strong></td><td style="color:#333;">{payment.start_date.strftime('%d/%m/%Y')}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Vence el:</strong></td><td style="color:#e63946;font-weight:bold;">{payment.end_date.strftime('%d/%m/%Y')}</td></tr>
        </table>
        <p style="color:#555;">¡Entrena duro y alcanza tus metas! 🏋️</p>
        """
        html = _base_template('Pago Confirmado ✅', contenido)
        ok, err = _send_smtp(client.email, f'Pago confirmado — {payment.membership.name}', html)
        return _log_notification(client.id, 'email', f'Pago confirmado: ${payment.amount}', ok, err)
 
    @staticmethod
    def send_expiry_warning(payment, days_left: int):
        client = payment.client
        if not client or not client.email:
            return False
        emoji = '⚠️' if days_left <= 1 else '🔔'
        dias_texto = 'mañana' if days_left == 1 else f'en {days_left} días'
        contenido = f"""
        <p style="color:#333;font-size:16px;">Hola <strong>{client.full_name}</strong>,</p>
        <p style="color:#555;">{emoji} Tu membresía vence <strong>{dias_texto}</strong>.</p>
        <table style="background:#fff3cd;border-radius:6px;padding:16px;width:100%;margin:16px 0;border-left:4px solid #ffc107;">
          <tr><td style="color:#666;padding:4px 0;"><strong>Plan:</strong></td><td style="color:#333;">{payment.membership.name}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Vence el:</strong></td><td style="color:#e63946;font-weight:bold;">{payment.end_date.strftime('%d/%m/%Y')}</td></tr>
        </table>
        <p style="color:#555;">Renueva antes de que venza para no perder días de entrenamiento. 💪</p>
        """
        html = _base_template(f'Tu membresía vence {dias_texto} {emoji}', contenido)
        ok, err = _send_smtp(client.email, f'{emoji} Tu membresía vence {dias_texto} — Body-Fit', html)
        return _log_notification(client.id, 'email', f'Aviso vencimiento: {days_left} días', ok, err)
 
    @staticmethod
    def send_expired_notice(payment):
        client = payment.client
        if not client or not client.email:
            return False
        contenido = f"""
        <p style="color:#333;font-size:16px;">Hola <strong>{client.full_name}</strong>,</p>
        <p style="color:#555;">Tu membresía venció el <strong>{payment.end_date.strftime('%d/%m/%Y')}</strong>. 😢</p>
        <table style="background:#f8d7da;border-radius:6px;padding:16px;width:100%;margin:16px 0;border-left:4px solid #e63946;">
          <tr><td style="color:#666;padding:4px 0;"><strong>Plan:</strong></td><td style="color:#333;">{payment.membership.name}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Venció el:</strong></td><td style="color:#e63946;font-weight:bold;">{payment.end_date.strftime('%d/%m/%Y')}</td></tr>
        </table>
        <p style="color:#555;">¡Te esperamos de vuelta! 💪</p>
        """
        html = _base_template('Tu membresía ha vencido ❌', contenido)
        ok, err = _send_smtp(client.email, '❌ Tu membresía en Body-Fit ha vencido — ¡Renueva!', html)
        return _log_notification(client.id, 'email', f'Membresía expirada: {payment.end_date}', ok, err)
 
    @staticmethod
    def send_password_reset(user):
        contenido = f"""
        <p style="color:#333;">Hola <strong>{user.full_name}</strong>,</p>
        <p style="color:#555;">Recibimos una solicitud para restablecer tu contraseña.</p>
        <p style="color:#555;">Si no la solicitaste, ignora este mensaje.</p>
        <p style="color:#555;">Comunícate con el administrador del sistema para continuar.</p>
        """
        html = _base_template('Recuperación de Contraseña 🔐', contenido)
        ok, err = _send_smtp(user.email, 'Recuperación de contraseña — Body-Fit', html)
        return _log_notification(None, 'email', f'Reset password: {user.email}', ok, err)
 
    @staticmethod
    def send_email(to_email, subject, body, client_id=None):
        html = _base_template(subject, f'<p style="color:#555;">{body}</p>')
        ok, err = _send_smtp(to_email, subject, html)
        return _log_notification(client_id, 'email', subject[:100], ok, err)
 