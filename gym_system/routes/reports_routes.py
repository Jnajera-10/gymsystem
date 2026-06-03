from flask import Blueprint, render_template, session, redirect, url_for
from services.report_service import ReportService

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    clients = ReportService.clients_report()
    return render_template('reports/reports.html', clients=clients)
