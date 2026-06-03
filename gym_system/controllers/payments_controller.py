from flask import request, redirect, url_for, flash, render_template
from database.models.payment import Payment
from database.models.client import Client
from database.models.membership import Membership
from database.db import db
from services.payment_service import PaymentService
from services.audit_service import AuditService
import logging
 
logger = logging.getLogger(__name__)
PER_PAGE = 30
 
 
class PaymentsController:
 
    @staticmethod
    def index():
        page = request.args.get('page', 1, type=int)
        pagination = (
            Payment.query
            .filter_by(is_deleted=False)
            .order_by(Payment.payment_date.desc())
            .paginate(page=page, per_page=PER_PAGE, error_out=False)
        )
        return render_template(
            'payments/payments.html',
            payments=pagination.items,
            pagination=pagination,
        )
 
    @staticmethod
    def create():
        clients = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
        memberships = Membership.query.filter_by(is_active=True).order_by(Membership.name).all()
        if request.method == 'POST':
            payment = PaymentService.register_payment(request.form)
            if payment:
                AuditService.log('create', 'payments', payment.id, None, str(payment.amount))
                try:
                    from services.notification_service import NotificationService
                    ok = NotificationService.send_payment_confirmation(payment)
                    if not ok:
                        flash('⚠️ Pago registrado, pero no se pudo enviar el email de confirmación. '
                              'Revisa las variables de entorno MAIL_* en Render.', 'warning')
                except Exception as exc:
                    logger.error(f'Error enviando email de pago: {exc}')
                    flash(f'⚠️ Pago registrado, pero error al enviar email: {exc}', 'warning')
                flash('Pago registrado correctamente.', 'success')
                return redirect(url_for('payments.receipt', payment_id=payment.id))
            flash('No se pudo registrar el pago.', 'danger')
        return render_template(
            'payments/create_payment.html',
            clients=clients,
            memberships=memberships,
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