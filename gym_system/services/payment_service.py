from database.models.payment import Payment, _get_shift
from database.models.membership import Membership
from database.models.client import Client
from database.models.attendance import Attendance
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

        # --- Plan Diario: usar cliente especial DIARIO automáticamente ---
        form_data = dict(form_data)   # mutable copy
        if membership.membership_type == 'diario':
            diario_client = Client.query.filter_by(document_number='DIARIO-0000').first()
            if not diario_client:
                # Crear al vuelo si no existe (failsafe)
                diario_client = Client(
                    full_name='DIARIO', document_type='otro',
                    document_number='DIARIO-0000', is_active=True,
                    notes='Cliente especial para pagos diarios.',
                )
                db.session.add(diario_client)
                db.session.flush()
            form_data['client_id'] = str(diario_client.id)

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

        # --- Pago mixto: leer métodos y montos ---
        cash_received = None
        cash_change   = None

        # Leer hasta 4 métodos del formulario: method_1, amount_1, method_2, amount_2 ...
        split_parts = []
        for i in range(1, 5):
            m = form_data.get(f'method_{i}', '').strip()
            a = form_data.get(f'amount_{i}', '').strip()
            if m and a:
                try:
                    split_parts.append((m, float(a)))
                except ValueError:
                    pass

        # Si no vino en formato split, usar campo legacy
        if not split_parts:
            m = form_data.get('payment_method', 'efectivo')
            try:
                a = float(form_data.get('amount', 0))
            except (ValueError, TypeError):
                a = 0
            split_parts = [(m, a)]

        from utils.helpers import serialize_payment_split, primary_payment_method
        payment_method_str = serialize_payment_split(split_parts)

        # Vuelto solo si hay efectivo
        efectivo_amount = sum(a for m, a in split_parts if m == 'efectivo')
        if efectivo_amount > 0:
            try:
                cash_received = float(form_data.get('cash_received') or 0) or None
                if cash_received:
                    cash_change = max(0, cash_received - float(form_data['amount']))
            except (ValueError, TypeError):
                pass

        # Fecha de pago: si el usuario la especificó (pago de otro mes), usarla.
        # Si no, usar hoy. Esto permite registrar pagos atrasados sin que
        # aparezcan como ganancia del día/mes incorrecto.
        raw_payment_date = form_data.get('payment_date', '').strip()
        if raw_payment_date:
            try:
                payment_date = datetime.strptime(raw_payment_date, '%Y-%m-%d').date()
            except ValueError:
                payment_date = datetime.now(BOGOTA).date()
        else:
            payment_date = datetime.now(BOGOTA).date()

        payment = Payment(
            client_id        = int(form_data['client_id']),
            membership_id    = int(form_data['membership_id']),
            amount           = float(form_data['amount']),
            payment_date     = payment_date,
            start_date       = start_date,
            end_date         = end_date,
            payment_method   = payment_method_str,
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
                payment_method   = payment_method_str,
                notes            = f'Plan Pareja — vinculado al pago del cliente #{form_data["client_id"]}',
                partner_client_id= int(form_data['client_id']),
            )
            db.session.add(partner_payment)

        db.session.commit()

        # ── Asistencia automática al registrar pago ────────────────────
        # Se registra la asistencia del día para el cliente principal
        # y para el segundo cliente si es Plan Pareja.
        # El cliente DIARIO no genera asistencia individual.
        now_bogota = datetime.now(BOGOTA)
        today      = now_bogota.date()

        diario_id = None
        _dc = Client.query.filter_by(document_number='DIARIO-0000').first()
        if _dc:
            diario_id = _dc.id

        for client_id_att in set(filter(None, [
            int(form_data['client_id']),
            partner_client_id,   # None si no es Plan Pareja
        ])):
            if client_id_att == diario_id:
                continue   # no registrar asistencia para el cliente DIARIO
            # Evitar duplicar si ya tiene asistencia hoy
            ya_asistio = Attendance.query.filter(
                Attendance.client_id == client_id_att,
                db.func.date(Attendance.check_in) == today,
            ).first()
            if not ya_asistio:
                db.session.add(Attendance(
                    client_id = client_id_att,
                    check_in  = now_bogota,
                    notes     = 'Asistencia registrada automáticamente al pagar',
                ))

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
