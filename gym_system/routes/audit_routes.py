from flask import Blueprint, render_template, session, redirect, url_for
from database.models.audit import AuditLog

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

@audit_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template('audit/audit.html', logs=logs)
