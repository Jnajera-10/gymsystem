from flask import Blueprint
from controllers.auth_controller import AuthController

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

auth_bp.add_url_rule('/login', 'login', AuthController.login, methods=['GET', 'POST'])
auth_bp.add_url_rule('/welcome', 'welcome', AuthController.welcome)
auth_bp.add_url_rule('/logout', 'logout', AuthController.logout)
auth_bp.add_url_rule('/forgot-password', 'forgot_password', AuthController.forgot_password, methods=['GET', 'POST'])
