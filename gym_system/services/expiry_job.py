"""
Job diario que revisa membresías próximas a vencer o ya vencidas
y envía notificaciones por email.

Se ejecuta automáticamente al recibir GET /health (UptimeRobot lo
llama cada 5 minutos) pero solo corre una vez por día. La fecha de
última ejecución se guarda en GymSettings.last_notif_run (campo
dedicado, sin tocar ningún campo de notas).
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

        # 1. Chequeo rápido en memoria (mismo proceso, mismo worker)
        if _last_job_date == today_str:
            return

        # 2. Chequeo persistente en BD (sobrevive reinicios del servidor)
        settings = GymSettings.query.first()
        if settings and settings.last_notif_run == today_str:
            _last_job_date = today_str  # sincronizar memoria
            return

        # ---------- Ejecutar el job ----------
        from services.notification_service import NotificationService

        sent = 0

        # Avisos de vencimiento próximo
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

        # Avisos de membresía expirada (vencieron ayer)
        yesterday = today - timedelta(days=1)
        expired = Payment.query.filter(
            Payment.end_date == yesterday,
            Payment.is_deleted == False,
        ).all()
        for p in expired:
            if p.client and p.client.email and p.client.is_active:
                NotificationService.send_expired_notice(p)
                sent += 1

        # ---------- Guardar fecha de ejecución ----------
        _last_job_date = today_str

        try:
            if settings:
                settings.last_notif_run = today_str
            else:
                settings = GymSettings(last_notif_run=today_str)
                db.session.add(settings)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f'[expiry_job] No se pudo guardar fecha de ejecución: {e}')

        logger.info(f'[expiry_job] Corrió el {today_str}, {sent} notificaciones enviadas.')
