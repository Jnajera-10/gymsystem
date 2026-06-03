from flask import Blueprint, render_template, session, redirect, url_for
from database.models.notifications import Notification

notification_bp = Blueprint('notification', __name__, url_prefix='/notification')

@notification_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
    return render_template('notifications/notifications.html', notifications=notifications)
