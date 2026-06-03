from flask import render_template
from database.models.client import Client
from database.models.payment import Payment
from database.models.attendance import Attendance
from database.models.inventory import Product
from database.models.sales import Sale
from services.membership_service import MembershipService
from services.payment_service import PaymentService
import pytz
from datetime import datetime

BOGOTA = pytz.timezone('America/Bogota')

class DashboardController:
    @staticmethod
    def index():
        today = datetime.now(BOGOTA).date()
        stats = {
            'total_clients': Client.query.filter_by(is_active=True).count(),
            'active_memberships': MembershipService.count_active(),
            'expiring_soon': MembershipService.count_expiring_soon(),
            'expired': MembershipService.count_expired(),
            'today_income': PaymentService.today_income(),
            'month_income': PaymentService.month_income(),
            'today_attendance': Attendance.query.filter(
                Attendance.check_in >= datetime.combine(today, datetime.min.time())
            ).count(),
            'low_stock': Product.query.filter(Product.quantity <= Product.min_stock).count(),
        }
        return render_template('dashboard/dashboard.html', stats=stats, today=today)
