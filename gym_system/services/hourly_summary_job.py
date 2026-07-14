"""
Job que junta todos los eventos acumulados (pagos, ventas,
eliminaciones, cobros pendientes) y envía UN solo mensaje de WhatsApp
al dueño con el resumen, en vez de un mensaje por cada evento.
 
Se dispara desde /health (igual que daily_report_job). En vez de
esperar a que cambie la hora en punto, despacha el resumen apenas
hay eventos pendientes en cola Y ya pasó al menos INTERVALO_MINUTOS
desde el último envío. Esto evita que un pago quede "atrapado"
hasta la próxima hora en punto cuando el ping de salud (UptimeRobot,
cada 5 min) llega justo después de que el resumen ya corrió esa hora.
 
Solo se ejecuta entre las 5:00am y las 10:00pm (hora Bogotá). Fuera
de ese rango los eventos quedan en la cola sin enviarse, y se
incluyen en el primer envío del día (a partir de las 5am).
 
Si no hay ningún evento pendiente, no envía nada (para no gastar
mensajes sin necesidad).
"""
import pytz
import logging
from datetime import datetime, timedelta
from services.notification_queue import pop_all, pending_count
 
BOGOTA = pytz.timezone('America/Bogota')
logger = logging.getLogger(__name__)
 
HORA_INICIO = 5    # 5:00 am
HORA_FIN    = 22   # 10:00 pm (no se envía después de esta hora)
LIMITE_CARACTERES = 3500  # margen de seguridad bajo los 4096 de WhatsApp
INTERVALO_MINUTOS = 5  # mínimo de minutos entre despachos consecutivos
 
_last_run_at = None  # datetime (Bogotá) del último envío exitoso
 
ICONOS = {
    'pago': '💪',
    'pago_pendiente': '⏳',
    'pago_eliminado': '🗑️',
    'venta': '🛒',
    'venta_pendiente': '⏳',
    'venta_cobrada': '✅',
}
 
TITULOS = {
    'pago': 'Pagos nuevos',
    'pago_pendiente': 'Pagos pendientes',
    'pago_eliminado': 'Pagos eliminados',
    'venta': 'Ventas (inventario)',
    'venta_pendiente': 'Ventas pendientes',
    'venta_cobrada': 'Ventas cobradas',
}
 
 
DIVISOR = '─' * 22


def _escapar_html(texto):
    """Escapa los caracteres especiales de Telegram HTML dentro del texto libre."""
    return (texto or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _construir_bloques(eventos):
    """Agrupa eventos por tipo y devuelve una lista de bloques de texto en HTML."""
    grupos = {}
    for ev in eventos:
        grupos.setdefault(ev['tipo'], []).append(ev['texto'])
 
    bloques = []
    for tipo, textos in grupos.items():
        icono = ICONOS.get(tipo, '•')
        titulo = TITULOS.get(tipo, tipo)
        lineas = "\n".join(f"  • {_escapar_html(t)}" for t in textos)
        bloques.append(f"{icono} <b>{titulo}</b> <code>({len(textos)})</code>\n{lineas}")
    return bloques
 
 
def _partir_en_mensajes(bloques, encabezado, pie):
    """
    Reparte los bloques en uno o más mensajes que no superen
    LIMITE_CARACTERES. Si un bloque por sí solo ya supera el límite
    (ej. un mismo tipo de evento con muchísimas líneas en la hora),
    ese bloque se corta línea por línea en sub-bloques, conservando
    el título y el contador correctos en cada parte.
    """
    margen = len(encabezado) + len(pie)
    mensajes = []
    actual = []
    largo_actual = margen
 
    def _agregar(pieza):
        nonlocal actual, largo_actual
        costo = len(pieza) + 2  # separador "\n\n"
        if actual and (largo_actual + costo) > LIMITE_CARACTERES:
            mensajes.append(actual)
            actual = []
            largo_actual = margen
        actual.append(pieza)
        largo_actual += costo
 
    for bloque in bloques:
        if margen + len(bloque) + 2 <= LIMITE_CARACTERES:
            _agregar(bloque)
            continue
 
        # Bloque demasiado grande: lo partimos línea por línea
        lineas = bloque.split('\n')
        titulo_linea = lineas[0]
        items = lineas[1:]
        sub_items = []
        sub_largo = margen + len(titulo_linea) + 2
        for item in items:
            if sub_items and (sub_largo + len(item) + 1) > LIMITE_CARACTERES:
                _agregar(titulo_linea + '\n' + '\n'.join(sub_items))
                sub_items = []
                sub_largo = margen + len(titulo_linea) + 2
            sub_items.append(item)
            sub_largo += len(item) + 1
        if sub_items:
            _agregar(titulo_linea + '\n' + '\n'.join(sub_items))
 
    if actual:
        mensajes.append(actual)
 
    return mensajes
 
 
def run_hourly_summary(app):
    global _last_run_at
 
    with app.app_context():
        now = datetime.now(BOGOTA)
 
        pendientes = pending_count()
        print(
            f'[hourly_summary] chequeo a las {now.strftime("%H:%M:%S")} '
            f'(pendientes={pendientes}, ultimo_run={_last_run_at})', flush=True
        )
 
        # Fuera del horario 5am-10pm: no enviar, dejar acumulando en la cola
        if now.hour < HORA_INICIO or now.hour >= HORA_FIN:
            print(f'[hourly_summary] fuera de horario (hora={now.hour}), no se ejecuta.', flush=True)
            return
 
        # Nada pendiente: no hay nada que despachar
        if pendientes == 0:
            print('[hourly_summary] sin eventos pendientes, no se envia nada.', flush=True)
            return
 
        # Ya se despacho hace menos de INTERVALO_MINUTOS: esperar al proximo ping
        if _last_run_at is not None and (now - _last_run_at) < timedelta(minutes=INTERVALO_MINUTOS):
            proximo = _last_run_at + timedelta(minutes=INTERVALO_MINUTOS)
            print(
                f'[hourly_summary] esperando intervalo minimo, proximo despacho posible '
                f'a partir de {proximo.strftime("%H:%M:%S")}, se omite.', flush=True
            )
            return
 
        hour_key = now.strftime('%Y-%m-%d-%H:%M')
 
        try:
            eventos = pop_all()
            print(f'[hourly_summary] eventos en cola: {len(eventos)}', flush=True)
            if not eventos:
                print(f'[hourly_summary] {hour_key} — sin eventos, no se envia nada.', flush=True)
                return
 
            _last_run_at = now
 
            fecha_str = now.strftime('%d/%m/%Y')
            hora_str = now.strftime('%H:%M')
            bloques = _construir_bloques(eventos)
 
            encabezado = f"📊 <b>Resumen L-GYM</b>\n<i>{fecha_str} — {hora_str}</i>\n{DIVISOR}\n"
            pie = f"\n{DIVISOR}\nTotal eventos: <code>{len(eventos)}</code>"
 
            partes = _partir_en_mensajes(bloques, encabezado, pie)
 
            from services.notification_service import send_telegram_owner
            import os
            base_url = os.environ.get('RENDER_EXTERNAL_URL') or os.environ.get('APP_BASE_URL', '')
            botones = None
            if base_url:
                botones = [{'texto': '📋 Ver pagos de hoy', 'url': f'{base_url.rstrip("/")}/payments/'}]
 
            total_partes = len(partes)
            for i, parte_bloques in enumerate(partes, start=1):
                cuerpo = "\n\n".join(parte_bloques)
                sufijo_parte = f" (parte {i}/{total_partes})" if total_partes > 1 else ""
                mensaje = f"{encabezado.rstrip(chr(10))}{sufijo_parte}\n{cuerpo}{pie}"
                print(f'[hourly_summary] mensaje a enviar (parte {i}/{total_partes}): {mensaje!r}', flush=True)
                # Solo la última parte lleva el botón, para no repetirlo en cada mensaje
                ok = send_telegram_owner(mensaje, botones=botones if i == total_partes else None)
                print(f'[hourly_summary] parte {i}/{total_partes} enviada, resultado={ok}', flush=True)
 
            print(
                f'[hourly_summary] {hour_key} — resumen enviado '
                f'({len(eventos)} eventos, {total_partes} mensaje(s)).', flush=True
            )
 
        except Exception as exc:
            print(f'[hourly_summary] ERROR generando resumen: {exc}', flush=True)
            import traceback
            traceback.print_exc()