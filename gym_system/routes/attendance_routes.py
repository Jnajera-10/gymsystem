from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.models.attendance import Attendance
from database.models.client import Client
from database.db import db
from services.attendance_service import AttendanceService
from utils.security import login_required

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/')
@login_required
def index():
    today_list = AttendanceService.today()
    clients = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
    return render_template('attendance/attendance.html', today_list=today_list, clients=clients)

@attendance_bp.route('/register', methods=['POST'])
@login_required
def register():
    client_id = request.form.get('client_id')
    if client_id:
        AttendanceService.register(int(client_id))
        flash('Asistencia registrada.', 'success')
    return redirect(url_for('attendance.index'))

@attendance_bp.route('/<int:aid>/delete', methods=['POST'])
@login_required
def delete(aid):
    a = Attendance.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash('Asistencia eliminada.', 'warning')
    return redirect(url_for('attendance.index'))
