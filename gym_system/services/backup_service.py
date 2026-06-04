"""
BackupService — exporta los datos como JSON usando SQLAlchemy,
sin depender de pg_dump (que no está disponible en Render free).

Genera un archivo .json con todas las tablas principales y lo guarda
en la carpeta backups/ del proyecto.
"""
import os
import json
import logging
from datetime import datetime, date
import pytz

BOGOTA = pytz.timezone('America/Bogota')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
logger = logging.getLogger(__name__)


def _serialize(value):
    """Convierte tipos no-JSON a string."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _model_to_dict(instance):
    """Convierte una fila de SQLAlchemy a dict serializable."""
    return {
        col.name: _serialize(getattr(instance, col.name))
        for col in instance.__table__.columns
    }


class BackupService:

    @staticmethod
    def _backup_dir():
        path = os.path.abspath(BACKUP_DIR)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def create_backup():
        """
        Genera un backup JSON con todas las tablas principales.
        Compatible con Render free (no requiere pg_dump).
        Devuelve la ruta del archivo generado.
        """
        from database.models.client import Client
        from database.models.payment import Payment
        from database.models.membership import Membership
        from database.models.sales import Sale, SaleItem
        from database.models.inventory import Product, StockMovement
        from database.models.attendance import Attendance
        from database.models.user import User
        from database.models.notifications import Notification
        from database.models.audit import AuditLog
        from database.models.settings import GymSettings

        tables = {
            'clients':        Client.query.all(),
            'payments':       Payment.query.all(),
            'memberships':    Membership.query.all(),
            'sales':          Sale.query.all(),
            'sale_items':     SaleItem.query.all(),
            'products':       Product.query.all(),
            'stock_movements': StockMovement.query.all(),
            'attendances':    Attendance.query.all(),
            'users':          User.query.all(),
            'notifications':  Notification.query.all(),
            'audit_logs':     AuditLog.query.all(),
            'gym_settings':   GymSettings.query.all(),
        }

        data = {
            'generated_at': datetime.now(BOGOTA).isoformat(),
            'tables': {
                name: [_model_to_dict(row) for row in rows]
                for name, rows in tables.items()
            }
        }

        timestamp = datetime.now(BOGOTA).strftime('%Y%m%d_%H%M%S')
        backup_dir = BackupService._backup_dir()
        dest = os.path.join(backup_dir, f'backup_{timestamp}.json')

        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f'[backup] Backup creado: {dest}')
        return dest

    @staticmethod
    def list_backups():
        backup_dir = BackupService._backup_dir()
        files = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
        return sorted(files, reverse=True)

    @staticmethod
    def restore_backup(filename):
        """
        La restauración automática desde JSON requiere lógica de
        inserción tabla por tabla y está fuera del alcance de este
        módulo. Para restaurar, descarga el JSON y usa los datos
        manualmente o contacta al administrador del sistema.
        """
        raise NotImplementedError(
            'La restauración automática no está disponible. '
            'Descarga el archivo JSON desde el servidor y restaura manualmente.'
        )
