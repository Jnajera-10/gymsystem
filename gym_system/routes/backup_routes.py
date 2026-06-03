from flask import Blueprint, render_template, redirect, url_for, flash, session
from services.backup_service import BackupService

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

@backup_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        backups = BackupService.list_backups()
    except:
        backups = []
    return render_template('backups/backups.html', backups=backups)

@backup_bp.route('/create', methods=['POST'])
def create():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        BackupService.create_backup()
        flash('Respaldo creado.', 'success')
    except Exception as e:
        flash(f'Error al crear respaldo: {e}', 'danger')
    return redirect(url_for('backup.index'))
