from flask import Blueprint
from controllers.delete_request_controller import DeleteRequestController
from utils.security import login_required, admin_required

dr_bp = Blueprint('delete_requests', __name__, url_prefix='/delete-requests')

dr_bp.add_url_rule('/', 'list_pending', admin_required(DeleteRequestController.list_pending))
dr_bp.add_url_rule('/request/<int:payment_id>', 'request_delete',
                   login_required(DeleteRequestController.request_delete), methods=['POST'])
dr_bp.add_url_rule('/<int:dr_id>/approve', 'approve',
                   admin_required(DeleteRequestController.approve), methods=['POST'])
dr_bp.add_url_rule('/<int:dr_id>/reject', 'reject',
                   admin_required(DeleteRequestController.reject), methods=['POST'])
