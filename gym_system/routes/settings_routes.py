from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.models.settings import GymSettings
from database.db import db
from utils.security import login_required, role_required

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def index():
    s = GymSettings.query.first()
    if not s:
        s = GymSettings()
        db.session.add(s)
        db.session.commit()
    if request.method == 'POST':
        s.gym_name = request.form.get('gym_name', s.gym_name)
        s.address = request.form.get('address', s.address)
        s.phone = request.form.get('phone', s.phone)
        s.email = request.form.get('email', s.email)
        db.session.commit()
        flash('Configuración guardada.', 'success')
        return redirect(url_for('settings.index'))
    return render_template('settings/settings.html', settings=s)
