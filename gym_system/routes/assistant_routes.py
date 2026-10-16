from flask import Blueprint, request, jsonify, session
from services import assistant_service as svc

assistant_bp = Blueprint('assistant', __name__, url_prefix='/assistant')


def _user():
    return {'id': session.get('user_id'), 'role': session.get('user_role')}


@assistant_bp.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(svc.chat(data.get('messages'), _user()))
    except svc.AssistantError as exc:
        return jsonify({'reply': f'⚠️ {exc}', 'actions': []})
    except Exception:
        from flask import current_app
        current_app.logger.exception('[assistant] error inesperado')
        return jsonify({'reply': '⚠️ Algo salió mal. Intenta de nuevo.', 'actions': []})


@assistant_bp.route('/confirm', methods=['POST'])
def confirm():
    data = request.get_json(silent=True) or {}
    ok, message = svc.confirm_action(str(data.get('token', '')), bool(data.get('approve', True)))
    return jsonify({'ok': ok, 'message': message})
