from database.models.audit import AuditLog
from database.db import db

class AuditService:
    @staticmethod
    def log(action, table_name, record_id, old_value=None, new_value=None):
        try:
            from flask import session
            user_id = session.get('user_id')
        except:
            user_id = None
        log = AuditLog(
            user_id=user_id,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_value=str(old_value) if old_value else None,
            new_value=str(new_value) if new_value else None
        )
        db.session.add(log)
        db.session.commit()
