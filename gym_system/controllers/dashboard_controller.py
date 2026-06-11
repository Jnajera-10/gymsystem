from flask import render_template, request, redirect, url_for, flash
from database.models.client import Client
from database.models.attendance import Attendance
from database.models.inventory import Product
from database.models.payment import Payment, SHIFT_MORNING, SHIFT_AFTERNOON
from database.models.cash_register import CashRegister
from database.models.expense import Expense
from database.models.sales import Sale
from database.db import db
from services.membership_service import MembershipService
from services.payment_service import PaymentService
import pytz
from datetime import datetime, timedelta, date as date_type

BOGOTA = pytz.timezone('America/Bogota')
JUNE_START = date_type(2026, 6, 1)


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

        # Inicio del día con timezone explícita
        start_of_day = BOGOTA.localize(datetime(today.year, today.month, today.day, 0, 0, 0))

        # ── Caja base del día ─────────────────────────────────────────
        cash_register = CashRegister.query.filter_by(date=today).first()
        opening_cash  = cash_register.opening_cash if cash_register else None

        # ── Estadísticas generales ────────────────────────────────────
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

        # ── Ingresos de inventario (ventas de productos) ──────────────
        # Hoy
        today_sales = Sale.query.filter(
            db.func.date(Sale.sale_date) == today,
            Sale.is_deleted == False,
        ).all()
        today_inventory_income = sum(s.total for s in today_sales)

        # Mes actual
        from sqlalchemy import extract
        month_sales = Sale.query.filter(
            extract('month', Sale.sale_date) == now.month,
            extract('year',  Sale.sale_date) == now.year,
            Sale.is_deleted == False,
        ).all()
        month_inventory_income = sum(s.total for s in month_sales)

        # Desde junio
        june_sales = Sale.query.filter(
            Sale.sale_date >= BOGOTA.localize(datetime(JUNE_START.year, JUNE_START.month, JUNE_START.day)),
            Sale.is_deleted == False,
        ).all()
        june_inventory_income = sum(s.total for s in june_sales)

        # ── Egresos ───────────────────────────────────────────────────
        # Hoy
        today_expenses_list = Expense.query.filter_by(date=today).order_by(Expense.created_at.desc()).all()
        today_expenses_total = sum(e.amount for e in today_expenses_list)

        # Mes actual
        month_expenses = Expense.query.filter(
            extract('month', Expense.date) == now.month,
            extract('year',  Expense.date) == now.year,
        ).all()
        month_expenses_total = sum(e.amount for e in month_expenses)

        # Desde junio
        june_expenses = Expense.query.filter(Expense.date >= JUNE_START).all()
        june_expenses_total = sum(e.amount for e in june_expenses)

        # ── Desglose por método de pago ───────────────────────────────
        june_payments = PaymentService.payments_since_raw(JUNE_START)
        june_breakdown = {}
        for p in june_payments:
            method = p.payment_method or 'otro'
            june_breakdown[method] = june_breakdown.get(method, 0) + p.amount

        # ── Alertas: próximas a vencer (≤3 días) ─────────────────────
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

        # ── Alertas: ya vencidas ──────────────────────────────────────
        expired_payments = (
            Payment.query
            .filter(
                Payment.end_date < today,
                Payment.is_deleted == False,
            )
            .order_by(Payment.end_date.desc())
            .limit(10)
            .all()
        )

        # ── Caja del día: desglose por método ─────────────────────────
        today_payments = Payment.query.filter(
            Payment.payment_date == today,
            Payment.is_deleted   == False,
        ).all()

        cash_breakdown = {}
        for p in today_payments:
            method = p.payment_method or 'otro'
            cash_breakdown[method] = cash_breakdown.get(method, 0) + p.amount

        month_payments = PaymentService.month_payments_raw()
        month_breakdown = {}
        for p in month_payments:
            method = p.payment_method or 'otro'
            month_breakdown[method] = month_breakdown.get(method, 0) + p.amount

        # ── Desglose por turno (hoy) ──────────────────────────────────
        morning_income   = sum(p.amount for p in today_payments if p.shift == SHIFT_MORNING)
        afternoon_income = sum(p.amount for p in today_payments if p.shift == SHIFT_AFTERNOON)

        # Ganancia neta del día = ingresos membresías + inventario - base - egresos
        net_income = (stats['today_income'] + today_inventory_income
                      - (opening_cash or 0) - today_expenses_total)

        # ── Ganancias exclusivas plan Diario ─────────────────────────
        # Se filtra por payment_date (fecha en que se registró el pago),
        # no por start_date. Así un pago viejo registrado hoy NO suma al día,
        # y un pago del mes pasado NO suma al mes actual.
        from database.models.membership import Membership as MembershipModel
        from sqlalchemy import extract as sql_extract

        daily_today_payments = (
            Payment.query
            .join(MembershipModel, Payment.membership_id == MembershipModel.id)
            .filter(
                Payment.payment_date == today,
                Payment.is_deleted   == False,
                MembershipModel.membership_type == 'diario',
            ).all()
        )
        daily_today_income = sum(p.amount for p in daily_today_payments)
        daily_count_today  = len(daily_today_payments)

        daily_month_payments = (
            Payment.query
            .join(MembershipModel, Payment.membership_id == MembershipModel.id)
            .filter(
                sql_extract('month', Payment.payment_date) == now.month,
                sql_extract('year',  Payment.payment_date) == now.year,
                Payment.is_deleted == False,
                MembershipModel.membership_type == 'diario',
            ).all()
        )
        daily_month_income = sum(p.amount for p in daily_month_payments)
        daily_count_month  = len(daily_month_payments)

        return render_template(
            'dashboard/dashboard.html',
            stats                   = stats,
            today                   = today,
            expiring_payments       = expiring_payments,
            expired_payments        = expired_payments,
            cash_breakdown          = cash_breakdown,
            month_breakdown         = month_breakdown,
            june_breakdown          = june_breakdown,
            opening_cash            = opening_cash,
            morning_income          = morning_income,
            afternoon_income        = afternoon_income,
            net_income              = net_income,
            # Egresos
            today_expenses_list     = today_expenses_list,
            today_expenses_total    = today_expenses_total,
            month_expenses_total    = month_expenses_total,
            june_expenses_total     = june_expenses_total,
            # Inventario separado
            today_inventory_income  = today_inventory_income,
            month_inventory_income  = month_inventory_income,
            june_inventory_income   = june_inventory_income,
            # Diarios
            daily_today_income      = daily_today_income,
            daily_today_count       = daily_count_today,
            daily_month_income      = daily_month_income,
            daily_month_count       = daily_count_month,
        )
