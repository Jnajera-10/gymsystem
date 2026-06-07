from flask import Blueprint
from controllers.dashboard_controller import DashboardController

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')

dashboard_bp.add_url_rule('/', 'index', DashboardController.index, methods=['GET', 'POST'])
