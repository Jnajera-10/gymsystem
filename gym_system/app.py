import os
from flask import Flask
from config import Config
from database.db import db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from routes.auth_routes import auth_bp
    from routes.user_routes import user_bp
    from routes.client_routes import client_bp
    from routes.membership_routes import membership_bp
    from routes.payment_routes import payment_bp
    from routes.attendance_routes import attendance_bp
    from routes.inventory_routes import inventory_bp
    from routes.sales_routes import sales_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.reports_routes import reports_bp
    from routes.notification_routes import notification_bp
    from routes.settings_routes import settings_bp
    from routes.backup_routes import backup_bp
    from routes.audit_routes import audit_bp
    from routes.health_routes import health_bp
    from routes.email_test_routes import email_test_bp
    from routes.profile_routes import profile_bp
    from routes.expense_routes import expense_bp
    from routes.delete_request_routes import dr_bp  # ← faltaba, causaba 404
    from routes.telegram_routes import telegram_bp
    from routes.face_routes import face_bp

    for bp in [auth_bp, user_bp, client_bp, membership_bp, payment_bp,
               attendance_bp, inventory_bp, sales_bp, dashboard_bp,
               reports_bp, notification_bp, settings_bp, backup_bp, audit_bp,
               health_bp, email_test_bp, profile_bp, expense_bp, dr_bp,
               telegram_bp, face_bp]:
        app.register_blueprint(bp)

    # ── Protección global: redirige al login si no hay sesión ───────────
    # Las rutas públicas permitidas son solo las de autenticación y health.
    @app.before_request
    def require_login():
        from flask import session, redirect, url_for, request
        PUBLIC_ENDPOINTS = {
            'auth.login',
            'auth.logout',
            'auth.forgot_password',
            'health.ping',
            'static',
            'telegram.telegram_webhook',
        }
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('errors/500.html'), 500

    with app.app_context():
        db.create_all()

        # ── Migración automática: columnas de reconocimiento facial ──────
        # Idempotente (IF NOT EXISTS); corre en cada arranque para que no
        # haga falta entrar a la Shell de Render ni correr comandos manuales.
        try:
            from sqlalchemy import text as _text
            with db.engine.connect() as _conn:
                _conn.execute(_text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS face_embedding TEXT"))
                _conn.execute(_text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS face_registered_at TIMESTAMP"))
                _conn.execute(_text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS biometric_consent BOOLEAN DEFAULT FALSE"))
                _conn.execute(_text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS biometric_consent_at TIMESTAMP"))
                _conn.commit()
        except Exception:
            pass

        # ── Migración automática: columnas de congelar membresía ─────────
        try:
            from sqlalchemy import text as _text2
            with db.engine.connect() as _conn2:
                _conn2.execute(_text2("ALTER TABLE payments ADD COLUMN IF NOT EXISTS is_frozen BOOLEAN DEFAULT FALSE"))
                _conn2.execute(_text2("ALTER TABLE payments ADD COLUMN IF NOT EXISTS frozen_at DATE"))
                _conn2.execute(_text2("ALTER TABLE payments ADD COLUMN IF NOT EXISTS frozen_days_total INTEGER DEFAULT 0"))
                _conn2.commit()
        except Exception:
            pass

        # ── Migración automática: payment_method VARCHAR(30) → VARCHAR(120) ──
        # Necesario porque los pagos divididos (ej. "efectivo:50000|nequi:30000")
        # pueden superar 30 caracteres. Se ejecuta en cada arranque; es
        # idempotente (no hace nada si la columna ya es VARCHAR(120) o mayor).
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            columns = inspector.get_columns('payments')
            payment_method_col = next(
                (c for c in columns if c['name'] == 'payment_method'), None
            )
            current_length = getattr(payment_method_col['type'], 'length', None) \
                if payment_method_col else None
            if current_length is not None and current_length < 120:
                with db.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE payments ALTER COLUMN payment_method TYPE VARCHAR(120)"
                    ))
                    conn.commit()
        except Exception:
            # No bloquear el arranque de la app si la migración falla
            # (ej. tabla aún no existe en el primer deploy).
            pass

    return app

application = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=False)
