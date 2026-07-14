"""
Job diario que envía un resumen del día por WhatsApp al dueño a las 10pm hora Bogotá.
Se dispara desde /health (UptimeRobot cada 5 min) pero solo corre una vez por día
después de las 22:00 hora Colombia.
Usa solo memoria — no requiere columnas extra en la BD.
"""
import pytz
import logging
from datetime import datetime, timedelta
from database.models.payment import Payment

BOGOTA  = pytz.timezone('America/Bogota')
HORA_REPORTE = 22   # 10pm
logger = logging.getLogger(__name__)

_last_report_date = None


def _escapar_html(texto):
    return (texto or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def run_daily_report(app):
    global _last_report_date

    with app.app_context():
        now   = datetime.now(BOGOTA)
        today = now.date()
        today_str = str(today)

        # Solo correr después de las 10pm
        if now.hour < HORA_REPORTE:
            return

        # Ya se envió hoy
        if _last_report_date == today_str:
            return

        # ── Calcular datos del día ────────────────────────────────
        try:
            pagos_hoy = Payment.query.filter(
                Payment.payment_date == today,
                Payment.is_deleted   == False,
                Payment.amount       > 0,
            ).all()

            total_dia = sum(p.amount for p in pagos_hoy)
            num_pagos = len(pagos_hoy)

            # Desglose por plan
            planes = {}
            for p in pagos_hoy:
                nombre = p.membership.name if p.membership else 'Otro'
                if nombre not in planes:
                    planes[nombre] = {'cantidad': 0, 'total': 0}
                planes[nombre]['cantidad'] += 1
                planes[nombre]['total']    += p.amount

            # Desglose por método
            from utils.helpers import parse_payment_split
            metodos = {}
            for p in pagos_hoy:
                for method, monto in parse_payment_split(p.payment_method):
                    val = monto if monto is not None else p.amount
                    metodos[method] = metodos.get(method, 0) + val

            # Membresías por vencer en los próximos 3 días
            proximos = Payment.query.filter(
                Payment.end_date  >= today,
                Payment.end_date  <= today + timedelta(days=3),
                Payment.is_deleted == False,
            ).all()

            # ── Armar mensaje ─────────────────────────────────────
            fecha_str = now.strftime('%d/%m/%Y')

            lineas_planes = ''
            for nombre, datos in sorted(planes.items(), key=lambda x: x[1]['cantidad'], reverse=True):
                lineas_planes += f"   - {nombre}: {datos['cantidad']} venta(s) - ${'{:,.0f}'.format(datos['total'])}\n"

            lineas_metodos = ''
            for method, total in sorted(metodos.items(), key=lambda x: x[1], reverse=True):
                lineas_metodos += f"   - {method.capitalize()}: ${'{:,.0f}'.format(total)}\n"

            lineas_vencer = ''
            for p in proximos[:5]:
                dias = (p.end_date - today).days
                label = 'Hoy' if dias == 0 else f'en {dias} dia(s)'
                nombre_c = _escapar_html(p.client.full_name) if p.client else '-'
                lineas_vencer += f"   * {nombre_c} vence {label}\n"
            if not lineas_vencer:
                lineas_vencer = '   OK - Ninguna membresia por vencer\n'

            mensaje = (
                f"🌙 <b>Reporte del día — L-GYM</b>\n"
                f"<i>{fecha_str}</i>\n"
                f"{'─'*22}\n"
                f"💰 <b>Ingresos:</b> <code>${'{:,.0f}'.format(total_dia)} COP</code>\n"
                f"🧾 <b>Pagos registrados:</b> <code>{num_pagos}</code>\n"
                f"{'─'*22}\n"
                f"📋 <b>Por plan</b>\n{lineas_planes}"
                f"{'─'*22}\n"
                f"💳 <b>Por método</b>\n{lineas_metodos}"
                f"{'─'*22}\n"
                f"⏳ <b>Próximos a vencer</b>\n{lineas_vencer}"
                f"{'─'*22}\n"
                f"<i>Generado a las {now.strftime('%H:%M')}</i>"
            )

            from services.notification_service import send_telegram_owner
            import os
            base_url = os.environ.get('RENDER_EXTERNAL_URL') or os.environ.get('APP_BASE_URL', '')
            botones = None
            if base_url:
                botones = [{'texto': '📊 Ver dashboard', 'url': base_url.rstrip('/') + '/'}]
            send_telegram_owner(mensaje, botones=botones)
            logger.info(f'[daily_report] Reporte enviado el {today_str}')

        except Exception as exc:
            logger.error(f'[daily_report] Error generando reporte: {exc}', exc_info=True)
            return

        # Guardar en memoria
        _last_report_date = today_str
