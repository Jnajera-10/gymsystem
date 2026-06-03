from database.models.payment import Payment
from database.models.membership import Membership
from database.db import db
import pytz
from datetime import datetime, timedelta

BOGOTA = pytz.timezone('America/Bogota')

class PaymentService:
    @staticmethod
    def register_payment(form_data):
        membership = Membership.query.get(form_data['membership_id'])
        if not membership:
            return None
        start_date = datetime.strptime(form_data['start_date'], '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=membership.duration_days)
        payment = Payment(
            client_id=int(form_data['client_id']),
            membership_id=int(form_data['membership_id']),
            amount=float(form_data['amount']),
            start_date=start_date,
            end_date=end_date,
            payment_method=form_data.get('payment_method', 'efectivo'),
            notes=form_data.get('notes')
        )
        db.session.add(payment)
        db.session.commit()
        return payment

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
