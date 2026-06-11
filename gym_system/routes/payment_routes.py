from flask import Blueprint
from controllers.payments_controller import PaymentsController
from utils.security import login_required, admin_required

payment_bp = Blueprint('payments', __name__, url_prefix='/payments')

payment_bp.add_url_rule('/', 'index', login_required(PaymentsController.index))
payment_bp.add_url_rule('/create', 'create', login_required(PaymentsController.create), methods=['GET', 'POST'])
payment_bp.add_url_rule('/<int:payment_id>/receipt', 'receipt', login_required(PaymentsController.receipt))
payment_bp.add_url_rule('/<int:payment_id>/extend', 'extend', admin_required(PaymentsController.extend_days), methods=['POST'])
payment_bp.add_url_rule('/<int:payment_id>/delete', 'delete', admin_required(PaymentsController.delete), methods=['POST'])

# ── Renovación rápida: precarga el formulario con cliente y plan ──
payment_bp.add_url_rule('/renew', 'renew', login_required(PaymentsController.renew), methods=['GET', 'POST'])
