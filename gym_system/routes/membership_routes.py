from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.models.membership import Membership
from database.db import db

membership_bp = Blueprint('membership', __name__, url_prefix='/membership')

@membership_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    memberships = Membership.query.all()
    return render_template('memberships/memberships.html', memberships=memberships)

@membership_bp.route('/create', methods=['GET', 'POST'])
def create():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        m = Membership(
            name=request.form['name'],
            duration_days=int(request.form['duration_days']),
            price=float(request.form['price'])
        )
        db.session.add(m)
        db.session.commit()
        flash('Membresía creada.', 'success')
        return redirect(url_for('membership.index'))
    return render_template('memberships/create_membership.html')

@membership_bp.route('/<int:mid>/edit', methods=['GET', 'POST'])
def edit(mid):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    m = Membership.query.get_or_404(mid)
    if request.method == 'POST':
        m.name = request.form['name']
        m.duration_days = int(request.form['duration_days'])
        m.price = float(request.form['price'])
        db.session.commit()
        flash('Membresía actualizada.', 'success')
        return redirect(url_for('membership.index'))
    return render_template('memberships/create_membership.html', membership=m)

@membership_bp.route('/<int:mid>/delete', methods=['POST'])
def delete(mid):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    m = Membership.query.get_or_404(mid)
    m.is_active = False
    db.session.commit()
    flash('Membresía desactivada.', 'warning')
    return redirect(url_for('membership.index'))
