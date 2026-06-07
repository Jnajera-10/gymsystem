from flask import render_template, request, redirect, url_for, flash
from database.models.client import Client
from database.models.attendance import Attendance
from database.models.inventory import Product
from database.models.payment import Payment, SHIFT_MORNING, SHIFT_AFTERNOON
from database.models.cash_register import CashRegister
from database.db import db
from services.membership_service import MembershipService
from services.payment_service import PaymentService
import pytz
from datetime import datetime, timedelta

BOGOTA = pytz.timezone('America/Bogota')


class DashboardController:
    @staticmethod
    def index():
        now   = datetime.now(BOGOTA)
        today = now.date()

        # ── Abrir caja (POST) ─────────────────────────────────────────
        if request.method == 'POST':
            try:
                opening = float(request.form.get('opening_cash', 0))
                cr = CashRegister.query.filter_by(date=today).first()
                if cr:
                    cr.opening_cash = opening
                    cr.notes = request.form.get('cash_notes', '')
                else:
                    cr = CashRegister(date=today, opening_cash=opening,
                                      notes=request.form.get('cash_notes', ''))
                    db.session.add(cr)
                db.session.commit()
                flash(f'✅ Caja abierta con ${opening:,.0f}', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al abrir caja: {e}', 'danger')
            return redirect(url_for('dashboard.index'))

        # Inicio del día con timezone explícita — evita TypeError al comparar
        start_of_day = BOGOTA.localize(datetime(today.year, today.month, today.day, 0, 0, 0))

        # ── Caja base del día ─────────────────────────────────────────
        cash_register = CashRegister.query.filter_by(date=today).first()
        opening_cash  = cash_register.opening_cash if cash_register else None

        # ── Estadísticas generales ────────────────────────────────────
        from datetime import date as date_type
        JUNE_START = date_type(2026, 6, 1)

        stats = {
            'total_clients':      Client.query.filter_by(is_active=True).count(),
            'active_memberships': MembershipService.count_active(),
            'expiring_soon':      MembershipService.count_expiring_soon(),
            'expired':            MembershipService.count_expired(),
            'today_income':       PaymentService.today_income(),
            'month_income':       PaymentService.month_income(),
            'june_income':        PaymentService.income_since(JUNE_START),
            'today_attendance':   Attendance.query.filter(
                                      Attendance.check_in >= start_of_day
                                  ).count(),
            'low_stock':          Product.query.filter(
                                      Product.quantity <= Product.min_stock,
                                      Product.is_active == True,
                                  ).count(),
        }

        # Desglose por método desde 01/06/2026
        june_payments = PaymentService.payments_since_raw(JUNE_START)
        june_breakdown = {}
        for p in june_payments:
            method = p.payment_method or 'otro'
            june_breakdown[method] = june_breakdown.get(method, 0) + p.amount

        # ── Alertas accionables: próximas a vencer (≤3 días) ─────────
        warn_limit = today + timedelta(days=3)
        expiring_payments = (
            Payment.query
            .filter(
                Payment.end_date >= today,
                Payment.end_date <= warn_limit,
                Payment.is_deleted == False,
            )
            .order_by(Payment.end_date.asc())
            .all()
        )

        # ── Alertas accionables: ya vencidas (ayer y anteriores) ─────
        expired_payments = (
            Payment.query
            .filter(
                Payment.end_date < today,
                Payment.is_deleted == False,
            )
            .order_by(Payment.end_date.desc())
            .limit(10)          # máximo 10 para no saturar el dashboard
            .all()
        )

        # ── Caja del día: desglose por método de pago ─────────────────
        today_payments = Payment.query.filter(
            Payment.payment_date == today,
            Payment.is_deleted   == False,
        ).all()

        cash_breakdown = {}
        for p in today_payments:
            method = p.payment_method or 'otro'
            cash_breakdown[method] = cash_breakdown.get(method, 0) + p.amount

        # También calcular ingresos del mes por método
        month_payments = PaymentService.month_payments_raw()
        month_breakdown = {}
        for p in month_payments:
            method = p.payment_method or 'otro'
            month_breakdown[method] = month_breakdown.get(method, 0) + p.amount

        # ── Desglose por turno (hoy) ──────────────────────────────────
        morning_income   = sum(p.amount for p in today_payments if p.shift == SHIFT_MORNING)
        afternoon_income = sum(p.amount for p in today_payments if p.shift == SHIFT_AFTERNOON)

        # Ganancia neta del día = ingresos - caja base
        net_income = stats['today_income'] - (opening_cash or 0)

        return render_template(
            'dashboard/dashboard.html',
            stats            = stats,
            today            = today,
            expiring_payments= expiring_payments,
            expired_payments = expired_payments,
            cash_breakdown   = cash_breakdown,
            month_breakdown  = month_breakdown,
            june_breakdown   = june_breakdown,
            opening_cash     = opening_cash,
            morning_income   = morning_income,
            afternoon_income = afternoon_income,
            net_income       = net_income,
        )
