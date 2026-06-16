from flask import request, session, redirect, url_for, flash, render_template
from database.models.user import User
from services.auth_service import AuthService

class AuthController:
    @staticmethod
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            remember = request.form.get('remember', False)
            user, error = AuthService.authenticate(username, password)
            if user:
                session['user_id']       = user.id
                session['user_role']     = user.role
                session['user_username'] = user.username
                session.permanent        = bool(remember)
                # Redirigir a la animación de bienvenida antes del dashboard
                return redirect(url_for('dashboard.index'))
            flash(error, 'danger')
        return render_template('auth/login.html')

    

    @staticmethod
    def logout():
        session.clear()
        return redirect(url_for('auth.login'))

    @staticmethod
    def forgot_password():
        if request.method == 'POST':
            email = request.form.get('email')
            AuthService.send_reset_email(email)
            flash('Si el correo existe, recibirás instrucciones.', 'info')
        return render_template('auth/forgot_password.html')
