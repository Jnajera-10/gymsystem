from database.models.payment import Payment
from database.models.membership import Membership
from database.models.client import Client
from database.db import db
import pytz
from datetime import datetime, timedelta

BOGOTA = pytz.timezone('America/Bogota')


class PaymentService:

    @staticmethod
    def register_payment(form_data):
        membership = Membership.query.get(form_data['membership_id'])
        if not membership:
            return None, 'Membresía no encontrada.'

        start_date = datetime.strptime(form_data['start_date'], '%Y-%m-%d').date()

        # -------------------------------------------------------
        # Cálculo de end_date
        # La membresía vence a las 23:59 del último día INCLUSIVE.
        # Ejemplo diario (1 día):  inicia el 4 → vence el 4 a 23:59
        # Ejemplo mensual (30 días): inicia 04/06 → vence 03/07 a 23:59
        #   …pero con 30 días y start_date 04/06:
        #   04/06 + 30 - 1 = 03/07  ← correcto
        # Plan mensual "mismo día del mes siguiente":
        #   Si quieres exactamente el 04/07 (no el 03/07),
        #   configura duration_days = 30 y el end_date queda 03/07.
        #   Para que quede 04/07 pon duration_days = 31 en ese plan.
        # La regla es: end_date = start_date + (duration_days - 1)
        # -------------------------------------------------------
        end_date = start_date + timedelta(days=membership.duration_days - 1)

        # --- Validación: Plan Pareja ---
        partner_client_id = None
        if membership.is_couple_plan:
            raw_partner = form_data.get('partner_client_id', '').strip()
            if not raw_partner:
                return None, 'El Plan Pareja requiere seleccionar un segundo cliente.'
            partner_client_id = int(raw_partner)
            if partner_client_id == int(form_data['client_id']):
                return None, 'Los dos clientes del Plan Pareja deben ser diferentes.'
            partner = Client.query.get(partner_client_id)
            if not partner or not partner.is_active:
                return None, 'El segundo cliente del Plan Pareja no existe o está inactivo.'

        # --- Validación: Plan Estudiantil ---
        if membership.is_student_plan:
            is_student = form_data.get('is_student') == 'on'
            if not is_student:
                return None, 'El Plan Estudiantil es exclusivo para estudiantes de bachillerato. Confirma que el cliente cumple el requisito.'

        payment = Payment(
            client_id=int(form_data['client_id']),
            membership_id=int(form_data['membership_id']),
            amount=float(form_data['amount']),
            start_date=start_date,
            end_date=end_date,
            payment_method=form_data.get('payment_method', 'efectivo'),
            notes=form_data.get('notes'),
            partner_client_id=partner_client_id,
        )
        db.session.add(payment)
        db.session.commit()
        return payment, None

    # ------------------------------------------------------------------
    # Helpers de ingresos (sin cambios)
    # ------------------------------------------------------------------
    @staticmethod
    def today_income():
        today = datetime.now(BOGOTA).date()
        payments = Payment.query.filter(
            Payment.payment_date == today,
            Payment.is_deleted == False
        ).all()
        return sum(p.amount for p in payments)

    @staticmethod
    def month_income():
        now = datetime.now(BOGOTA)
        from sqlalchemy import extract
        payments = Payment.query.filter(
            extract('month', Payment.payment_date) == now.month,
            extract('year', Payment.payment_date) == now.year,
            Payment.is_deleted == False
        ).all()
        return sum(p.amount for p in payments)
