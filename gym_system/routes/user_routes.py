from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.models.user import User
from database.db import db
from utils.security import hash_password

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    users = User.query.all()
    return render_template('users/users.html', users=users)

@user_bp.route('/create', methods=['GET', 'POST'])
def create():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=hash_password(request.form['password']),
            full_name=request.form['full_name'],
            role=request.form['role']
        )
        db.session.add(user)
        db.session.commit()
        flash('Usuario creado.', 'success')
        return redirect(url_for('user.index'))
    return render_template('users/create_user.html')

@user_bp.route('/<int:user_id>/deactivate', methods=['POST'])
def deactivate(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    flash('Usuario desactivado.', 'warning')
    return redirect(url_for('user.index'))
