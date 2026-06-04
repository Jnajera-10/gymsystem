from flask import Blueprint, render_template
from database.models.notifications import Notification
from utils.security import login_required

notification_bp = Blueprint('notification', __name__, url_prefix='/notification')

@notification_bp.route('/')
@login_required
def index():
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
    return render_template('notifications/notifications.html', notifications=notifications)
