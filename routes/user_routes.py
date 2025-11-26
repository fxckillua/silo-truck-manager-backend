from flask import Blueprint, request, jsonify
from models import Usuario, Condutor, Notificacao, CaminhaoCondutor
from database import db
from werkzeug.security import generate_password_hash
from datetime import date

user_bp = Blueprint("users", __name__, url_prefix="/users")


def _parse_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _close_active_link(condutor_id: int, truck_id: int | None):
    """Marca um vínculo como inativo ao mover o motorista para outro caminhão."""
    if not condutor_id or not truck_id:
        return

    vinculo = (
        CaminhaoCondutor.query.filter_by(
            id_condutor=condutor_id,
            id_caminhao=truck_id,
            ativo=True,
        )
        .order_by(CaminhaoCondutor.id_vinculo.desc())
        .first()
    )

    if vinculo:
        vinculo.ativo = False
        vinculo.data_fim = date.today()


def _ensure_link(condutor, truck_id):
    """Garante que exista um vínculo histórico entre motorista e caminhão."""
    if condutor is None:
        return

    if condutor.id_caminhao == truck_id:
        # Já está apontando para este caminhão → apenas reativa o vínculo, caso exista
        if truck_id:
            vinculo = CaminhaoCondutor.query.filter_by(
                id_condutor=condutor.id_condutor,
                id_caminhao=truck_id,
            ).first()
            if vinculo:
                vinculo.ativo = True
                vinculo.data_fim = None
                if not vinculo.data_inicio:
                    vinculo.data_inicio = date.today()
            else:
                db.session.add(
                    CaminhaoCondutor(
                        id_condutor=condutor.id_condutor,
                        id_caminhao=truck_id,
                        data_inicio=date.today(),
                        ativo=True,
                    )
                )
        return

    # Encerra vínculo anterior
    if condutor.id_caminhao:
        vinculo_atual = CaminhaoCondutor.query.filter_by(
            id_condutor=condutor.id_condutor,
            id_caminhao=condutor.id_caminhao,
        ).first()
        if not vinculo_atual:
            db.session.add(
                CaminhaoCondutor(
                    id_condutor=condutor.id_condutor,
                    id_caminhao=condutor.id_caminhao,
                    data_inicio=date.today(),
                    ativo=True,
                )
            )
        _close_active_link(condutor.id_condutor, condutor.id_caminhao)

    condutor.id_caminhao = truck_id

    if truck_id:
        vinculo = CaminhaoCondutor.query.filter_by(
            id_condutor=condutor.id_condutor,
            id_caminhao=truck_id,
        ).first()
        if vinculo:
            vinculo.ativo = True
            vinculo.data_fim = None
            if not vinculo.data_inicio:
                vinculo.data_inicio = date.today()
        else:
            db.session.add(
                CaminhaoCondutor(
                    id_condutor=condutor.id_condutor,
                    id_caminhao=truck_id,
                    data_inicio=date.today(),
                    ativo=True,
                )
            )

@user_bp.route("/", methods=["GET"])
def get_users():
    users = Usuario.query.all()
    return jsonify([u.to_dict() for u in users])

# @user_bp.route("/", methods=["POST"])
# def create_user():
#     data = request.get_json()
#     nome = data.get("name")
#     email = data.get("email")
#     profile = data.get("profile")
#     password = data.get("password", "123456")

#     if not nome or not email or not profile:
#         return jsonify({"message": "Nome, email e perfil são obrigatórios"}), 400

#     user = Usuario(
#         nome=nome,
#         email=email,
#         perfil=profile,
#         senha=generate_password_hash(password)
#     )
#     db.session.add(user)
#     db.session.commit()

#     return jsonify(user.to_dict()), 201

@user_bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json() or {}

    nome = data.get("name")
    email = data.get("email")
    profile = data.get("profile")
    password = data.get("password") or "123456"

    if not nome or not email or not profile:
        return jsonify({"message": "Nome, email e perfil são obrigatórios"}), 400

    # Evita email duplicado
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"message": "Email já cadastrado"}), 400

    # Cria o usuário
    user = Usuario(
        nome=nome,
        email=email,
        perfil=profile,
        senha=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.flush()  # garante user.id_usuario antes do commit

    # Se for motorista, cria também o condutor
    if profile == "motorista":
        cnh = data.get("cnh")
        telefone = data.get("telefone")
        id_caminhao = _parse_int(data.get("id_caminhao"))

        if not cnh:
            db.session.rollback()
            return jsonify({"message": "CNH é obrigatória para motoristas"}), 400

        condutor = Condutor(
            nome=nome,
            cnh=cnh,
            telefone=telefone,
            email=email,
            id_usuario=user.id_usuario,
        )
        db.session.add(condutor)
        db.session.flush()
        _ensure_link(condutor, id_caminhao)

    db.session.commit()
    return jsonify(user.to_dict()), 201

@user_bp.route("/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    """Atualiza dados de um usuário e, se for motorista, os dados do condutor/caminhão."""
    data = request.get_json() or {}

    user = Usuario.query.get_or_404(user_id)

    nome = data.get("name")
    email = data.get("email")
    profile = data.get("profile")
    password = data.get("password")
    cnh = data.get("cnh")
    telefone = data.get("telefone")
    id_caminhao = _parse_int(data.get("id_caminhao"))

    # Evita email duplicado
    if email and Usuario.query.filter(
        Usuario.email == email,
        Usuario.id_usuario != user.id_usuario
    ).first():
        return jsonify({"message": "Email já cadastrado"}), 400

    if nome is not None:
        user.nome = nome
    if email is not None:
        user.email = email
    if profile is not None:
        user.perfil = profile
    if password:
        user.senha = generate_password_hash(password)

    # Lógica de condutor (motorista)
    condutor = Condutor.query.filter_by(id_usuario=user.id_usuario).first()

    # Se mudou o perfil para algo que NÃO é motorista, apaga o condutor
    if profile is not None and profile != "motorista":
        if condutor:
            db.session.delete(condutor)
            condutor = None

    # Se o usuário é (ou continua sendo) motorista, atualiza/vincula condutor
    if (profile == "motorista") or (profile is None and user.perfil == "motorista"):
        if condutor is None and (cnh or id_caminhao or telefone):
            # criando condutor novo
            if not cnh:
                return jsonify({"message": "CNH é obrigatória para motorista"}), 400

            condutor = Condutor(
                nome=nome or user.nome,
                cnh=cnh,
                telefone=telefone,
                email=email or user.email,
                id_usuario=user.id_usuario,
                id_caminhao=id_caminhao,
            )
            db.session.add(condutor)
        elif condutor:
            # atualizando condutor existente
            if nome is not None:
                condutor.nome = nome
            if email is not None:
                condutor.email = email
            if cnh is not None:
                condutor.cnh = cnh
            if telefone is not None:
                condutor.telefone = telefone
            if id_caminhao is not None:
                _ensure_link(condutor, id_caminhao)

    db.session.commit()
    return jsonify(user.to_dict()), 200


def _delete_user(id_usuario):
    usuario = Usuario.query.get(id_usuario)
    if usuario:
        condutor = Condutor.query.filter_by(id_usuario=id_usuario).first()
        if condutor:
            # Remove vínculos históricos antes da exclusão para evitar erro de FK
            CaminhaoCondutor.query.filter_by(id_condutor=condutor.id_condutor).delete()
            condutor.id_caminhao = None
            db.session.delete(condutor)

        Notificacao.query.filter_by(id_usuario=id_usuario).delete()
        db.session.delete(usuario)
        db.session.commit()

        return jsonify({"message": "Motorista e seus vínculos excluídos com sucesso."}), 200
    return jsonify({"message": "Usuário não encontrado"}), 404


@user_bp.route('/delete/<int:id_usuario>', methods=['DELETE'])
def delete_user_legacy(id_usuario):
    """Mantém compatibilidade com chamadas antigas /users/delete/<id>."""
    return _delete_user(id_usuario)


@user_bp.route('/<int:id_usuario>', methods=['DELETE'])
def delete_user(id_usuario):
    """Suporta DELETE direto em /users/<id> usado pelo frontend."""
    return _delete_user(id_usuario)

