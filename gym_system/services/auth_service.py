import bcrypt
from database.models.user import User
from database.db import db
import pytz
from datetime import datetime, timedelta

BOGOTA = pytz.timezone('America/Bogota')
MAX_ATTEMPTS = 5

class AuthService:
    @staticmethod
    def authenticate(username, password):
        user = User.query.filter_by(username=username, is_active=True).first()
        if not user:
            return None, 'Usuario o contraseña incorrectos.'
        now = datetime.now(BOGOTA)
        # La BD guarda DateTime SIN zona horaria (hora de Bogotá). Se compara siempre
        # en "naive Bogotá" para no mezclar fechas con y sin zona (TypeError → 500).
        now_naive = now.replace(tzinfo=None)

        locked = user.locked_until
        if locked is not None:
            if locked.tzinfo is not None:
                locked = locked.astimezone(BOGOTA).replace(tzinfo=None)
            if locked > now_naive:
                return None, f'Cuenta bloqueada hasta {locked.strftime("%H:%M")}.'
            # El bloqueo ya venció: se limpia para que empiece con intentos en cero
            user.locked_until = None
            user.failed_attempts = 0

        if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            user.failed_attempts = 0
            user.locked_until = None
            user.last_login = now_naive
            db.session.commit()
            return user, None
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= MAX_ATTEMPTS:
            user.locked_until = now_naive + timedelta(minutes=15)
        db.session.commit()
        remaining = MAX_ATTEMPTS - user.failed_attempts
        return None, f'Contraseña incorrecta. Intentos restantes: {max(0, remaining)}.'

    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def send_reset_email(email):
        from services.notification_service import NotificationService
        user = User.query.filter_by(email=email).first()
        if user:
            NotificationService.send_password_reset(user)
