import threading

from flask import request, redirect, url_for, flash, render_template, jsonify
from database.models.client import Client
from database.models.payment import Payment
from database.models.attendance import Attendance
from database.models.notifications import Notification
from database.models.sales import Sale, SaleItem
from database.db import db
from services.audit_service import AuditService
from utils.validators import validate_client
import pytz
from datetime import datetime, date

BOGOTA = pytz.timezone('America/Bogota')


# ---------------------------------------------------------------------------
# Helper: envía el email de bienvenida en un hilo separado para que la
# respuesta HTTP sea inmediata y el worker de gunicorn no se quede esperando.
# ---------------------------------------------------------------------------
def _send_welcome_async(app, client_id: int):
    """Ejecuta send_welcome() fuera del ciclo de la request."""
    with app.app_context():
        try:
            from database.models.client import Client as _Client
            from services.notification_service import NotificationService
            client = _Client.query.get(client_id)
            if client:
                NotificationService.send_welcome(client)
        except Exception:
            pass  # Errores de email no deben tumbar el proceso background


class ClientsController:

    @staticmethod
    def search():
        """AJAX: devuelve JSON con clientes activos que coincidan con ?q=texto"""
        q = request.args.get('q', '').strip()
        query = Client.query.filter_by(is_active=True)
        if q:
            query = query.filter(
                db.or_(
                    Client.full_name.ilike(f'%{q}%'),
                    Client.document_number.ilike(f'%{q}%'),
                )
            )
        clients = query.order_by(Client.full_name).limit(20).all()
        return jsonify([
            {'id': c.id, 'text': f'{c.full_name} — {c.document_number}'}
            for c in clients
        ])

    @staticmethod
    def index():
        search = request.args.get('q', '')
        show_inactive = request.args.get('inactivos') == '1'
        page = request.args.get('page', 1, type=int)
        per_page = 25

        if show_inactive:
            query = Client.query.filter(Client.is_active == False)
        else:
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
            show_inactive=show_inactive,
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

            # ---------------------------------------------------------------
            # FIX TIMEOUT: el email se dispara en un hilo separado.
            # La respuesta HTTP llega de inmediato; el email viaja en segundo
            # plano sin bloquear el worker de gunicorn.
            # ---------------------------------------------------------------
            if client.email:
                from flask import current_app
                app = current_app._get_current_object()
                t = threading.Thread(
                    target=_send_welcome_async,
                    args=(app, client.id),
                    daemon=True,
                )
                t.start()

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
                'Se desactivó de todas formas.',
                'warning',
            )

        client.is_active = False
        db.session.commit()
        AuditService.log('delete', 'clients', client.id, 'activo', 'inactivo')
        flash(f'Cliente {client.full_name} desactivado.', 'warning')
        return redirect(url_for('clients.index'))

    @staticmethod
    def activate(client_id):
        client = Client.query.get_or_404(client_id)
        client.is_active = True
        db.session.commit()
        AuditService.log('update', 'clients', client.id, 'inactivo', 'activo')
        flash(f'✅ Cliente {client.full_name} reactivado correctamente.', 'success')
        return redirect(url_for('clients.index'))

    @staticmethod
    def delete(client_id):
        """Elimina físicamente el cliente y todos sus registros relacionados.
        Esto libera el documento para que se pueda volver a registrar."""
        client = Client.query.get_or_404(client_id)
        name = client.full_name

        # ---------------------------------------------------------------
        # PROTECCIÓN DE INGRESOS DEL MES: si el cliente tiene pagos
        # registrados dentro del mes actual, no se permite el borrado
        # físico porque eliminaría esos montos de los reportes de
        # ingresos (mes actual, "desde inicio de mes", etc.) de forma
        # retroactiva y descuadraría la caja.
        # En ese caso, solo se desactiva el cliente (igual que el botón
        # "Desactivar").
        # ---------------------------------------------------------------
        today = datetime.now(BOGOTA).date()
        month_start = date(today.year, today.month, 1)
        has_month_payments = Payment.query.filter(
            Payment.client_id == client_id,
            Payment.payment_date >= month_start,
            Payment.is_deleted == False,
        ).first() is not None

        if has_month_payments:
            client.is_active = False
            db.session.commit()
            AuditService.log(
                'update', 'clients', client.id, 'activo',
                'inactivo (no se pudo eliminar: tiene pagos del mes actual)',
            )
            flash(
                f'⚠️ {name} tiene pagos registrados este mes, así que no se '
                'eliminó por completo (esto afectaría los reportes de ingresos). '
                'Se desactivó en su lugar.',
                'warning',
            )
            return redirect(url_for('clients.index'))

        # ---------------------------------------------------------------
        # FIX FOREIGNKEYVIOLATION: hay que borrar en orden de dependencia.
        #
        # Árbol de FKs:
        #   clients
        #     ├── notifications  (client_id)
        #     ├── attendances    (client_id)
        #     ├── payments       (client_id)
        #     └── sales          (client_id)
        #           └── sale_items (sale_id)   ← había que borrar esto primero
        #
        # sale_items referencia a sales, así que se elimina antes que sales.
        # ---------------------------------------------------------------

        # 0. limpiar referencias "partner_client_id" en pagos de OTROS
        #    clientes que apunten a este cliente (Plan Pareja), para no
        #    dejar una FK colgando hacia un cliente eliminado.
        Payment.query.filter_by(partner_client_id=client_id).update(
            {Payment.partner_client_id: None}, synchronize_session=False
        )

        # 1. sale_items de las ventas de este cliente
        sale_ids = [s.id for s in Sale.query.filter_by(client_id=client_id).all()]
        if sale_ids:
            SaleItem.query.filter(SaleItem.sale_id.in_(sale_ids)).delete(
                synchronize_session=False
            )

        # 2. ventas
        Sale.query.filter_by(client_id=client_id).delete()

        # 3. resto de tablas dependientes
        Notification.query.filter_by(client_id=client_id).delete()
        Attendance.query.filter_by(client_id=client_id).delete()
        Payment.query.filter_by(client_id=client_id).delete()

        # 4. el cliente
        db.session.delete(client)
        db.session.commit()

        AuditService.log('delete', 'clients', client_id, name, 'ELIMINADO PERMANENTEMENTE')
        flash(
            f'Cliente {name} eliminado permanentemente. '
            'Su documento ya puede volver a registrarse.',
            'success',
        )
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
        # Último pago aunque esté vencido (para mostrar botón renovar)
        last_payment = payments[0] if payments else None

        return render_template(
            'clients/client_details.html',
            client=client,
            payments=payments,
            active_payment=active_payment,
            last_payment=last_payment,
            today=today,
        )


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None
