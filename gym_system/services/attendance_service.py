import html
import logging
import threading
from datetime import datetime, timedelta

import pytz

from database.models.attendance import Attendance
from database.models.notifications import Notification
from database.models.payment import Payment
from database.db import db

BOGOTA = pytz.timezone('America/Bogota')
logger = logging.getLogger(__name__)

# Si el mismo cliente congelado intenta marcar varias veces (ej. el kiosco
# facial reintenta cada pocos segundos), solo se avisa al admin una vez
# dentro de esta ventana para no llenarle el Telegram de mensajes repetidos.
FROZEN_ALERT_COOLDOWN_MIN = 30
_FROZEN_ALERT_TAG = '❄️ Asistencia congelado'


class AttendanceService:
    @staticmethod
    def register(client_id, notes=None):
        record = Attendance(client_id=client_id, notes=notes)
        db.session.add(record)
        db.session.commit()
        return record

    @staticmethod
    def today():
        today = datetime.now(BOGOTA).date()
        return Attendance.query.filter(
            db.func.date(Attendance.check_in) == today
        ).all()

    # ──────────────────────────────────────────────────────────────
    #  Membresía congelada: aviso al admin
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_frozen_payment(client_id):
        """Retorna el pago congelado vigente del cliente (o None)."""
        return (
            Payment.query
            .filter(
                Payment.client_id == client_id,
                Payment.is_deleted == False,
                Payment.is_frozen == True,
            )
            .order_by(Payment.id.desc())
            .first()
        )

    @staticmethod
    def notify_frozen_attempt(client, payment, source='manual', registered_by=None):
        """
        Avisa al admin (Telegram) que un cliente con la membresía congelada
        está intentando registrar asistencia.

        - Nunca lanza excepción ni bloquea el check-in: cualquier error
          solo se registra en el log.
        - El envío a Telegram se hace en un hilo aparte para no demorar
          la pantalla de recepción / kiosco.
        - Anti-spam: un solo aviso por cliente cada FROZEN_ALERT_COOLDOWN_MIN
          minutos.

        Retorna True si se disparó un aviso, False si se omitió.
        """
        try:
            from flask import current_app

            desde = datetime.now(BOGOTA) - timedelta(minutes=FROZEN_ALERT_COOLDOWN_MIN)
            reciente = Notification.query.filter(
                Notification.client_id == client.id,
                Notification.channel == 'telegram',
                Notification.message.like(f'{_FROZEN_ALERT_TAG}%'),
                Notification.created_at >= desde,
            ).first()
            if reciente:
                return False

            now = datetime.now(BOGOTA)
            today = now.date()
            dias = max((today - payment.frozen_at).days, 0) if payment.frozen_at else 0
            origen = 'Reconocimiento facial' if source == 'facial' else 'Registro manual'
            esc = html.escape

            lineas = [
                '❄️ <b>BODY-FIT GYM - Cliente congelado en recepción</b>',
                '-' * 28,
                f'👤 <b>Cliente:</b> {esc(client.full_name)}',
                f'🪪 <b>Documento:</b> {esc(str(client.document_type or ""))} {esc(str(client.document_number or ""))}',
                f'📋 <b>Plan:</b> {esc(payment.membership.name) if payment.membership else "-"}',
                f'❄️ <b>Congelada desde:</b> {payment.frozen_at.strftime("%d/%m/%Y") if payment.frozen_at else "-"} ({dias} día(s))',
                f'⏳ <b>Vence (sin contar congelado):</b> {payment.end_date.strftime("%d/%m/%Y")}',
                f'📲 <b>Origen:</b> {origen}',
            ]
            if registered_by:
                lineas.append(f'🧑‍💼 <b>Recepción:</b> {esc(str(registered_by))}')
            lineas += [
                f'🕑 <b>Hora:</b> {now.strftime("%H:%M")}',
                '-' * 28,
                '⚠️ Intentó marcar asistencia con la membresía congelada.',
            ]
            mensaje = '\n'.join(lineas)

            # Se guarda primero (sirve de anti-spam y de historial); el
            # estado se actualiza cuando termina el envío.
            notif = Notification(
                client_id=client.id,
                channel='telegram',
                message=f'{_FROZEN_ALERT_TAG}: {client.full_name}'[:255],
                status='pendiente',
            )
            db.session.add(notif)
            db.session.commit()
            notif_id = notif.id

            app = current_app._get_current_object()
            threading.Thread(
                target=AttendanceService._send_frozen_alert,
                args=(app, notif_id, mensaje),
                daemon=True,
            ).start()
            return True
        except Exception as exc:
            logger.error(f'[ASISTENCIA] No se pudo avisar de cliente congelado: {exc}')
            try:
                db.session.rollback()
            except Exception:
                pass
            return False

    @staticmethod
    def _send_frozen_alert(app, notif_id, mensaje):
        from services.notification_service import send_telegram_owner
        try:
            ok = send_telegram_owner(mensaje)
        except Exception as exc:
            logger.error(f'[ASISTENCIA] Error enviando aviso a Telegram: {exc}')
            ok = False
        try:
            with app.app_context():
                n = Notification.query.get(notif_id)
                if n:
                    n.status = 'enviado' if ok else 'error'
                    n.sent_at = datetime.now(BOGOTA) if ok else None
                    db.session.commit()
        except Exception as exc:
            logger.error(f'[ASISTENCIA] No se pudo actualizar estado de notificación: {exc}')
