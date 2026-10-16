"""
Salo: asistente flotante.

Cómo funciona
-------------
1. El navegador manda el historial corto del chat a /assistant/chat.
2. Aquí se lo pasamos al modelo junto con una lista de "herramientas".
3. Herramientas de LECTURA (buscar cliente, ver planes, estado) se ejecutan
   al instante.
4. Herramientas de ESCRITURA (registrar cliente, pago, asistencia) NO se
   ejecutan solas: se guardan como acción pendiente y el usuario debe pulsar
   "Confirmar" en el chat. Así la IA nunca modifica datos sin tu visto bueno.
5. Al confirmar, se ejecuta con la MISMA lógica del sistema
   (validate_client, PaymentService.register_payment, reglas de asistencia,
   AuditService), así no se salta ninguna validación.

Compatible con cualquier API estilo OpenAI (Gemini, Groq, OpenRouter, OpenAI).
Variables de entorno:
    AI_API_KEY    (obligatoria)
    AI_BASE_URL   (default: Gemini)  https://generativelanguage.googleapis.com/v1beta/openai
    AI_MODEL      (default: gemini-2.0-flash)
"""
import json
import logging
import os
import re
import secrets
import threading
import time
import unicodedata
from datetime import datetime, timedelta

import pytz
import requests
from flask import session, current_app

from database.db import db
from database.models.client import Client
from database.models.membership import Membership
from database.models.payment import Payment
from database.models.attendance import Attendance
from services.audit_service import AuditService
from services.attendance_service import AttendanceService
from services.payment_service import PaymentService
from utils.validators import validate_client

BOGOTA = pytz.timezone('America/Bogota')
logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
MAX_HISTORY = 12
MAX_PENDING = 5
LLM_TIMEOUT = 30
LLM_RETRY_STATUS = {500, 502, 503, 504}   # errores temporales del proveedor (saturado/caído)
LLM_RETRY_DELAY = 1.5                      # segundos antes del único reintento
MAX_PAYMENTS_LIST = 20
PAYMENT_METHODS = ['efectivo', 'transferencia', 'nequi', 'daviplata', 'tarjeta', 'datafono']
DOC_TYPES = ['CC', 'TI', 'CE', 'PAS']
MUSIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'music')
MUSIC_ACTIONS = ['pausar', 'reanudar', 'siguiente', 'anterior', 'detener', 'subir_volumen', 'bajar_volumen']


# ──────────────────────────────────────────────────────────────────────
# Definición de herramientas (formato OpenAI)
# ──────────────────────────────────────────────────────────────────────
def _tool(name, description, props, required):
    return {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {'type': 'object', 'properties': props, 'required': required},
        },
    }


TOOLS = [
    _tool('buscar_cliente',
          'Busca clientes activos por nombre o número de documento. Úsala SIEMPRE antes de '
          'registrar un pago o asistencia para obtener el id real del cliente.',
          {'consulta': {'type': 'string', 'description': 'Nombre o documento'}}, ['consulta']),
    _tool('listar_planes',
          'Lista los planes/membresías activos con id, precio y duración.', {}, []),
    _tool('estado_cliente',
          'Muestra si un cliente tiene membresía vigente, hasta cuándo y si está congelada.',
          {'client_id': {'type': 'integer'}}, ['client_id']),
    _tool('resumen_hoy',
          'Resumen de hoy: pagos, ingresos y asistencias. Solo para administradores.', {}, []),
    _tool('buscar_pagos',
          'Busca pagos registrados con filtros opcionales y combinables: cliente, rango de fechas, '
          'método, plan, monto o número de recibo. Sin filtros devuelve los más recientes, así que '
          'sirve también para "último pago". Devuelve el total encontrado y la suma. '
          'Incluye los pagos "espejo" de Plan Pareja/Familiar (monto $0, el cobro está en el pago del '
          'titular) marcados con tipo=espejo. Solo para administradores.',
          {'cliente': {'type': 'string', 'description': 'Nombre o documento del cliente (parcial sirve)'},
           'client_id': {'type': 'integer', 'description': 'Id exacto del cliente (si ya lo tienes)'},
           'recibo': {'type': 'integer', 'description': 'Número de recibo / id del pago'},
           'fecha_desde': {'type': 'string', 'description': 'YYYY-MM-DD, fecha de pago desde (inclusive)'},
           'fecha_hasta': {'type': 'string', 'description': 'YYYY-MM-DD, fecha de pago hasta (inclusive)'},
           'metodo_pago': {'type': 'string', 'enum': PAYMENT_METHODS},
           'membership_id': {'type': 'integer', 'description': 'Id del plan (usa listar_planes)'},
           'monto_min': {'type': 'number'},
           'monto_max': {'type': 'number'},
           'incluir_espejo': {'type': 'boolean',
                              'description': 'Incluir pagos espejo de Pareja/Familiar (por defecto true)'},
           'orden': {'type': 'string', 'enum': ['recientes', 'antiguos', 'monto_mayor'],
                     'description': 'Por defecto recientes'},
           'limite': {'type': 'integer', 'description': 'Cuántos mostrar (1-20, por defecto 5)'}}, []),
    _tool('registrar_cliente',
          'Prepara el registro de un cliente nuevo (requiere confirmación del usuario). '
          'Nombre y documento son obligatorios: si falta el documento, PREGÚNTALO, no lo inventes.',
          {
              'nombre_completo': {'type': 'string'},
              'numero_documento': {'type': 'string'},
              'tipo_documento': {'type': 'string', 'enum': DOC_TYPES, 'description': 'Por defecto CC'},
              'telefono': {'type': 'string'},
              'email': {'type': 'string'},
          }, ['nombre_completo', 'numero_documento']),
    _tool('registrar_pago',
          'Prepara el registro de un pago/membresía (requiere confirmación del usuario). '
          'Usa ids reales obtenidos con buscar_cliente y listar_planes.',
          {
              'client_id': {'type': 'integer'},
              'membership_id': {'type': 'integer'},
              'metodo_pago': {'type': 'string', 'enum': PAYMENT_METHODS},
              'monto': {'type': 'number', 'description': 'Si no se indica, se usa el precio del plan'},
              'fecha_inicio': {'type': 'string', 'description': 'YYYY-MM-DD, por defecto hoy'},
              'partner_client_id': {'type': 'integer', 'description': 'Solo Plan Pareja: segundo cliente'},
              'es_estudiante': {'type': 'boolean', 'description': 'Solo Plan Estudiantil: el usuario confirmó que es bachiller'},
              'notas': {'type': 'string'},
          }, ['client_id', 'membership_id', 'metodo_pago']),
    _tool('registrar_asistencia',
          'Prepara el registro de asistencia de hoy para un cliente (requiere confirmación).',
          {'client_id': {'type': 'integer'}}, ['client_id']),
    _tool('listar_canciones',
          'Lista las canciones disponibles para reproducir en el asistente.', {}, []),
    _tool('reproducir_musica',
          'Reproduce música en el navegador del usuario (no necesita confirmación). Con \'consulta\' busca '
          'por título o artista (ej. "Brickell", "Yandel"); si varias coinciden, suenan en cola. '
          'Sin consulta, o con aleatorio=true, reproduce en orden aleatorio.',
          {'consulta': {'type': 'string', 'description': 'Título o artista (parcial sirve)'},
           'aleatorio': {'type': 'boolean', 'description': 'Reproducir en orden aleatorio'}}, []),
    _tool('controlar_musica',
          'Controla la música que está sonando: pausar, reanudar, siguiente, anterior, detener, '
          'subir_volumen o bajar_volumen.',
          {'accion': {'type': 'string', 'enum': MUSIC_ACTIONS}}, ['accion']),
]

WRITE_TOOLS = {'registrar_cliente', 'registrar_pago', 'registrar_asistencia'}


def _system_prompt():
    hoy = datetime.now(BOGOTA)
    return (
        'Eres Salo, el asistente del sistema de gestión del gimnasio Body-Fit. Si te preguntan cómo te llamas, responde que te llamas Salo. Hablas en español, '
        'breve y amable.\n'
        'ESTILO (siempre, con toda la recepción): hablas como "el Ferxxo", con el parlache paisa de Medellín y '
        'vibra de reggaetón: relajado, chévere y con buena energía. Usa expresiones como "parce", "mor", "qué más pues", '
        '"de una", "bien chimba", "nea", "ferxxo", "con toda", "pilas". Tutea siempre y trata a la recepcionista con '
        'respeto y camaradería, sin coqueteo ni nada subido de tono. Respuestas cortas, máximo 1-2 emojis (💚🔥💪🎵). '
        'Eres Salo, un personaje: no digas que eres Feid ni inventes frases suyas, y no cites letras de canciones. '
        'El estilo NUNCA cambia los datos: nombres, montos, fechas y ids deben ser exactos y claros, '
        'y los errores o avisos importantes (membresía vencida, congelada, falta un dato) se dicen con claridad.\n'
        'Ayudas a recepción a registrar clientes, pagos de membresía y '
        'asistencia, y a consultar estados.\n'
        f'Fecha de hoy: {hoy.strftime("%Y-%m-%d")} (zona Bogotá). Moneda: pesos colombianos (COP).\n'
        'Reglas:\n'
        '- Nunca inventes ids, documentos, precios ni datos. Usa las herramientas.\n'
        '- Para pagos/asistencia primero busca al cliente con buscar_cliente. Si hay varios '
        'resultados parecidos, pregunta cuál. Si no hay, ofrece registrarlo.\n'
        '- Para elegir plan usa listar_planes y haz coincidir lo que dijo el usuario.\n'
        '- Si falta un dato obligatorio (documento, método de pago, plan), pregúntalo en una sola frase.\n'
        '- Las acciones de escritura quedan pendientes: después de llamarlas, dile al usuario '
        'que revise el resumen y pulse "Confirmar". No digas que ya se hizo.\n'
        '- Plan Familiar no se puede registrar por aquí: indica que use el formulario de pagos.\n'
        '- Para "último pago" o pagos recientes usa buscar_pagos (filtra por cliente, fechas, método, plan, monto o recibo según lo que pidan; no inventes filtros).\n'
        '- Música: puedes reproducir las canciones de la carpeta del gimnasio con reproducir_musica y '
        'controlarla con controlar_musica (pausar, siguiente, volumen...). Si piden "música" sin especificar, '
        'ponla aleatoria. Si no sabes qué canciones hay, usa listar_canciones. No necesitan confirmación.\n'
        '- Si piden algo que no puedes hacer (borrar, editar, reportes complejos), dilo y sugiere la pantalla correspondiente.'
    )


# ──────────────────────────────────────────────────────────────────────
# Llamada al modelo
# ──────────────────────────────────────────────────────────────────────
class AssistantError(Exception):
    pass


def _call_llm(messages):
    key = os.environ.get('AI_API_KEY', '').strip()
    if not key:
        raise AssistantError('El asistente no está configurado: falta la variable AI_API_KEY.')
    base = os.environ.get('AI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai').rstrip('/')
    model = os.environ.get('AI_MODEL', 'gemini-2.0-flash')
    payload = {'model': model, 'messages': messages, 'tools': TOOLS,
               'tool_choice': 'auto', 'temperature': 0.2, 'max_tokens': 600}
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    r = None
    for attempt in (1, 2):                      # 1 intento + 1 reintento automático
        last = attempt == 2
        try:
            r = requests.post(f'{base}/chat/completions', headers=headers, json=payload,
                              timeout=LLM_TIMEOUT)
        except requests.RequestException as exc:
            logger.error(f'[assistant] error de red (intento {attempt}): {exc}')
            if last:
                raise AssistantError('No pude conectar con la IA. Intenta de nuevo en un momento.')
            time.sleep(LLM_RETRY_DELAY)
            continue
        if r.status_code in LLM_RETRY_STATUS and not last:
            logger.warning(f'[assistant] HTTP {r.status_code} temporal, reintentando…')
            time.sleep(LLM_RETRY_DELAY)
            continue
        break

    if r.status_code == 429:
        raise AssistantError('Se agotó el cupo gratuito de la IA por ahora. Intenta más tarde.')
    if r.status_code in LLM_RETRY_STATUS:
        logger.error(f'[assistant] HTTP {r.status_code} tras reintento: {r.text[:300]}')
        raise AssistantError('La IA está saturada en este momento. Intenta de nuevo en un minuto.')
    if r.status_code in (401, 403):
        logger.error(f'[assistant] HTTP {r.status_code}: {r.text[:300]}')
        raise AssistantError('La IA rechazó la llave. Revisa AI_API_KEY.')
    if r.status_code == 404:
        logger.error(f'[assistant] HTTP 404: {r.text[:300]}')
        raise AssistantError('No encontré el modelo de IA. Revisa AI_MODEL.')
    if r.status_code >= 400:
        logger.error(f'[assistant] HTTP {r.status_code}: {r.text[:300]}')
        raise AssistantError(f'La IA respondió con error ({r.status_code}). Intenta de nuevo.')
    try:
        return r.json()['choices'][0]['message']
    except (KeyError, IndexError, ValueError):
        raise AssistantError('Respuesta inesperada de la IA.')


# ──────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────
def _money(v):
    return f'${float(v):,.0f}'.replace(',', '.')


def _today():
    return datetime.now(BOGOTA).date()


def _client_brief(c):
    return {'id': c.id, 'nombre': c.full_name, 'documento': c.document_number, 'telefono': c.phone}


def _active_payment(client_id):
    today = _today()
    return (Payment.query
            .filter(Payment.client_id == client_id, Payment.is_deleted == False,
                    Payment.start_date <= today,
                    db.or_(Payment.end_date >= today, Payment.is_frozen == True))
            .order_by(Payment.end_date.desc()).first())


# ──────────────────────────────────────────────────────────────────────
# Herramientas de lectura
# ──────────────────────────────────────────────────────────────────────
def _t_buscar_cliente(a, user):
    q = (a.get('consulta') or '').strip()
    if len(q) < 2:
        return {'error': 'La consulta es muy corta.'}
    rows = (Client.query.filter(Client.is_active == True, Client.document_number != 'DIARIO-0000')
            .filter(db.or_(Client.full_name.ilike(f'%{q}%'), Client.document_number.ilike(f'%{q}%')))
            .order_by(Client.full_name).limit(8).all())
    return {'resultados': [_client_brief(c) for c in rows], 'total': len(rows)}


def _t_listar_planes(a, user):
    rows = Membership.query.filter_by(is_active=True).order_by(Membership.name).all()
    return {'planes': [{'id': m.id, 'nombre': m.name, 'tipo': m.membership_type,
                        'precio': m.price, 'dias': m.duration_days} for m in rows]}


def _t_estado_cliente(a, user):
    c = Client.query.get(a.get('client_id'))
    if not c:
        return {'error': 'Cliente no encontrado.'}
    p = _active_payment(c.id)
    if not p:
        last = (Payment.query.filter_by(client_id=c.id, is_deleted=False)
                .order_by(Payment.end_date.desc()).first())
        return {'cliente': c.full_name, 'membresia_vigente': False,
                'ultimo_vencimiento': last.end_date.isoformat() if last else None}
    return {'cliente': c.full_name, 'membresia_vigente': True,
            'plan': p.membership.name if p.membership else None,
            'vence': p.end_date.isoformat(), 'congelada': bool(p.is_frozen),
            'dias_restantes': (p.end_date - _today()).days}


def _t_resumen_hoy(a, user):
    if user.get('role') != 'admin':
        return {'error': 'Solo el administrador puede ver los ingresos.'}
    today = _today()
    pagos = Payment.query.filter(Payment.payment_date == today, Payment.is_deleted == False,
                                 Payment.amount > 0).all()
    asist = Attendance.query.filter(db.func.date(Attendance.check_in) == today).count()
    return {'pagos': len(pagos), 'ingresos': _money(sum(p.amount for p in pagos)), 'asistencias': asist}


def _parse_date(v):
    try:
        return datetime.strptime(str(v).strip(), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _t_buscar_pagos(a, user):
    if user.get('role') != 'admin':
        return {'error': 'Solo el administrador puede ver los pagos.'}
    try:
        limit = max(1, min(int(a.get('limite') or 5), MAX_PAYMENTS_LIST))
    except (TypeError, ValueError):
        limit = 5

    q = Payment.query.filter(Payment.is_deleted == False)
    # Los pagos "espejo" (Plan Pareja/Familiar) tienen monto 0: se muestran salvo que pidan ocultarlos
    if a.get('incluir_espejo') is False:
        q = q.filter(Payment.amount > 0)

    if a.get('recibo'):
        q = q.filter(Payment.id == a.get('recibo'))
    if a.get('client_id'):
        q = q.filter(Payment.client_id == a.get('client_id'))
    texto = (a.get('cliente') or '').strip()
    if texto:
        if len(texto) < 2:
            return {'error': 'El nombre o documento del cliente es muy corto.'}
        q = q.join(Client, Payment.client_id == Client.id).filter(
            db.or_(Client.full_name.ilike(f'%{texto}%'), Client.document_number.ilike(f'%{texto}%')))
    for campo, op in (('fecha_desde', '>='), ('fecha_hasta', '<=')):
        if a.get(campo):
            d = _parse_date(a.get(campo))
            if not d:
                return {'error': f'{campo} inválida (usa AAAA-MM-DD).'}
            q = q.filter(Payment.payment_date >= d if op == '>=' else Payment.payment_date <= d)
    if a.get('metodo_pago'):
        # el método puede ser compuesto (pago dividido), por eso "contiene"
        q = q.filter(Payment.payment_method.ilike(f'%{str(a.get("metodo_pago")).lower()}%'))
    if a.get('membership_id'):
        q = q.filter(Payment.membership_id == a.get('membership_id'))
    try:
        if a.get('monto_min') is not None:
            q = q.filter(Payment.amount >= float(a.get('monto_min')))
        if a.get('monto_max') is not None:
            q = q.filter(Payment.amount <= float(a.get('monto_max')))
    except (TypeError, ValueError):
        return {'error': 'Monto inválido.'}

    total = q.count()
    suma = q.with_entities(db.func.coalesce(db.func.sum(Payment.amount), 0)).scalar() or 0
    orden = a.get('orden')
    if orden == 'antiguos':
        q = q.order_by(Payment.payment_date.asc(), Payment.id.asc())
    elif orden == 'monto_mayor':
        q = q.order_by(Payment.amount.desc(), Payment.id.desc())
    else:
        q = q.order_by(Payment.payment_date.desc(), Payment.id.desc())
    rows = q.limit(limit).all()

    def _row(p):
        es_espejo = (p.amount or 0) == 0 and p.partner_client_id is not None
        row = {
            'recibo': p.id,
            'tipo': 'espejo' if es_espejo else 'pago',
            'cliente': p.client.full_name if p.client else None,
            'plan': p.membership.name if p.membership else None,
            'monto': _money(p.amount),
            'metodo': p.payment_method,
            'fecha_pago': p.payment_date.isoformat() if p.payment_date else None,
            'vence': p.end_date.isoformat() if p.end_date else None,
        }
        if es_espejo:
            row['pagado_por'] = p.partner.full_name if p.partner else None
        return row

    return {'total_encontrados': total, 'suma_total': _money(suma), 'mostrando': len(rows),
            'pagos': [_row(p) for p in rows]}


READ_HANDLERS = {
    'buscar_cliente': _t_buscar_cliente,
    'listar_planes': _t_listar_planes,
    'estado_cliente': _t_estado_cliente,
    'resumen_hoy': _t_resumen_hoy,
    'buscar_pagos': _t_buscar_pagos,
}


# ──────────────────────────────────────────────────────────────────────
# Música (la reproducción ocurre en el navegador; aquí solo se decide QUÉ sonar)
# ──────────────────────────────────────────────────────────────────────
def _norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def list_songs():
    """Canciones de la carpeta music/ (basta con copiar un .mp3 ahí para que aparezca)."""
    songs = []
    if not os.path.isdir(MUSIC_DIR):
        return songs
    for fname in sorted(os.listdir(MUSIC_DIR), key=_norm):
        if not fname.lower().endswith(('.mp3', '.m4a', '.ogg', '.wav')):
            continue
        title = os.path.splitext(fname)[0]
        songs.append({'id': _norm(title).replace(' ', '-'), 'title': title, 'file': fname,
                      '_key': _norm(title)})
    return songs


def song_file(song_id):
    """Ruta del archivo a partir del id (el cliente nunca manda nombres de archivo)."""
    for s in list_songs():
        if s['id'] == song_id:
            return os.path.join(MUSIC_DIR, s['file']), s['file']
    return None, None


def _public(song):
    return {'id': song['id'], 'title': song['title']}


def _t_listar_canciones(a, user, commands):
    songs = list_songs()
    return {'total': len(songs), 'canciones': [s['title'] for s in songs]}


def _t_reproducir_musica(a, user, commands):
    songs = list_songs()
    if not songs:
        return {'error': 'No hay canciones cargadas en el sistema.'}
    q = _norm(a.get('consulta'))
    if q:
        tokens = q.split()
        found = [s for s in songs if all(t in s['_key'] for t in tokens)]
        if not found:
            return {'error': 'No encontré esa canción.', 'disponibles': [s['title'] for s in songs]}
    else:
        found = songs
    shuffle = bool(a.get('aleatorio')) or not q
    commands.append({'type': 'play', 'queue': [s['id'] for s in found],
                     'shuffle': shuffle and len(found) > 1})
    if shuffle and len(found) > 1:
        return {'estado': 'reproduciendo_aleatorio', 'canciones_en_cola': len(found)}
    return {'estado': 'reproduciendo', 'cancion': found[0]['title'], 'en_cola': [s['title'] for s in found[1:]]}


def _t_controlar_musica(a, user, commands):
    action = a.get('accion')
    if action not in MUSIC_ACTIONS:
        return {'error': f'Acción inválida. Opciones: {", ".join(MUSIC_ACTIONS)}.'}
    commands.append({'type': action})
    return {'estado': 'ok', 'accion': action}


MUSIC_HANDLERS = {
    'listar_canciones': _t_listar_canciones,
    'reproducir_musica': _t_reproducir_musica,
    'controlar_musica': _t_controlar_musica,
}


# ──────────────────────────────────────────────────────────────────────
# Escritura: preparar (valida + resume) y ejecutar (al confirmar)
# ──────────────────────────────────────────────────────────────────────
def _prepare_cliente(a):
    form = {
        'full_name': (a.get('nombre_completo') or '').strip().title(),
        'document_type': (a.get('tipo_documento') or 'CC').upper(),
        'document_number': (a.get('numero_documento') or '').strip(),
        'phone': (a.get('telefono') or '').strip() or None,
        'email': (a.get('email') or '').strip() or None,
    }
    if form['document_type'] not in DOC_TYPES:
        form['document_type'] = 'CC'
    errors = validate_client(form)          # misma validación que el formulario
    if errors:
        return None, ' '.join(errors)
    lines = [f'Nombre: {form["full_name"]}', f'Documento: {form["document_type"]} {form["document_number"]}']
    if form['phone']:
        lines.append(f'Teléfono: {form["phone"]}')
    if form['email']:
        lines.append(f'Email: {form["email"]}')
    return {'title': 'Registrar cliente nuevo', 'lines': lines, 'data': form}, None


def _prepare_pago(a):
    client = Client.query.get(a.get('client_id'))
    if not client or not client.is_active:
        return None, 'El cliente no existe o está inactivo.'
    m = Membership.query.get(a.get('membership_id'))
    if not m or not m.is_active:
        return None, 'El plan no existe o está inactivo.'
    if m.is_familiar_plan:
        return None, 'El Plan Familiar requiere varios integrantes: regístralo desde Pagos → Nuevo pago.'
    method = (a.get('metodo_pago') or '').lower()
    if method not in PAYMENT_METHODS:
        return None, f'Método de pago inválido. Opciones: {", ".join(PAYMENT_METHODS)}.'
    try:
        amount = float(a.get('monto') if a.get('monto') is not None else m.price)
    except (TypeError, ValueError):
        return None, 'Monto inválido.'
    if amount <= 0:
        return None, 'El monto debe ser mayor a 0.'
    start = (a.get('fecha_inicio') or _today().isoformat()).strip()
    try:
        datetime.strptime(start, '%Y-%m-%d')
    except ValueError:
        return None, 'Fecha de inicio inválida (usa AAAA-MM-DD).'

    form = {
        'client_id': str(client.id), 'membership_id': str(m.id), 'amount': str(amount),
        'start_date': start, 'payment_method': method, 'notes': (a.get('notas') or '').strip() or None,
    }
    lines = [f'Cliente: {client.full_name}', f'Plan: {m.name} ({m.duration_days} días)',
             f'Monto: {_money(amount)}', f'Método: {method}', f'Inicia: {start}']

    if m.is_couple_plan:
        partner = Client.query.get(a.get('partner_client_id') or 0)
        if not partner:
            return None, 'El Plan Pareja requiere el segundo cliente. Pregunta quién es.'
        form['partner_client_id'] = str(partner.id)
        lines.append(f'Pareja: {partner.full_name}')
    if m.is_student_plan:
        if not a.get('es_estudiante'):
            return None, 'El Plan Estudiantil es solo para bachilleres. Pregunta si el cliente lo es.'
        form['is_student'] = 'on'
    if m.membership_type == 'diario':
        lines[0] = 'Cliente: DIARIO (pago diario, sin cliente propio)'

    # Aviso, no bloqueo (el formulario tampoco bloquea): ya tiene plan vigente
    prev = _active_payment(client.id)
    if prev and m.membership_type != 'diario':
        lines.append(f'⚠️ Ya tiene membresía vigente hasta {prev.end_date.strftime("%d/%m/%Y")}.')
    return {'title': 'Registrar pago', 'lines': lines, 'data': form}, None


def _prepare_asistencia(a):
    client = Client.query.get(a.get('client_id'))
    if not client or not client.is_active:
        return None, 'El cliente no existe o está inactivo.'
    return {'title': 'Registrar asistencia', 'lines': [f'Cliente: {client.full_name}', 'Fecha: hoy'],
            'data': {'client_id': client.id}}, None


PREPARERS = {
    'registrar_cliente': ('create_client', _prepare_cliente),
    'registrar_pago': ('create_payment', _prepare_pago),
    'registrar_asistencia': ('attendance', _prepare_asistencia),
}


def _send_welcome_async(app, client_id):
    with app.app_context():
        try:
            from services.notification_service import NotificationService
            c = Client.query.get(client_id)
            if c:
                NotificationService.send_welcome(c)
        except Exception:
            pass


def _exec_create_client(d):
    errors = validate_client(d)             # se revalida al confirmar (p. ej. documento duplicado)
    if errors:
        return False, ' '.join(errors)
    c = Client(full_name=d['full_name'], document_type=d['document_type'],
               document_number=d['document_number'], email=d.get('email'), phone=d.get('phone'))
    db.session.add(c)
    db.session.commit()
    AuditService.log('create', 'clients', c.id, None, f'{c.full_name} (Salo)')
    if c.email:
        app = current_app._get_current_object()
        threading.Thread(target=_send_welcome_async, args=(app, c.id), daemon=True).start()
    return True, f'✅ Cliente {c.full_name} registrado (id {c.id}).'


def _exec_create_payment(d):
    payment, partner_payment, error, familiar = PaymentService.register_payment(d)
    if error:
        return False, error
    AuditService.log('create', 'payments', payment.id, None, f'{payment.amount} (Salo)')
    if partner_payment:
        AuditService.log('create', 'payments', partner_payment.id, None, 'Plan Pareja (espejo, Salo)')
    # Mismo aviso por Telegram/email que el formulario normal
    try:
        from controllers.payments_controller import _send_payment_email, _send_couple_email
        _send_payment_email(payment)
        if partner_payment:
            _send_couple_email(partner_payment, payment.client)
    except Exception as exc:
        logger.error(f'[assistant] notificación de pago falló: {exc}')
    finally:
        session.pop('_flashes', None)   # esos helpers usan flash(); no queremos mensajes colgados
    return True, (f'✅ Pago registrado: {payment.client.full_name} — {payment.membership.name} '
                  f'({_money(payment.amount)}). Vence {payment.end_date.strftime("%d/%m/%Y")}. '
                  f'Recibo #{payment.id}.')


def _exec_attendance(d):
    client = Client.query.get(d['client_id'])
    if not client or not client.is_active:
        return False, 'El cliente no existe o está inactivo.'
    frozen = AttendanceService.blocking_frozen_payment(client.id)   # mismas reglas que /attendance/register
    if frozen:
        AttendanceService.notify_frozen_attempt(client, frozen, source='asistente',
                                                registered_by=session.get('user_username'))
        return False, f'❄️ La membresía de {client.full_name} está congelada. No se registró; ya se avisó al dueño.'
    if not _active_payment(client.id) or _active_payment(client.id).end_date < _today():
        return False, f'⚠️ {client.full_name} no tiene membresía activa. Registra un pago primero.'
    today = _today()
    if Attendance.query.filter(Attendance.client_id == client.id,
                               db.func.date(Attendance.check_in) == today).first():
        return False, f'{client.full_name} ya tiene asistencia registrada hoy.'
    AttendanceService.register(client.id, notes='Registrada con Salo')
    return True, f'✅ Asistencia registrada para {client.full_name}.'


EXECUTORS = {'create_client': _exec_create_client, 'create_payment': _exec_create_payment,
             'attendance': _exec_attendance}


# ──────────────────────────────────────────────────────────────────────
# Acciones pendientes (viven en la sesión del usuario)
# ──────────────────────────────────────────────────────────────────────
def _pending():
    return session.setdefault('assistant_pending', {})


def _store_pending(kind, prepared):
    store = _pending()
    while len(store) >= MAX_PENDING:
        store.pop(next(iter(store)))
    token = secrets.token_urlsafe(8)
    store[token] = {'kind': kind, 'data': prepared['data']}
    session.modified = True
    return token


def confirm_action(token, approve=True):
    store = _pending()
    action = store.pop(token, None)
    session.modified = True
    if not action:
        return False, 'Esa acción ya no está disponible (expiró o ya se procesó).'
    if not approve:
        return True, 'Cancelado. No se hizo ningún cambio.'
    try:
        return EXECUTORS[action['kind']](action['data'])
    except Exception as exc:
        db.session.rollback()
        logger.error(f'[assistant] error ejecutando {action["kind"]}: {exc}', exc_info=True)
        return False, 'Ocurrió un error al guardar. No se hizo ningún cambio.'


# ──────────────────────────────────────────────────────────────────────
# Chat principal
# ──────────────────────────────────────────────────────────────────────
def _clean_history(history):
    out = []
    for m in (history or [])[-MAX_HISTORY:]:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str):
            out.append({'role': m['role'], 'content': m['content'][:1000]})
    return out


def chat(history, user):
    """Devuelve {'reply': str, 'actions': [{token,title,lines}], 'music': [comandos para el reproductor]}."""
    messages = [{'role': 'system', 'content': _system_prompt()}] + _clean_history(history)
    actions = []
    music = []

    for _ in range(MAX_TOOL_ROUNDS):
        msg = _call_llm(messages)
        calls = msg.get('tool_calls') or []
        if not calls:
            reply = (msg.get('content') or '').strip() or 'No entendí, ¿puedes repetirlo?'
            return {'reply': reply, 'actions': actions, 'music': music}

        messages.append({'role': 'assistant', 'content': msg.get('content') or '', 'tool_calls': calls})
        for call in calls:
            name = call['function']['name']
            try:
                args = json.loads(call['function'].get('arguments') or '{}')
            except ValueError:
                args = {}

            if name in READ_HANDLERS:
                result = READ_HANDLERS[name](args, user)
            elif name in MUSIC_HANDLERS:
                result = MUSIC_HANDLERS[name](args, user, music)
            elif name in PREPARERS:
                kind, prep = PREPARERS[name]
                prepared, err = prep(args)
                if err:
                    result = {'error': err}
                else:
                    token = _store_pending(kind, prepared)
                    actions.append({'token': token, 'title': prepared['title'], 'lines': prepared['lines']})
                    result = {'estado': 'pendiente_de_confirmacion',
                              'instruccion': 'Pide al usuario que pulse Confirmar en la tarjeta.'}
            else:
                result = {'error': 'Herramienta desconocida.'}
            messages.append({'role': 'tool', 'tool_call_id': call.get('id', name),
                             'content': json.dumps(result, ensure_ascii=False, default=str)})

    return {'reply': 'Necesito un poco más de detalle para continuar. ¿Qué quieres hacer exactamente?',
            'actions': actions, 'music': music}
