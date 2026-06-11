from flask import Blueprint
from controllers.clients_controller import ClientsController
 
client_bp = Blueprint('clients', __name__, url_prefix='/clients')
 
client_bp.add_url_rule('/', 'index', ClientsController.index)
client_bp.add_url_rule('/search', 'search', ClientsController.search)   # ← AJAX búsqueda
client_bp.add_url_rule('/create', 'create', ClientsController.create, methods=['GET', 'POST'])
client_bp.add_url_rule('/<int:client_id>/edit', 'edit', ClientsController.edit, methods=['GET', 'POST'])
client_bp.add_url_rule('/<int:client_id>/deactivate', 'deactivate', ClientsController.deactivate, methods=['POST'])
client_bp.add_url_rule('/<int:client_id>/activate', 'activate', ClientsController.activate, methods=['POST'])
client_bp.add_url_rule('/<int:client_id>/delete', 'delete', ClientsController.delete, methods=['POST'])
client_bp.add_url_rule('/<int:client_id>', 'detail', ClientsController.detail)
 