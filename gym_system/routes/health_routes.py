from flask import Blueprint, jsonify, current_app
import pytz
from datetime import datetime

BOGOTA = pytz.timezone('America/Bogota')
health_bp = Blueprint('health', __name__)

# Control en memoria (se reinicia con el servidor, suficiente para free tier)
_last_job_date = None


@health_bp.route('/health')
def health():
    global _last_job_date

    today = datetime.now(BOGOTA).date()

    # Ejecutar job de vencimientos una vez por día
    if _last_job_date != today:
        try:
            from services.expiry_job import run_expiry_notifications
            run_expiry_notifications(current_app._get_current_object())
            _last_job_date = today
        except Exception as e:
            current_app.logger.error(f'expiry_job error: {e}')

    # Ejecutar reporte diario a las 10pm hora Colombia
    try:
        from services.daily_report_job import run_daily_report
        run_daily_report(current_app._get_current_object())
    except Exception as e:
        current_app.logger.error(f'daily_report error: {e}')

    return jsonify({'status': 'ok', 'time': str(datetime.now(BOGOTA))}), 200
