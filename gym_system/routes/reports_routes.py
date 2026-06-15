from flask import Blueprint, render_template, send_file, request
from services.report_service import ReportService
from services.export_service import ExportService
from utils.pdf_generator import generate_report_pdf
from utils.security import login_required
from database.db import db
from database.models.payment import Payment
from database.models.membership import Membership as MembershipModel
from database.models.client import Client
import pytz
from datetime import datetime, timedelta

BOGOTA      = pytz.timezone('America/Bogota')
reports_bp  = Blueprint('reports', __name__, url_prefix='/reports')


def _parse_range(request):
    """Lee mes/año del query string y devuelve (start_date, end_date, mes, anio)."""
    now   = datetime.now(BOGOTA)
    mes   = request.args.get('mes',  type=int, default=now.month)
    anio  = request.args.get('anio', type=int, default=now.year)
    mes   = max(1, min(12, mes))
    anio  = max(2020, min(2100, anio))
    from calendar import monthrange
    _, last_day = monthrange(anio, mes)
    from datetime import date
    start = date(anio, mes, 1)
    end   = date(anio, mes, last_day)
    return start, end, mes, anio


# ── Página principal ─────────────────────────────────────────────────
@reports_bp.route('/')
@login_required
def index():
    now   = datetime.now(BOGOTA)
    mes   = request.args.get('mes',  type=int, default=now.month)
    anio  = request.args.get('anio', type=int, default=now.year)
    start, end, mes, anio = _parse_range(request)
    today = now.date()

    # Estadísticas del período seleccionado
    payments_period = ReportService.payments_report(start, end)
    income_period   = sum(p.amount for p in payments_period)
    income_by_method = {}
    for p in payments_period:
        m = p.payment_method or 'otro'
        income_by_method[m] = income_by_method.get(m, 0) + p.amount

    clients_active  = Client.query.filter_by(is_active=True).count()

    # Por vencer (≤3 días) — excluye plan Diario
    warn_limit = today + timedelta(days=3)
    expiring   = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date >= today,
            Payment.end_date <= warn_limit,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
        )
        .order_by(Payment.end_date)
        .all()
    )

    # Vencidas — excluye plan Diario y clientes con membresía activa
    from database.db import db as _db
    active_ids = _db.session.query(Payment.client_id).filter(
        Payment.end_date >= today,
        Payment.is_deleted == False,
    ).distinct().subquery()
    expired = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date < today,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
            Payment.client_id.notin_(active_ids),
        )
        .order_by(Payment.end_date.desc())
        .all()
    )

    return render_template(
        'reports/reports.html',
        mes             = mes,
        anio            = anio,
        start           = start,
        end             = end,
        payments_period = payments_period,
        income_period   = income_period,
        income_by_method= income_by_method,
        clients_active  = clients_active,
        expiring        = expiring,
        expired         = expired,
        today           = today,
    )


# ── Exportar clientes activos ────────────────────────────────────────
@reports_bp.route('/excel/clients')
@login_required
def excel_clients():
    clients = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
    buf = ExportService.export_clients_excel(clients)
    return send_file(buf, as_attachment=True, download_name='clientes_activos.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@reports_bp.route('/pdf/clients')
@login_required
def pdf_clients():
    clients = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()
    buf = generate_report_pdf('clientes', clients)
    return send_file(buf, as_attachment=True, download_name='clientes_activos.pdf',
                     mimetype='application/pdf')


# ── Exportar pagos del mes (con filtro) ──────────────────────────────
@reports_bp.route('/excel/payments')
@login_required
def excel_payments():
    start, end, mes, anio = _parse_range(request)
    payments = ReportService.payments_report(start, end)
    buf = ExportService.export_payments_excel(payments)
    name = f'pagos_{anio}_{mes:02d}.xlsx'
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@reports_bp.route('/pdf/payments')
@login_required
def pdf_payments():
    start, end, mes, anio = _parse_range(request)
    payments = ReportService.payments_report(start, end)
    buf = generate_report_pdf('pagos', payments, start=start, end=end)
    name = f'pagos_{anio}_{mes:02d}.pdf'
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype='application/pdf')


# ── Exportar ventas del mes ──────────────────────────────────────────
@reports_bp.route('/excel/sales')
@login_required
def excel_sales():
    from database.models.sales import Sale
    start, end, mes, anio = _parse_range(request)
    sales = ReportService.sales_report(start, end)
    buf = ExportService.export_sales_excel(sales)
    name = f'ventas_{anio}_{mes:02d}.xlsx'
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@reports_bp.route('/pdf/sales')
@login_required
def pdf_sales():
    start, end, mes, anio = _parse_range(request)
    sales = ReportService.sales_report(start, end)
    buf = generate_report_pdf('ventas', sales, start=start, end=end)
    name = f'ventas_{anio}_{mes:02d}.pdf'
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype='application/pdf')


# ── Exportar vencidos / por vencer (excluye plan Diario) ─────────────
@reports_bp.route('/excel/expired')
@login_required
def excel_expired():
    today = datetime.now(BOGOTA).date()
    from database.db import db as _db
    active_ids = _db.session.query(Payment.client_id).filter(
        Payment.end_date >= today,
        Payment.is_deleted == False,
    ).distinct().subquery()
    expired = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date < today,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
            Payment.client_id.notin_(active_ids),
        )
        .order_by(Payment.end_date.desc())
        .all()
    )
    buf = ExportService.export_expired_excel(expired, today)
    return send_file(buf, as_attachment=True, download_name='membresias_vencidas.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@reports_bp.route('/excel/expiring')
@login_required
def excel_expiring():
    today      = datetime.now(BOGOTA).date()
    warn_limit = today + timedelta(days=3)
    expiring   = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date >= today,
            Payment.end_date <= warn_limit,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
        )
        .order_by(Payment.end_date)
        .all()
    )
    buf = ExportService.export_expired_excel(expiring, today, label='Por Vencer')
    return send_file(buf, as_attachment=True, download_name='membresias_por_vencer.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@reports_bp.route('/pdf/expired')
@login_required
def pdf_expired():
    today = datetime.now(BOGOTA).date()
    from database.db import db as _db
    active_ids = _db.session.query(Payment.client_id).filter(
        Payment.end_date >= today,
        Payment.is_deleted == False,
    ).distinct().subquery()
    expired = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date < today,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
            Payment.client_id.notin_(active_ids),
        )
        .order_by(Payment.end_date.desc())
        .all()
    )
    buf = generate_report_pdf('vencidos', expired, today=today)
    return send_file(buf, as_attachment=True, download_name='membresias_vencidas.pdf',
                     mimetype='application/pdf')


@reports_bp.route('/pdf/expiring')
@login_required
def pdf_expiring():
    today      = datetime.now(BOGOTA).date()
    warn_limit = today + timedelta(days=3)
    expiring   = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date >= today,
            Payment.end_date <= warn_limit,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
        )
        .order_by(Payment.end_date)
        .all()
    )
    buf = generate_report_pdf('por_vencer', expiring, today=today)
    return send_file(buf, as_attachment=True, download_name='membresias_por_vencer.pdf',
                     mimetype='application/pdf')


@reports_bp.route('/pdf/cierre-caja')
@login_required
def pdf_cierre_caja():
    """
    Genera el PDF de cierre de caja del día actual y lo envía por correo
    al admin. También lo descarga directamente en el navegador.
    """
    from utils.pdf_generator import generate_cierre_caja_pdf
    from utils.helpers import parse_payment_split
    from database.models.sales import Sale
    from database.models.expense import Expense
    from database.models.settings import GymSettings
    from database.models.user import User
    from services.notification_service import send_email_raw
    import io

    BOGOTA = pytz.timezone('America/Bogota')
    today  = datetime.now(BOGOTA).date()

    # ── Pagos del día ────────────────────────────────────────────────
    payments = (
        Payment.query
        .filter(
            Payment.payment_date == today,
            Payment.is_deleted   == False,
        )
        .order_by(Payment.payment_date)
        .all()
    )

    # ── Egresos del día ──────────────────────────────────────────────
    expenses = Expense.query.filter(Expense.date == today).all()

    # ── Ventas de inventario del día ─────────────────────────────────
    sales = (
        Sale.query
        .filter(
            db.func.date(Sale.sale_date) == today,
        )
        .all()
    )

    # ── Opening cash (base de caja) ──────────────────────────────────
    settings     = GymSettings.query.first()
    opening_cash = getattr(settings, 'opening_cash', 0) or 0

    # ── Desglose por método de pago ──────────────────────────────────
    cash_breakdown = {}
    for p in payments:
        for method, amount in parse_payment_split(p.payment_method, p.amount):
            cash_breakdown[method] = cash_breakdown.get(method, 0) + amount

    # ── Usuario que genera el cierre ─────────────────────────────────
    from flask import session
    usuario_cierre = session.get('username', 'Sistema')

    # ── Generar PDF ──────────────────────────────────────────────────
    buf = generate_cierre_caja_pdf(
        fecha          = today,
        payments       = payments,
        expenses       = expenses,
        sales          = sales,
        opening_cash   = opening_cash,
        cash_breakdown = cash_breakdown,
        usuario_cierre = usuario_cierre,
    )
    pdf_bytes = buf.read()

    # ── Enviar por correo al admin ───────────────────────────────────
    admin = User.query.filter_by(role='admin').first()
    if admin and admin.email:
        fecha_str = today.strftime('%d/%m/%Y')
        total_dia = sum(p.amount for p in payments)
        html = f"""
        <h2 style="color:#1a1a2e">💪 Body-Fit — Cierre de Caja {fecha_str}</h2>
        <p>Se adjunta el reporte de cierre de caja del día <b>{fecha_str}</b>.</p>
        <table style="border-collapse:collapse;width:100%;max-width:400px">
          <tr style="background:#f3f4f6">
            <td style="padding:8px;font-weight:bold">Total ingresos del día</td>
            <td style="padding:8px">${total_dia:,.0f}</td>
          </tr>
          {''.join(f'<tr><td style="padding:6px;padding-left:16px">· {m.capitalize()}</td><td style="padding:6px">${a:,.0f}</td></tr>' for m, a in cash_breakdown.items())}
          <tr style="background:#f3f4f6">
            <td style="padding:8px;font-weight:bold">Pagos registrados</td>
            <td style="padding:8px">{len(payments)}</td>
          </tr>
        </table>
        <p style="color:#6b7280;font-size:12px">Generado por {usuario_cierre} — Body-Fit Gym</p>
        """
        try:
            send_email_raw(
                to_email    = admin.email,
                subject     = f'Cierre de Caja {fecha_str} — Body-Fit',
                html_body   = html,
                attachment  = pdf_bytes,
                attach_name = f'cierre_caja_{today.strftime("%Y%m%d")}.pdf',
            )
            from flask import flash
            flash('✅ PDF generado y enviado por correo al administrador.', 'success')
        except Exception as e:
            from flask import flash
            flash(f'PDF generado pero no se pudo enviar por correo: {e}', 'warning')

    # ── Descargar en el navegador ────────────────────────────────────
    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment = True,
        download_name = f'cierre_caja_{today.strftime("%Y%m%d")}.pdf',
        mimetype      = 'application/pdf',
    )
    today      = datetime.now(BOGOTA).date()
    warn_limit = today + timedelta(days=3)
    expiring   = (
        Payment.query
        .join(MembershipModel, Payment.membership_id == MembershipModel.id)
        .filter(
            Payment.end_date >= today,
            Payment.end_date <= warn_limit,
            Payment.is_deleted == False,
            MembershipModel.membership_type != 'diario',
        )
        .order_by(Payment.end_date)
        .all()
    )
    buf = generate_report_pdf('por_vencer', expiring, today=today)
    return send_file(buf, as_attachment=True, download_name='membresias_por_vencer.pdf',
                     mimetype='application/pdf')
