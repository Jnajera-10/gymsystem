from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
import pytz

from database.models.client import Client
from database.models.payment import Payment
from services.face_service import FaceService
from services.attendance_service import AttendanceService
from utils.security import login_required

BOGOTA = pytz.timezone('America/Bogota')

face_bp = Blueprint('face', __name__)


def _has_active_membership(client_id):
    today = datetime.now(BOGOTA).date()
    return Payment.query.filter(
        Payment.client_id == client_id,
        Payment.is_deleted == False,
        Payment.start_date <= today,
        Payment.end_date >= today,
    ).first() is not None


@face_bp.route('/attendance/facial')
@login_required
def facial_checkin_page():
    """Pantalla de kiosco: cámara + verificación automática."""
    return render_template('attendance/facial_checkin.html')


@face_bp.route('/api/face/register/<int:client_id>', methods=['POST'])
@login_required
def register_face(client_id):
    """
    Recibe el embedding (vector de ~128 floats) generado por face-api.js
    en el navegador y lo asocia al cliente. Requiere consentimiento previo.
    """
    data = request.get_json(silent=True) or {}
    embedding = data.get('embedding')
    consent = data.get('consent', False)

    if not embedding or not isinstance(embedding, list):
        return jsonify({'ok': False, 'error': 'Embedding inválido.'}), 400

    client = Client.query.get(client_id)
    if not client:
        return jsonify({'ok': False, 'error': 'Cliente no encontrado.'}), 404

    if not consent and not client.biometric_consent:
        return jsonify({
            'ok': False,
            'error': 'Falta el consentimiento del cliente para guardar datos biométricos (Habeas Data).'
        }), 400

    if consent:
        FaceService.set_consent(client_id, True)

    FaceService.save_embedding(client_id, embedding)
    return jsonify({'ok': True, 'message': f'Rostro registrado para {client.full_name}.'})


@face_bp.route('/api/face/clear/<int:client_id>', methods=['POST'])
@login_required
def clear_face(client_id):
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'ok': False, 'error': 'Cliente no encontrado.'}), 404
    FaceService.clear_embedding(client_id)
    return jsonify({'ok': True, 'message': f'Rostro eliminado de {client.full_name}.'})


@face_bp.route('/api/face/lookup', methods=['POST'])
@login_required
def lookup_face():
    """
    Igual que verify_face, pero solo identifica al cliente — no registra
    asistencia ni valida membresía. Se usa en el botón "Consultar Cliente"
    del dashboard para llevar directo a la ficha del cliente.
    """
    data = request.get_json(silent=True) or {}
    embedding = data.get('embedding')

    if not embedding or not isinstance(embedding, list):
        return jsonify({'ok': False, 'status': 'error', 'message': 'Embedding inválido.'}), 400

    client, distance = FaceService.find_match(embedding)

    if not client:
        return jsonify({'ok': True, 'status': 'not_found', 'message': 'Rostro no reconocido.'})

    return jsonify({
        'ok': True,
        'status': 'found',
        'client_id': client.id,
        'client_name': client.full_name,
        'distance': round(distance, 3) if distance is not None else None,
    })


@face_bp.route('/api/face/verify', methods=['POST'])
@login_required
def verify_face():
    """
    Recibe un embedding capturado en vivo (pantalla de check-in), busca el
    cliente más parecido y, si tiene membresía activa, registra su asistencia
    automáticamente — igual que el flujo manual de attendance.register.
    """
    data = request.get_json(silent=True) or {}
    embedding = data.get('embedding')

    if not embedding or not isinstance(embedding, list):
        return jsonify({'ok': False, 'status': 'error', 'message': 'Embedding inválido.'}), 400

    client, distance = FaceService.find_match(embedding)

    if not client:
        return jsonify({
            'ok': True,
            'status': 'not_found',
            'message': 'Rostro no reconocido. Intenta de nuevo o busca manualmente.',
        })

    if not _has_active_membership(client.id):
        return jsonify({
            'ok': True,
            'status': 'no_membership',
            'client_name': client.full_name,
            'client_id': client.id,
            'message': f'{client.full_name} no tiene membresía activa.',
        })

    AttendanceService.register(client.id)

    return jsonify({
        'ok': True,
        'status': 'checked_in',
        'client_name': client.full_name,
        'client_id': client.id,
        'distance': round(distance, 3) if distance is not None else None,
        'message': f'Bienvenido, {client.full_name}.',
    })
