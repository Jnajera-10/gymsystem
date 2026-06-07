from database.models.payment import Payment, _get_shift
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
            return None, None, 'Membresía no encontrada.'

        start_date = datetime.strptime(form_data['start_date'], '%Y-%m-%d').date()
        end_date   = start_date + timedelta(days=membership.duration_days - 1)

        # --- Validación: Plan Pareja ---
        partner_client_id = None
        partner_payment   = None
        if membership.is_couple_plan:
            raw_partner = form_data.get('partner_client_id', '').strip()
            if not raw_partner:
                return None, None, 'El Plan Pareja requiere seleccionar un segundo cliente.'
            partner_client_id = int(raw_partner)
            if partner_client_id == int(form_data['client_id']):
                return None, None, 'Los dos clientes del Plan Pareja deben ser diferentes.'
            partner = Client.query.get(partner_client_id)
            if not partner or not partner.is_active:
                return None, None, 'El segundo cliente del Plan Pareja no existe o está inactivo.'

        # --- Validación: Plan Estudiantil ---
        if membership.is_student_plan:
            if form_data.get('is_student') != 'on':
                return None, None, 'El Plan Estudiantil es exclusivo para bachilleres. Confirma el requisito.'

        # --- Pago principal ---
        cash_received = None
        cash_change   = None
        if form_data.get('payment_method') == 'efectivo':
            try:
                cash_received = float(form_data.get('cash_received') or 0) or None
                if cash_received:
                    cash_change = max(0, cash_received - float(form_data['amount']))
            except (ValueError, TypeError):
                pass

        payment = Payment(
            client_id        = int(form_data['client_id']),
            membership_id    = int(form_data['membership_id']),
            amount           = float(form_data['amount']),
            start_date       = start_date,
            end_date         = end_date,
            payment_method   = form_data.get('payment_method', 'efectivo'),
            notes            = form_data.get('notes'),
            partner_client_id= partner_client_id,
            shift            = form_data.get('shift', _get_shift()),
            cash_received    = cash_received,
            cash_change      = cash_change,
        )
        db.session.add(payment)

        # --- Plan Pareja: pago espejo para el segundo cliente ---
        if membership.is_couple_plan and partner_client_id:
            partner_payment = Payment(
                client_id        = partner_client_id,
                membership_id    = int(form_data['membership_id']),
                amount           = 0,
                start_date       = start_date,
                end_date         = end_date,
                payment_method   = form_data.get('payment_method', 'efectivo'),
                notes            = f'Plan Pareja — vinculado al pago del cliente #{form_data["client_id"]}',
                partner_client_id= int(form_data['client_id']),
            )
            db.session.add(partner_payment)

        db.session.commit()
        return payment, partner_payment, None

    # ------------------------------------------------------------------
    # Helpers de ingresos
    # ------------------------------------------------------------------
    @staticmethod
    def today_income():
        today = datetime.now(BOGOTA).date()
        payments = Payment.query.filter(
            Payment.payment_date == today,
            Payment.is_deleted   == False,
        ).all()
        return sum(p.amount for p in payments)

    @staticmethod
    def month_income():
        now = datetime.now(BOGOTA)
        from sqlalchemy import extract
        payments = Payment.query.filter(
            extract('month', Payment.payment_date) == now.month,
            extract('year',  Payment.payment_date) == now.year,
            Payment.is_deleted == False,
        ).all()
        return sum(p.amount for p in payments)

    @staticmethod
    def month_payments_raw():
        """Retorna todos los pagos del mes actual (para desglose por método)."""
        now = datetime.now(BOGOTA)
        from sqlalchemy import extract
        return Payment.query.filter(
            extract('month', Payment.payment_date) == now.month,
            extract('year',  Payment.payment_date) == now.year,
            Payment.is_deleted == False,
        ).all()

    @staticmethod
    def income_since(since_date):
        """Total de ingresos desde una fecha dada (inclusive)."""
        payments = Payment.query.filter(
            Payment.payment_date >= since_date,
            Payment.is_deleted   == False,
        ).all()
        return sum(p.amount for p in payments)

    @staticmethod
    def payments_since_raw(since_date):
        """Retorna todos los pagos desde una fecha dada (para desglose por método)."""
        return Payment.query.filter(
            Payment.payment_date >= since_date,
            Payment.is_deleted   == False,
        ).all()
