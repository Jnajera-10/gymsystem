from flask import request, session, redirect, url_for, flash, render_template
from database.models.delete_request import DeleteRequest
from database.models.payment import Payment
from database.models.user import User
from database.db import db
from services.audit_service import AuditService
import pytz
from datetime import datetime

BOGOTA = pytz.timezone('America/Bogota')


class DeleteRequestController:

    @staticmethod
    def request_delete(payment_id):
        """Recepcionista o admin solicita eliminar un pago."""
        payment = Payment.query.get_or_404(payment_id)

        # Si ya hay una solicitud pendiente para este pago, no crear otra
        existing = DeleteRequest.query.filter_by(
            payment_id=payment_id, status='pendiente'
        ).first()
        if existing:
            flash('Ya existe una solicitud pendiente para este pago.', 'warning')
            return redirect(request.referrer or url_for('payments.index'))

        # Si es admin, puede eliminar directo sin esperar aprobación
        user_role = session.get('user_role')
        if user_role == 'admin':
            from services.payment_service import PaymentService
            mirrors = PaymentService.soft_delete_payment(payment)
            db.session.commit()
            AuditService.log(
                'DELETE_DIRECTO', 'payments', payment.id,
                f'${payment.amount:,.0f} — {payment.client.full_name if payment.client else "?"}',
                'Eliminado por admin.'
            )
            for mirror in mirrors:
                AuditService.log(
                    'DELETE_DIRECTO', 'payments', mirror.id,
                    f'${mirror.amount:,.0f}',
                    f'Eliminado (espejo vinculado al pago #{payment.id}).'
                )
            flash('✅ Pago eliminado correctamente.', 'success')
            return redirect(url_for('payments.index'))

        # Recepcionista → crear solicitud pendiente
        dr = DeleteRequest(
            payment_id    = payment_id,
            requested_by  = session.get('user_id'),
            justification = '',
            status        = 'pendiente',
        )
        db.session.add(dr)
        db.session.commit()

        AuditService.log(
            'SOLICITUD_ELIMINACION', 'payments', payment.id,
            f'${payment.amount:,.0f} — {payment.client.full_name if payment.client else "?"}',
            'Solicitud de eliminación enviada.'
        )
        flash('✅ Solicitud enviada. El administrador recibirá la notificación y decidirá.', 'info')
        return redirect(request.referrer or url_for('payments.index'))

    @staticmethod
    def list_pending():
        """Admin: ver todas las solicitudes pendientes."""
        pendientes  = DeleteRequest.query.filter_by(status='pendiente').order_by(DeleteRequest.created_at.desc()).all()
        historial   = DeleteRequest.query.filter(DeleteRequest.status != 'pendiente').order_by(DeleteRequest.reviewed_at.desc()).limit(30).all()
        return render_template(
            'delete_requests/list.html',
            pendientes = pendientes,
            historial  = historial,
        )

    @staticmethod
    def approve(dr_id):
        """Admin aprueba la solicitud → elimina el pago."""
        dr = DeleteRequest.query.get_or_404(dr_id)
        if dr.status != 'pendiente':
            flash('Esta solicitud ya fue procesada.', 'warning')
            return redirect(url_for('delete_requests.list_pending'))

        payment = dr.payment
        from services.payment_service import PaymentService
        mirrors = PaymentService.soft_delete_payment(payment)
        dr.status      = 'aprobada'
        dr.reviewed_by = session.get('user_id')
        dr.review_note = request.form.get('review_note', '').strip() or None
        dr.reviewed_at = datetime.now(BOGOTA)
        db.session.commit()

        AuditService.log(
            'DELETE_APROBADO', 'payments', payment.id,
            f'Solicitud #{dr.id} de {dr.requester.username if dr.requester else "?"}',
            f'Aprobada por admin. {dr.review_note or ""}'
        )
        for mirror in mirrors:
            AuditService.log(
                'DELETE_APROBADO', 'payments', mirror.id,
                f'Solicitud #{dr.id}',
                f'Eliminado (espejo vinculado al pago #{payment.id})'
            )
        flash(f'✅ Solicitud aprobada. Pago de ${payment.amount:,.0f} eliminado.', 'success')
        return redirect(url_for('delete_requests.list_pending'))

    @staticmethod
    def reject(dr_id):
        """Admin rechaza la solicitud → el pago sigue activo."""
        dr = DeleteRequest.query.get_or_404(dr_id)
        if dr.status != 'pendiente':
            flash('Esta solicitud ya fue procesada.', 'warning')
            return redirect(url_for('delete_requests.list_pending'))

        dr.status      = 'rechazada'
        dr.reviewed_by = session.get('user_id')
        dr.review_note = request.form.get('review_note', '').strip() or None
        dr.reviewed_at = datetime.now(BOGOTA)
        db.session.commit()

        payment = dr.payment
        AuditService.log(
            'DELETE_RECHAZADO', 'payments', payment.id if payment else None,
            f'Solicitud #{dr.id} de {dr.requester.username if dr.requester else "?"}',
            f'Rechazada por admin. {dr.review_note or ""}'
        )
        flash('Solicitud rechazada. El pago permanece activo.', 'warning')
        return redirect(url_for('delete_requests.list_pending'))
