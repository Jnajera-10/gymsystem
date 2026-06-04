from flask import Blueprint, render_template, redirect, url_for, send_file, request
from services.report_service import ReportService
from services.export_service import ExportService
from utils.pdf_generator import generate_report_pdf
from utils.security import login_required
from database.models.payment import Payment
from database.models.sales import Sale
from database.models.client import Client

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    clients = ReportService.clients_report()
    return render_template('reports/reports.html', clients=clients)

@reports_bp.route('/excel/clients')
@login_required
def excel_clients():
    clients = Client.query.filter_by(is_active=True).all()
    buf = ExportService.export_clients_excel(clients)
    return send_file(buf, as_attachment=True, download_name='clientes.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@reports_bp.route('/excel/payments')
@login_required
def excel_payments():
    payments = Payment.query.filter_by(is_deleted=False).all()
    buf = ExportService.export_payments_excel(payments)
    return send_file(buf, as_attachment=True, download_name='pagos.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@reports_bp.route('/excel/sales')
@login_required
def excel_sales():
    sales = Sale.query.filter_by(is_deleted=False).all()
    buf = ExportService.export_sales_excel(sales)
    return send_file(buf, as_attachment=True, download_name='ventas.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@reports_bp.route('/pdf/clients')
@login_required
def pdf_clients():
    clients = Client.query.filter_by(is_active=True).all()
    buf = generate_report_pdf('clientes', clients)
    return send_file(buf, as_attachment=True, download_name='clientes.pdf', mimetype='application/pdf')

@reports_bp.route('/pdf/payments')
@login_required
def pdf_payments():
    payments = Payment.query.filter_by(is_deleted=False).all()
    buf = generate_report_pdf('pagos', payments)
    return send_file(buf, as_attachment=True, download_name='pagos.pdf', mimetype='application/pdf')

@reports_bp.route('/pdf/sales')
@login_required
def pdf_sales():
    sales = Sale.query.filter_by(is_deleted=False).all()
    buf = generate_report_pdf('ventas', sales)
    return send_file(buf, as_attachment=True, download_name='ventas.pdf', mimetype='application/pdf')
