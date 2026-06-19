import os
import requests
import logging
from database.models.notifications import Notification
from database.db import db
import pytz
from datetime import datetime

BOGOTA = pytz.timezone('America/Bogota')
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
#  WHATSAPP — Twilio Sandbox
# ══════════════════════════════════════════════════════════════════

def send_whatsapp_owner(mensaje: str) -> bool:
    """
    Envía un mensaje de WhatsApp al dueño del gym via CallMeBot (gratis, sin límite).
    Requiere variables de entorno:
        CALLMEBOT_PHONE    (ej. 573006855353)
        CALLMEBOT_APIKEY   (ej. 9315615)
    """
    phone  = os.environ.get('CALLMEBOT_PHONE', '').strip()
    apikey = os.environ.get('CALLMEBOT_APIKEY', '').strip()

    if not all([phone, apikey]):
        print('[WHATSAPP] Variables CALLMEBOT_PHONE o CALLMEBOT_APIKEY no configuradas.')
        return False

    try:
        import urllib.parse
        texto_encoded = urllib.parse.quote(mensaje)
        url = f'https://api.callmebot.com/whatsapp.php?phone={phone}&text={texto_encoded}&apikey={apikey}'
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f'[WHATSAPP OK] Mensaje enviado via CallMeBot a {phone}')
            return True
        else:
            print(f'[WHATSAPP ERROR] {response.status_code}: {response.text[:200]}')
            return False
    except Exception as exc:
        print(f'[WHATSAPP ERROR] {exc}')
        return False


def _send_brevo(to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """
    Envía email usando la API HTTP de Brevo (antes Sendinblue).
    Funciona desde Render free porque usa HTTPS, no SMTP.
    """
    api_key = os.environ.get('BREVO_API_KEY', '').strip()
    mail_from = os.environ.get('MAIL_FROM', '').strip()
    mail_name = os.environ.get('MAIL_FROM_NAME', 'Body-Fit Gym').strip()

    if not api_key:
        msg = 'BREVO_API_KEY vacía en variables de entorno.'
        print("[LOG-ERROR]", f'[EMAIL] {msg}')
        return False, msg

    if not mail_from:
        msg = 'MAIL_FROM vacío en variables de entorno.'
        print("[LOG-ERROR]", f'[EMAIL] {msg}')
        return False, msg

    payload = {
        'sender': {'name': mail_name, 'email': mail_from},
        'to': [{'email': to_email}],
        'subject': subject,
        'htmlContent': html_body,
    }

    try:
        response = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            json=payload,
            headers={
                'api-key': api_key,
                'Content-Type': 'application/json',
            },
            timeout=15,
        )
        if response.status_code in (200, 201):
            print("[LOG-INFO]", f'[EMAIL OK] {subject} → {to_email}')
            return True, ''
        else:
            err = response.text[:200]
            print("[LOG-ERROR]", f'[EMAIL ERROR] {response.status_code} → {err}')
            return False, err
    except Exception as exc:
        err = str(exc)[:200]
        print("[LOG-ERROR]", f'[EMAIL ERROR] {subject} → {to_email}: {err}')
        return False, err


def send_email_raw(to_email: str, subject: str, html_body: str,
                   attachment: bytes = None, attach_name: str = None):
    """
    Envía un correo directo (sin crear notificación en BD) con soporte
    de adjunto binario (ej. PDF de cierre de caja).
    Usa la API de Brevo con el campo 'attachment' en base64.
    Lanza excepción si falla.
    """
    import base64
    api_key   = os.environ.get('BREVO_API_KEY', '').strip()
    mail_from = os.environ.get('MAIL_FROM', '').strip()
    mail_name = os.environ.get('MAIL_FROM_NAME', 'Body-Fit Gym').strip()

    if not api_key or not mail_from:
        raise ValueError('BREVO_API_KEY o MAIL_FROM no configurados.')

    payload = {
        'sender':      {'name': mail_name, 'email': mail_from},
        'to':          [{'email': to_email}],
        'subject':     subject,
        'htmlContent': html_body,
    }

    if attachment and attach_name:
        payload['attachment'] = [{
            'name':    attach_name,
            'content': base64.b64encode(attachment).decode('utf-8'),
        }]

    response = requests.post(
        'https://api.brevo.com/v3/smtp/email',
        json    = payload,
        headers = {'api-key': api_key, 'Content-Type': 'application/json'},
        timeout = 20,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f'Brevo error {response.status_code}: {response.text[:200]}')
    print("[LOG-INFO]", f'[EMAIL OK con adjunto] {subject} → {to_email}')


def _log_notification(client_id, channel, message, success, error=''):
    try:
        status = 'enviado' if success else 'error'
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
        print("[LOG-ERROR]", f'[EMAIL LOG] No se pudo guardar notificación en BD: {exc}')
        try:
            db.session.rollback()
        except Exception:
            pass
    return success


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
        ok, err = _send_brevo(client.email, '¡Bienvenido a Body-Fit Gym! 💪', html)
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
        ok, err = _send_brevo(client.email, f'Pago confirmado — {payment.membership.name}', html)
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
        ok, err = _send_brevo(client.email, f'{emoji} Tu membresía vence {dias_texto} — Body-Fit', html)
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
        ok, err = _send_brevo(client.email, '❌ Tu membresía en Body-Fit ha vencido — ¡Renueva!', html)
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
        ok, err = _send_brevo(user.email, 'Recuperación de contraseña — Body-Fit', html)
        return _log_notification(None, 'email', f'Reset password: {user.email}', ok, err)

    @staticmethod
    def send_email(to_email, subject, body, client_id=None):
        html = _base_template(subject, f'<p style="color:#555;">{body}</p>')
        ok, err = _send_brevo(to_email, subject, html)
        return _log_notification(client_id, 'email', subject[:100], ok, err)


    @staticmethod
    def send_couple_plan_notification(partner_payment, main_client):
        """
        Notifica al segundo cliente del Plan Pareja que su membresía
        fue activada porque el cliente principal hizo el pago.
        """
        partner = partner_payment.client
        if not partner or not partner.email:
            return False
        contenido = f"""
        <p style="color:#333;font-size:16px;">Hola <strong>{partner.full_name}</strong>,</p>
        <p style="color:#555;">
          ¡Buenas noticias! <strong>{main_client.full_name}</strong> registró un
          <strong>Plan Pareja</strong> y tu membresía ha sido activada también. 🎉
        </p>
        <table style="background:#f8f8f8;border-radius:6px;padding:16px;width:100%;margin:16px 0;">
          <tr><td style="color:#666;padding:4px 0;"><strong>Plan:</strong></td><td style="color:#333;">{partner_payment.membership.name}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Válido desde:</strong></td><td style="color:#333;">{partner_payment.start_date.strftime('%d/%m/%Y')}</td></tr>
          <tr><td style="color:#666;padding:4px 0;"><strong>Vence el:</strong></td><td style="color:#e63946;font-weight:bold;">{partner_payment.end_date.strftime('%d/%m/%Y')}</td></tr>
        </table>
        <p style="color:#555;">¡Nos vemos en el gym! 💪</p>
        """
        html = _base_template('¡Tu Plan Pareja está activo! 💑', contenido)
        ok, err = _send_brevo(partner.email, '💑 Tu Plan Pareja en Body-Fit está activo', html)
        return _log_notification(partner.id, 'email', 'Plan Pareja activado', ok, err)
