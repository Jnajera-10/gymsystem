"""
Job diario que revisa membresías próximas a vencer o ya vencidas
y envía notificaciones por email.

Se ejecuta automáticamente al recibir GET /health (UptimeRobot lo
llama cada 5 minutos) pero solo corre una vez por día. La fecha de
última ejecución se guarda en memoria (variable de módulo) y también
en GymSettings.notes como fallback persistente entre reinicios.
"""
import pytz
import logging
from datetime import datetime, timedelta
from database.models.payment import Payment
from database.models.settings import GymSettings
from database.db import db

BOGOTA = pytz.timezone('America/Bogota')
WARN_DAYS = [3, 1]   # avisar 3 días antes y 1 día antes
logger = logging.getLogger(__name__)

# Control en memoria para el proceso actual
_last_job_date = None


def run_expiry_notifications(app):
    """Llamar con el app context activo."""
    global _last_job_date

    with app.app_context():
        today = datetime.now(BOGOTA).date()
        today_str = str(today)

        # --- Control de una sola ejecución por día ---
        # 1. Chequeo rápido en memoria (mismo proceso)
        if _last_job_date == today_str:
            return

        # 2. Chequeo persistente en BD (sobrevive reinicios del servidor)
        settings = GymSettings.query.first()
        if settings and settings.notes:
            # Guardamos la fecha en el campo notes con un prefijo especial
            # para no pisar notas del usuario. Si se necesita un campo
            # dedicado, agregar last_notif_run a GymSettings.
            for line in settings.notes.splitlines():
                if line.startswith('_last_notif_run='):
                    saved_date = line.split('=', 1)[1].strip()
                    if saved_date == today_str:
                        _last_job_date = today_str  # sincronizar memoria
                        return

        from services.notification_service import NotificationService

        sent = 0

        # 1. Avisos de vencimiento próximo
        for days in WARN_DAYS:
            target_date = today + timedelta(days=days)
            payments = Payment.query.filter(
                Payment.end_date == target_date,
                Payment.is_deleted == False,
            ).all()
            for p in payments:
                if p.client and p.client.email and p.client.is_active:
                    NotificationService.send_expiry_warning(p, days)
                    sent += 1

        # 2. Avisos de membresía expirada (vencieron ayer)
        yesterday = today - timedelta(days=1)
        expired = Payment.query.filter(
            Payment.end_date == yesterday,
            Payment.is_deleted == False,
        ).all()
        for p in expired:
            if p.client and p.client.email and p.client.is_active:
                NotificationService.send_expired_notice(p)
                sent += 1

        # --- Guardar fecha de última ejecución ---
        _last_job_date = today_str

        if settings:
            # Limpiar líneas _last_notif_run anteriores y agregar la nueva
            existing_lines = [
                line for line in (settings.notes or '').splitlines()
                if not line.startswith('_last_notif_run=')
            ]
            existing_lines.append(f'_last_notif_run={today_str}')
            settings.notes = '\n'.join(existing_lines)
        else:
            settings = GymSettings(notes=f'_last_notif_run={today_str}')
            db.session.add(settings)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f'[expiry_job] No se pudo guardar fecha de ejecución: {e}')

        logger.info(f'[expiry_job] Corrió el {today_str}, {sent} notificaciones enviadas.')
