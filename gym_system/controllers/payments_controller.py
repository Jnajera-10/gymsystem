from datetime import datetime
import pytz
BOGOTA = pytz.timezone("America/Bogota")

from flask import request, redirect, url_for, flash, render_template
from database.models.payment import Payment, SHIFT_MORNING, SHIFT_AFTERNOON, _get_shift
from database.models.client import Client
from database.models.membership import Membership
from database.models.cash_register import CashRegister
from database.db import db
from services.payment_service import PaymentService
from services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)
PER_PAGE = 30


class PaymentsController:

    @staticmethod
    def index():
        page   = request.args.get('page', 1, type=int)
        # ── Filtros ──────────────────────────────────────────────
        q           = request.args.get('q', '').strip()
        plan_filter = request.args.get('plan', '').strip()
        method      = request.args.get('method', '').strip()
        date_from   = request.args.get('date_from', '').strip()
        date_to     = request.args.get('date_to', '').strip()

        query = Payment.query.filter_by(is_deleted=False)

        if q:
            query = (
                query
                .join(Client, Payment.client_id == Client.id)
                .filter(
                    db.or_(
                        Client.full_name.ilike(f'%{q}%'),
                        Client.document_number.ilike(f'%{q}%'),
                    )
                )
            )

        if plan_filter:
            try:
                query = query.filter(Payment.membership_id == int(plan_filter))
            except ValueError:
                pass

        if method:
            query = query.filter(Payment.payment_method == method)

        if date_from:
            try:
                query = query.filter(Payment.payment_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
            except ValueError:
                pass

        if date_to:
            try:
                query = query.filter(Payment.payment_date <= datetime.strptime(date_to, '%Y-%m-%d').date())
            except ValueError:
                pass

        pagination = query.order_by(Payment.payment_date.desc()).paginate(
            page=page, per_page=PER_PAGE, error_out=False
        )

        memberships = Membership.query.filter_by(is_active=True).order_by(Membership.name).all()

        today = datetime.now(BOGOTA).date()
        return render_template(
            'payments/payments.html',
            payments    = pagination.items,
            pagination  = pagination,
            memberships = memberships,
            today       = today,
            q           = q,
            plan_filter = plan_filter,
            method      = method,
            date_from   = date_from,
            date_to     = date_to,
        )

    @staticmethod
    def create():
        clients     = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
        memberships = Membership.query.filter_by(is_active=True).order_by(Membership.name).all()

        if request.method == 'POST':
            payment, partner_payment, error = PaymentService.register_payment(request.form)
            if error:
                flash(error, 'danger')
            elif payment:
                AuditService.log('create', 'payments', payment.id, None, str(payment.amount))
                _send_payment_email(payment)

                if partner_payment:
                    AuditService.log('create', 'payments', partner_payment.id, None, 'Plan Pareja (espejo)')
                    _send_couple_email(partner_payment, payment.client)
                    flash('✅ Membresía activada también para el segundo cliente del Plan Pareja.', 'info')

                flash('Pago registrado correctamente.', 'success')
                return redirect(url_for('payments.receipt', payment_id=payment.id))
            else:
                flash('No se pudo registrar el pago.', 'danger')

        return render_template(
            'payments/create_payment.html',
            clients       = clients,
            memberships   = memberships,
            current_shift = _get_shift(),
            today         = datetime.now(BOGOTA).strftime('%Y-%m-%d'),
        )

    @staticmethod
    def renew():
        """
        Renovación rápida: precarga el formulario de nuevo pago con el
        cliente y la membresía seleccionados, y calcula la fecha de
        inicio como el día siguiente al vencimiento actual (si aún está
        activa) o hoy si ya venció.

        GET  /payments/renew?client_id=X&membership_id=Y  → muestra el form
        POST /payments/renew                               → registra el pago
        """
        today = datetime.now(BOGOTA).date()

        if request.method == 'POST':
            # Reutiliza exactamente la misma lógica que /payments/create
            payment, partner_payment, error = PaymentService.register_payment(request.form)
            if error:
                flash(error, 'danger')
                # Volver al form de renovación con los datos precargados
                client_id     = request.form.get('client_id')
                membership_id = request.form.get('membership_id')
                return redirect(url_for(
                    'payments.renew',
                    client_id=client_id,
                    membership_id=membership_id,
                ))
            elif payment:
                AuditService.log('create', 'payments', payment.id, None, str(payment.amount))
                _send_payment_email(payment)
                if partner_payment:
                    AuditService.log('create', 'payments', partner_payment.id, None, 'Plan Pareja (espejo)')
                    _send_couple_email(partner_payment, payment.client)
                    flash('✅ Membresía activada también para el segundo cliente del Plan Pareja.', 'info')
                flash('Renovación registrada correctamente.', 'success')
                return redirect(url_for('payments.receipt', payment_id=payment.id))
            else:
                flash('No se pudo registrar la renovación.', 'danger')

        # ── GET: precarga de datos ────────────────────────────────
        client_id     = request.args.get('client_id', type=int)
        membership_id = request.args.get('membership_id', type=int)

        client     = Client.query.get_or_404(client_id) if client_id else None
        membership = Membership.query.get(membership_id) if membership_id else None

        # Calcular fecha de inicio sugerida
        suggested_start = today
        if client and membership:
            # Buscar el último pago activo de este cliente con esta membresía
            last_payment = (
                Payment.query
                .filter(
                    Payment.client_id     == client.id,
                    Payment.membership_id == membership.id,
                    Payment.is_deleted    == False,
                )
                .order_by(Payment.end_date.desc())
                .first()
            )
            if last_payment and last_payment.end_date >= today:
                # La membresía aún no venció → la renovación arranca al día siguiente
                from datetime import timedelta
                suggested_start = last_payment.end_date + timedelta(days=1)

        clients     = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
        memberships = Membership.query.filter_by(is_active=True).order_by(Membership.name).all()

        return render_template(
            'payments/renew_payment.html',
            clients          = clients,
            memberships      = memberships,
            preselect_client = client,
            preselect_membership = membership,
            suggested_start  = suggested_start,
        )

    @staticmethod
    def receipt(payment_id):
        payment = Payment.query.get_or_404(payment_id)
        return render_template('payments/receipt.html', payment=payment)

    @staticmethod
    def delete(payment_id):
        payment = Payment.query.get_or_404(payment_id)
        payment.is_deleted = True
        db.session.commit()
        AuditService.log('delete', 'payments', payment.id, str(payment.amount), 'eliminado')
        flash('Pago eliminado.', 'warning')
        return redirect(url_for('payments.index'))


# ──────────────────────────────────────────────────────────────────────
# Helpers de email
# ──────────────────────────────────────────────────────────────────────
def _send_payment_email(payment):
    try:
        client = payment.client
        if not client or not client.email:
            return
        import os
        if not os.environ.get('BREVO_API_KEY') or not os.environ.get('MAIL_FROM'):
            flash('⚠️ Pago registrado. Email no enviado: revisa BREVO_API_KEY y MAIL_FROM en Render.', 'warning')
            return
        from services.notification_service import NotificationService
        ok = NotificationService.send_payment_confirmation(payment)
        if ok:
            flash(f'📧 Confirmación enviada a {client.email}', 'info')
        else:
            flash('⚠️ Pago registrado, pero el email de confirmación falló.', 'warning')
    except Exception as exc:
        logger.error(f'[EMAIL] Error pago {payment.id}: {exc}', exc_info=True)
        flash('⚠️ Pago registrado, pero error al enviar email.', 'warning')


def _send_couple_email(partner_payment, main_client):
    """Notifica al segundo cliente del Plan Pareja."""
    try:
        partner = partner_payment.client
        if not partner or not partner.email:
            return
        import os
        if not os.environ.get('BREVO_API_KEY') or not os.environ.get('MAIL_FROM'):
            return
        from services.notification_service import NotificationService
        NotificationService.send_couple_plan_notification(partner_payment, main_client)
    except Exception as exc:
        logger.error(f'[EMAIL] Error Plan Pareja notificación: {exc}', exc_info=True)
