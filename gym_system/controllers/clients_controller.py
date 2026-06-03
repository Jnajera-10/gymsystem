from flask import request, redirect, url_for, flash, render_template
from database.models.client import Client
from database.models.payment import Payment
from database.db import db
from services.audit_service import AuditService
from utils.validators import validate_client
import pytz
from datetime import datetime, date

BOGOTA = pytz.timezone('America/Bogota')


class ClientsController:

    @staticmethod
    def index():
        search = request.args.get('q', '')
        page = request.args.get('page', 1, type=int)
        per_page = 25

        query = Client.query.filter(Client.is_active == True)
        if search:
            query = query.filter(Client.full_name.ilike(f'%{search}%'))

        pagination = query.order_by(Client.full_name).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return render_template(
            'clients/clients.html',
            clients=pagination.items,
            pagination=pagination,
            search=search,
        )

    @staticmethod
    def create():
        if request.method == 'POST':
            errors = validate_client(request.form)
            if errors:
                for e in errors:
                    flash(e, 'danger')
                return render_template('clients/create_client.html', data=request.form)

            client = Client(
                full_name=request.form['full_name'],
                document_type=request.form['document_type'],
                document_number=request.form['document_number'],
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                birth_date=_parse_date(request.form.get('birth_date')),
                gender=request.form.get('gender'),
                address=request.form.get('address'),
                emergency_contact=request.form.get('emergency_contact'),
                emergency_phone=request.form.get('emergency_phone'),
                notes=request.form.get('notes'),
            )
            db.session.add(client)
            db.session.commit()
            AuditService.log('create', 'clients', client.id, None, client.full_name)
            try:
                from services.notification_service import NotificationService
                NotificationService.send_welcome(client)
            except Exception:
                pass
            flash('Cliente registrado exitosamente.', 'success')
            return redirect(url_for('clients.index'))
        return render_template('clients/create_client.html')

    @staticmethod
    def edit(client_id):
        client = Client.query.get_or_404(client_id)
        if request.method == 'POST':
            old_name = client.full_name

            client.full_name = request.form['full_name']
            client.document_type = request.form.get('document_type', client.document_type)
            client.document_number = request.form.get('document_number', client.document_number)
            client.email = request.form.get('email')
            client.phone = request.form.get('phone')
            client.birth_date = _parse_date(request.form.get('birth_date'))
            client.gender = request.form.get('gender')
            client.address = request.form.get('address')
            client.emergency_contact = request.form.get('emergency_contact')
            client.emergency_phone = request.form.get('emergency_phone')
            client.notes = request.form.get('notes')

            db.session.commit()
            AuditService.log('update', 'clients', client.id, old_name, client.full_name)
            flash('Cliente actualizado.', 'success')
            return redirect(url_for('clients.detail', client_id=client.id))
        return render_template('clients/edit_client.html', client=client)

    @staticmethod
    def deactivate(client_id):
        client = Client.query.get_or_404(client_id)

        # Verificar membresías activas (pagos vigentes)
        today = datetime.now(BOGOTA).date()
        active_payment = Payment.query.filter(
            Payment.client_id == client_id,
            Payment.end_date >= today,
            Payment.is_deleted == False,
        ).first()

        if active_payment:
            flash(
                f'⚠️ {client.full_name} tiene una membresía vigente hasta '
                f'{active_payment.end_date.strftime("%d/%m/%Y")}. '
                'Desactívalo igualmente solo si estás seguro.',
                'warning',
            )
            # Guardamos la intención en la sesión para confirmar en segundo clic
            from flask import session
            confirm_key = f'confirm_deactivate_{client_id}'
            if not session.get(confirm_key):
                session[confirm_key] = True
                return redirect(url_for('clients.index'))
            session.pop(confirm_key, None)

        client.is_active = False
        db.session.commit()
        AuditService.log('delete', 'clients', client.id, 'activo', 'inactivo')
        flash(f'Cliente {client.full_name} desactivado.', 'warning')
        return redirect(url_for('clients.index'))

    @staticmethod
    def detail(client_id):
        client = Client.query.get_or_404(client_id)
        today = datetime.now(BOGOTA).date()
        payments = Payment.query.filter_by(
            client_id=client_id, is_deleted=False
        ).order_by(Payment.payment_date.desc()).all()

        active_payment = next(
            (p for p in payments if p.end_date >= today), None
        )
        return render_template(
            'clients/client_details.html',
            client=client,
            payments=payments,
            active_payment=active_payment,
            today=today,
        )


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None
