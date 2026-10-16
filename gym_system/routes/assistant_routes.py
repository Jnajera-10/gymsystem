from flask import Blueprint, request, jsonify, session, send_file, abort
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


# ── Música ───────────────────────────────────────────────────────────
# Las canciones NO se sirven desde /static (que es público): pasan por aquí,
# así que solo las escucha quien tenga sesión iniciada.
@assistant_bp.route('/music', methods=['GET'])
def music_list():
    return jsonify({'songs': [{'id': s['id'], 'title': s['title']} for s in svc.list_songs()]})


@assistant_bp.route('/music/<song_id>', methods=['GET'])
def music_file(song_id):
    path, _ = svc.song_file(song_id)
    if not path:
        abort(404)
    # conditional=True habilita Range requests (necesario para adelantar/atrasar la canción)
    resp = send_file(path, mimetype='audio/mpeg', conditional=True, max_age=3600)
    resp.headers['Cache-Control'] = 'private, max-age=3600'
    return resp
