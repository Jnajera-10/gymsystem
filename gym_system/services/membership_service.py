from database.models.payment import Payment
from database.db import db
import pytz
from datetime import datetime, timedelta

BOGOTA = pytz.timezone('America/Bogota')
EXPIRY_WARN_DAYS = 3

class MembershipService:
    @staticmethod
    def count_active():
        from database.models.membership import Membership
        today = datetime.now(BOGOTA).date()
        # Clientes únicos con membresía vigente (o congelada), excluyendo plan diario
        return db.session.query(Payment.client_id).join(
            Membership, Payment.membership_id == Membership.id
        ).filter(
            db.or_(Payment.end_date >= today, Payment.is_frozen == True),
            Payment.is_deleted == False,
            Membership.membership_type != 'diario',
        ).distinct().count()

    @staticmethod
    def count_expiring_soon():
        """Próximas a vencer (≤3 días): excluye plan Diario y congeladas."""
        from database.models.membership import Membership
        today = datetime.now(BOGOTA).date()
        soon  = today + timedelta(days=EXPIRY_WARN_DAYS)
        return (
            Payment.query
            .join(Membership, Payment.membership_id == Membership.id)
            .filter(
                Payment.end_date >= today,
                Payment.end_date <= soon,
                Payment.is_deleted == False,
                Payment.is_frozen == False,
                Membership.membership_type != 'diario',
            )
            .count()
        )

    @staticmethod
    def count_expired():
        """
        Vencidas: excluye plan Diario, congeladas, y excluye clientes que ya
        tienen otra membresía activa (aunque sea de otro plan).
        """
        from database.models.membership import Membership
        today = datetime.now(BOGOTA).date()

        # Subquery: client_ids con al menos 1 pago activo (o congelado) hoy
        active_ids = db.session.query(Payment.client_id).filter(
            db.or_(Payment.end_date >= today, Payment.is_frozen == True),
            Payment.is_deleted == False,
        ).distinct().subquery()

        return (
            Payment.query
            .join(Membership, Payment.membership_id == Membership.id)
            .filter(
                Payment.end_date < today,
                Payment.is_deleted == False,
                Payment.is_frozen == False,
                Membership.membership_type != 'diario',
                Payment.client_id.notin_(active_ids),
            )
            .count()
        )

    @staticmethod
    def get_active_memberships():
        today = datetime.now(BOGOTA).date()
        return Payment.query.filter(
            db.or_(Payment.end_date >= today, Payment.is_frozen == True),
            Payment.is_deleted == False,
        ).all()
