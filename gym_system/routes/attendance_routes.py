from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.models.attendance import Attendance
from database.models.client import Client
from database.db import db
from services.attendance_service import AttendanceService

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    today_list = AttendanceService.today()
    clients = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
    return render_template('attendance/attendance.html', today_list=today_list, clients=clients)

@attendance_bp.route('/register', methods=['POST'])
def register():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    client_id = request.form.get('client_id')
    if client_id:
        AttendanceService.register(int(client_id))
        flash('Asistencia registrada.', 'success')
    return redirect(url_for('attendance.index'))
