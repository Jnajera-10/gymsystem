from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.models.attendance import Attendance
from database.models.client import Client
from database.models.payment import Payment
from database.db import db
from services.attendance_service import AttendanceService
from utils.security import login_required
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


def _clients_with_active_membership():
    """
    Retorna solo los clientes que tienen al menos una membresía vigente hoy.
    Se usa en la pantalla de registro de asistencia.
    """
    today = datetime.now(BOGOTA).date()
    # Subconsulta: IDs de clientes con pago activo hoy
    from sqlalchemy import select
    active_ids_select = (
        select(Payment.client_id)
        .where(
            Payment.is_deleted == False,
            Payment.start_date <= today,
            # Las membresías congeladas también aparecen: así recepción puede
            # intentar marcarlas y el admin recibe el aviso.
            db.or_(Payment.end_date >= today, Payment.is_frozen == True),
        )
        .distinct()
    )
    return (
        Client.query
        .filter(Client.is_active == True)
        .filter(Client.id.in_(active_ids_select))
        .order_by(Client.full_name)
        .all()
    )


@attendance_bp.route('/')
@login_required
def index():
    today_list     = AttendanceService.today()
    active_clients = _clients_with_active_membership()

    # Búsqueda rápida por nombre o documento (solo entre activos con membresía)
    q = request.args.get('q', '').strip()
    if q:
        active_clients = [
            c for c in active_clients
            if q.lower() in c.full_name.lower() or q in (c.document_number or '')
        ]

    return render_template(
        'attendance/attendance.html',
        today_list     = today_list,
        clients        = active_clients,
        search_q       = q,
    )


@attendance_bp.route('/register', methods=['POST'])
@login_required
def register():
    client_id = request.form.get('client_id')
    if not client_id:
        flash('Selecciona un cliente.', 'danger')
        return redirect(url_for('attendance.index'))

    # Verificar membresía activa antes de registrar
    # (una membresía congelada cuenta como vigente, igual que en el flujo facial)
    today = datetime.now(BOGOTA).date()
    has_active = Payment.query.filter(
        Payment.client_id  == int(client_id),
        Payment.is_deleted == False,
        Payment.start_date <= today,
        db.or_(Payment.end_date >= today, Payment.is_frozen == True),
    ).first()

    if not has_active:
        client = Client.query.get(int(client_id))
        nombre = client.full_name if client else 'Cliente'
        flash(f'⚠️ {nombre} no tiene membresía activa. Registra un pago primero.', 'warning')
        return redirect(url_for('attendance.index'))

    # ── Membresía congelada: avisar al admin por Telegram ──────────
    frozen_payment = AttendanceService.get_frozen_payment(int(client_id))
    if frozen_payment:
        client = Client.query.get(int(client_id))
        AttendanceService.notify_frozen_attempt(
            client, frozen_payment,
            source='manual',
            registered_by=session.get('user_username'),
        )
        flash(f'❄️ La membresía de {client.full_name} está congelada. Se notificó al administrador.', 'warning')

    AttendanceService.register(int(client_id))
    flash('✅ Asistencia registrada.', 'success')
    return redirect(url_for('attendance.index'))


@attendance_bp.route('/<int:aid>/delete', methods=['POST'])
@login_required
def delete(aid):
    a = Attendance.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash('Asistencia eliminada.', 'warning')
    return redirect(url_for('attendance.index'))
