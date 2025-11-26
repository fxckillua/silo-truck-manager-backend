from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from models import Usuario
from database import db
from utils.auth import generate_token, generate_reset_token, verify_reset_token
from services.email_service import send_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email e senha são obrigatórios"}), 400

    user = Usuario.query.filter_by(email=email).first()
    if not user:
        return jsonify({"message": "Usuário não encontrado"}), 401

    # Para testes, se a senha estiver em texto puro, pode trocar pela comparação simples:
    # if user.senha != password:
    if not check_password_hash(user.senha, password):
        return jsonify({"message": "Senha inválida"}), 401

    token = generate_token(user.id_usuario, user.perfil)
    return jsonify({
        "token": token,
        "user": user.to_dict()
    })


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email é obrigatório"}), 400

    user = Usuario.query.filter_by(email=email).first()

    # Sempre responde sucesso para evitar enumeração
    if not user:
        return jsonify({"message": "Se o email existir, enviaremos um link de recuperação."}), 200

    token = generate_reset_token(user.id_usuario)
    frontend_base = current_app.config.get("FRONTEND_BASE_URL", "http://localhost:8080")
    reset_link = f"{frontend_base}/reset-password?token={token}"

    body = (
        f"Olá {user.nome},\n\n"
        "Recebemos uma solicitação para redefinir sua senha no Fleet Manager.\n"
        f"Use o link abaixo para criar uma nova senha (expira em 15 minutos):\n{reset_link}\n\n"
        "Se você não fez esta solicitação, ignore este email."
    )

    html = f"""
        <p>Olá <strong>{user.nome}</strong>,</p>
        <p>Recebemos uma solicitação para redefinir sua senha no <strong>Fleet Manager</strong>.</p>
        <p>Use o link abaixo para criar uma nova senha. O link expira em 15 minutos.</p>
        <p><a href="{reset_link}">Redefinir senha</a></p>
        <p>Se você não fez esta solicitação, apenas ignore esta mensagem.</p>
    """

    try:
        send_email(
            subject="Recuperação de senha - Fleet Manager",
            recipients=[email],
            body=body,
            html=html,
        )
    except Exception as exc:  # pragma: no cover - log e retorna erro genérico
        current_app.logger.exception("Erro ao enviar email de recuperação", exc_info=exc)
        return jsonify({"message": "Não foi possível enviar o email. Tente novamente mais tarde."}), 500

    return jsonify({"message": "Se o email existir, enviaremos um link de recuperação."}), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    token = data.get("token")
    password = data.get("password")

    if not token or not password:
        return jsonify({"message": "Token e nova senha são obrigatórios"}), 400

    user_id = verify_reset_token(token)
    if not user_id:
        return jsonify({"message": "Token inválido ou expirado"}), 400

    user = Usuario.query.get(user_id)
    if not user:
        return jsonify({"message": "Usuário não encontrado"}), 404

    user.senha = generate_password_hash(password)
    db.session.commit()

    return jsonify({"message": "Senha redefinida com sucesso"}), 200
