"""
Webhook de Telegram — permite que el dueño le escriba al bot (ej. /resumen)
y reciba al instante el corte del día, en vez de esperar al reporte
automático de las 10pm (services/daily_report_job.py).

Reutiliza las mismas variables de entorno que ya usa notification_service.py:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID   (chat autorizado — solo él puede usar el bot)
"""
import os
import requests
import pytz
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app

from database.models.payment import Payment
from utils.helpers import parse_payment_split

BOGOTA = pytz.timezone('America/Bogota')
telegram_bp = Blueprint('telegram', __name__)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
AUTHORIZED_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()


def _enviar_mensaje(chat_id, texto):
    if not BOT_TOKEN:
        current_app.logger.error('[telegram_webhook] TELEGRAM_BOT_TOKEN no configurado.')
        return
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    try:
        requests.post(
            url,
            json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML',
                  'disable_web_page_preview': True},
            timeout=15,
        )
    except Exception as exc:
        current_app.logger.error(f'[telegram_webhook] error enviando mensaje: {exc}')


def _resumen_del_dia():
    """Arma el mismo tipo de resumen que el reporte de las 10pm, pero al momento."""
    now = datetime.now(BOGOTA)
    hoy = now.date()

    pagos_hoy = Payment.query.filter(
        Payment.payment_date == hoy,
        Payment.is_deleted == False,
        Payment.amount > 0,
    ).all()

    total_dia = sum(p.amount for p in pagos_hoy)
    num_pagos = len(pagos_hoy)

    planes = {}
    for p in pagos_hoy:
        nombre = p.membership.name if p.membership else 'Otro'
        planes.setdefault(nombre, {'cantidad': 0, 'total': 0})
        planes[nombre]['cantidad'] += 1
        planes[nombre]['total'] += p.amount

    metodos = {}
    for p in pagos_hoy:
        for method, monto in parse_payment_split(p.payment_method):
            val = monto if monto is not None else p.amount
            metodos[method] = metodos.get(method, 0) + val

    proximos = Payment.query.filter(
        Payment.end_date >= hoy,
        Payment.end_date <= hoy + timedelta(days=3),
        Payment.is_deleted == False,
    ).all()

    lineas_planes = ''.join(
        f"   - {nombre}: {d['cantidad']} venta(s) - ${'{:,.0f}'.format(d['total'])}\n"
        for nombre, d in sorted(planes.items(), key=lambda x: x[1]['cantidad'], reverse=True)
    ) or '   Sin ventas todavía\n'

    lineas_metodos = ''.join(
        f"   - {m.capitalize()}: ${'{:,.0f}'.format(t)}\n"
        for m, t in sorted(metodos.items(), key=lambda x: x[1], reverse=True)
    ) or '   -\n'

    lineas_vencer = ''
    for p in proximos[:5]:
        dias = (p.end_date - hoy).days
        label = 'Hoy' if dias == 0 else f'en {dias} dia(s)'
        nombre_c = (p.client.full_name if p.client else '-')
        lineas_vencer += f"   * {nombre_c} vence {label}\n"
    if not lineas_vencer:
        lineas_vencer = '   OK - Ninguna membresia por vencer\n'

    return (
        f"📊 <b>Resumen L-GYM — {now.strftime('%d/%m/%Y')}</b>\n"
        f"{'─'*22}\n"
        f"💰 <b>Ingresos hoy:</b> <code>${'{:,.0f}'.format(total_dia)} COP</code>\n"
        f"🧾 <b>Pagos registrados:</b> <code>{num_pagos}</code>\n"
        f"{'─'*22}\n"
        f"📋 <b>Por plan</b>\n{lineas_planes}"
        f"{'─'*22}\n"
        f"💳 <b>Por método</b>\n{lineas_metodos}"
        f"{'─'*22}\n"
        f"⏳ <b>Próximos a vencer</b>\n{lineas_vencer}"
        f"{'─'*22}\n"
        f"<i>Consultado a las {now.strftime('%H:%M')}</i>"
    )


@telegram_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json(silent=True)
    if not data or 'message' not in data:
        return jsonify({'ok': True})

    message = data['message']
    chat_id = str(message.get('chat', {}).get('id', ''))
    texto = (message.get('text') or '').strip().lower()

    # Seguridad: solo responde al chat autorizado (el mismo TELEGRAM_CHAT_ID
    # que usa notification_service.send_telegram_owner)
    if not AUTHORIZED_CHAT_ID or chat_id != AUTHORIZED_CHAT_ID:
        return jsonify({'ok': True})

    if texto in ('/resumen', '/hoy', 'cuanto va', '¿cuánto va?', 'cuánto va'):
        try:
            resumen = _resumen_del_dia()
        except Exception as exc:
            current_app.logger.error(f'[telegram_webhook] error generando resumen: {exc}', exc_info=True)
            resumen = '⚠️ Hubo un error generando el resumen. Revisa los logs.'
        _enviar_mensaje(chat_id, resumen)
    elif texto == '/start':
        _enviar_mensaje(chat_id, 'Bot de L-GYM activo ✅\nEscribe /resumen para ver el corte de hoy.')
    else:
        _enviar_mensaje(chat_id, 'Comando no reconocido. Usa /resumen')

    return jsonify({'ok': True})
