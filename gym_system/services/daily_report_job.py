"""
Job diario que envía un resumen del día por WhatsApp al dueño a las 10pm hora Bogotá.
Se dispara desde /health (UptimeRobot cada 5 min) pero solo corre una vez por día
después de las 22:00 hora Colombia.
"""
import pytz
import logging
from datetime import datetime, date
from database.models.payment import Payment
from database.models.settings import GymSettings
from database.models.membership import Membership
from database.db import db

BOGOTA  = pytz.timezone('America/Bogota')
HORA_REPORTE = 22   # 10pm
logger = logging.getLogger(__name__)

_last_report_date = None


def run_daily_report(app):
    global _last_report_date

    with app.app_context():
        now   = datetime.now(BOGOTA)
        today = now.date()
        today_str = str(today)

        # Solo correr después de las 10pm
        if now.hour < HORA_REPORTE:
            return

        # Chequeo en memoria
        if _last_report_date == today_str:
            return

        # Chequeo persistente en BD
        settings = GymSettings.query.first()
        if settings and settings.last_report_run == today_str:
            _last_report_date = today_str
            return

        # ── Calcular datos del día ────────────────────────────────
        try:
            pagos_hoy = Payment.query.filter(
                Payment.payment_date == today,
                Payment.is_deleted   == False,
                Payment.amount       > 0,        # excluir espejo plan pareja
            ).all()

            total_dia    = sum(p.amount for p in pagos_hoy)
            num_pagos    = len(pagos_hoy)

            # Desglose por plan
            planes = {}
            for p in pagos_hoy:
                nombre = p.membership.name if p.membership else 'Otro'
                if nombre not in planes:
                    planes[nombre] = {'cantidad': 0, 'total': 0}
                planes[nombre]['cantidad'] += 1
                planes[nombre]['total']    += p.amount

            # Desglose por método de pago
            from utils.helpers import parse_payment_split
            metodos = {}
            for p in pagos_hoy:
                for method, monto in parse_payment_split(p.payment_method):
                    val = monto if monto is not None else p.amount
                    metodos[method] = metodos.get(method, 0) + val

            # Membresías por vencer en los próximos 3 días
            from datetime import timedelta
            proximos = Payment.query.filter(
                Payment.end_date  >= today,
                Payment.end_date  <= today + timedelta(days=3),
                Payment.is_deleted == False,
            ).all()

            # ── Armar mensaje ─────────────────────────────────────
            fecha_str = now.strftime('%d/%m/%Y')

            lineas_planes = ''
            for nombre, datos in sorted(planes.items(), key=lambda x: x[1]['cantidad'], reverse=True):
                lineas_planes += f"   • {nombre}: {datos['cantidad']} venta(s) — ${'{:,.0f}'.format(datos['total'])}\n"

            lineas_metodos = ''
            for method, total in sorted(metodos.items(), key=lambda x: x[1], reverse=True):
                lineas_metodos += f"   • {method.capitalize()}: ${'{:,.0f}'.format(total)}\n"

            lineas_vencer = ''
            for p in proximos[:5]:
                dias = (p.end_date - today).days
                label = 'Hoy' if dias == 0 else f'en {dias} día(s)'
                nombre_c = p.client.full_name if p.client else '—'
                lineas_vencer += f"   ⚠️ {nombre_c} vence {label}\n"
            if not lineas_vencer:
                lineas_vencer = '   ✅ Ninguna membresía por vencer\n'

            mensaje = (
                f"📊 *REPORTE DEL DÍA — BODY-FIT GYM*\n"
                f"📅 {fecha_str}\n"
                f"{'─'*30}\n"
                f"💰 *Total ingresos:* ${'{:,.0f}'.format(total_dia)} COP\n"
                f"🧾 *Pagos registrados:* {num_pagos}\n"
                f"{'─'*30}\n"
                f"📋 *Por plan:*\n{lineas_planes}"
                f"{'─'*30}\n"
                f"💳 *Por método:*\n{lineas_metodos}"
                f"{'─'*30}\n"
                f"⏳ *Próximos a vencer:*\n{lineas_vencer}"
                f"{'─'*30}\n"
                f"🕙 Generado a las {now.strftime('%H:%M')} | Body-Fit 💪"
            )

            from services.notification_service import send_whatsapp_owner
            send_whatsapp_owner(mensaje)
            logger.info(f'[daily_report] Reporte enviado el {today_str}')

        except Exception as exc:
            logger.error(f'[daily_report] Error generando reporte: {exc}', exc_info=True)
            return

        # ── Guardar fecha de ejecución ────────────────────────────
        _last_report_date = today_str
        try:
            if settings:
                settings.last_report_run = today_str
            else:
                settings = GymSettings(last_report_run=today_str)
                db.session.add(settings)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f'[daily_report] No se pudo guardar fecha: {e}')
