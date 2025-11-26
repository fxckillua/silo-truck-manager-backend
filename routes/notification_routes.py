from flask import Blueprint, request, jsonify
from models import Notificacao, Usuario, Condutor
from database import db
from sqlalchemy import or_


# serviço que atualiza status e gera notificações automáticas
from services.maintenance_alerts import update_truck_status_and_notifications

notification_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


# @notification_bp.route("/", methods=["GET"])
# def get_notifications():
#     # Antes de buscar as notificações, atualiza status dos caminhões
#     # e gera novas notificações automáticas, se for o caso
#     update_truck_status_and_notifications()

#     user_id = request.args.get("userId")
#     query = Notificacao.query
#     if user_id:
#         query = query.filter_by(id_usuario=user_id)
#     notifs = query.order_by(Notificacao.data_envio.desc()).all()
#     return jsonify([n.to_dict() for n in notifs])

#essa está funcionando
# @notification_bp.route("/", methods=["GET"])
# def get_notifications():
#     # Atualiza status dos caminhões e gera notificações automáticas
#     update_truck_status_and_notifications()

#     from models import Usuario, Condutor, Notificacao

#     # vem da query string: /notifications?userId=3
#     user_id = request.args.get("userId", type=int)

#     # Se não mandou userId, devolve tudo (comportamento antigo)
#     if not user_id:
#         notifs = Notificacao.query.order_by(Notificacao.data_envio.desc()).all()
#         return jsonify([n.to_dict() for n in notifs])

#     # Descobre quem é o usuário
#     user = Usuario.query.get(user_id)
#     if not user:
#         return jsonify([])

#     # Se for MOTORISTA → só notificações ligadas ao caminhão dele
#     if user.perfil == "motorista":
#         condutor = Condutor.query.filter_by(id_usuario=user_id).first()

#         # Motorista sem caminhão vinculado
#         if not condutor or not condutor.id_caminhao:
#             # Aqui você escolhe: lista vazia ou só notificações diretas pro usuário
#             notifs = (
#                 Notificacao.query
#                 .filter_by(id_usuario=user_id)
#                 .order_by(Notificacao.data_envio.desc())
#                 .all()
#             )
#             return jsonify([n.to_dict() for n in notifs])

#         # Motorista com caminhão vinculado:
#         #  – notificações diretamente para ele (id_usuario)
#         #  – E/ou notificações gerais do caminhão (id_caminhao)
#         notifs = (
#             Notificacao.query
#             .filter(
#                 (Notificacao.id_usuario == user_id) |
#                 (Notificacao.id_caminhao == condutor.id_caminhao)
#             )
#             .order_by(Notificacao.data_envio.desc())
#             .all()
#         )
#         return jsonify([n.to_dict() for n in notifs])

#     # ADMIN / MECÂNICO / GESTOR → vê tudo normalmente
#     notifs = Notificacao.query.order_by(Notificacao.data_envio.desc()).all()
#     return jsonify([n.to_dict() for n in notifs])

@notification_bp.route("/", methods=["GET"])
def get_notifications():
    # Atualiza status / gera novas notificações
    update_truck_status_and_notifications()

    user_id = request.args.get("userId", type=int)

    # Se não vier userId, devolve tudo (ex: teste no Insomnia)
    if not user_id:
        notifs = Notificacao.query.order_by(Notificacao.data_envio.desc()).all()
        return jsonify([n.to_dict() for n in notifs])

    user = Usuario.query.get(user_id)
    if not user:
        return jsonify([])

    # --- MOTORISTA: só notificações do caminhão vinculado ---
    if user.perfil == "motorista":
        condutor = Condutor.query.filter_by(id_usuario=user_id).first()

        if not condutor:
            notifs = (
                Notificacao.query
                .filter_by(id_usuario=user.id_usuario)
                .order_by(Notificacao.data_envio.desc())
                .all()
            )
            return jsonify([n.to_dict() for n in notifs])

        truck_ids = {v.id_caminhao for v in condutor.vinculos}
        if not truck_ids and condutor.id_caminhao:
            truck_ids.add(condutor.id_caminhao)

        filters = [Notificacao.id_usuario == user.id_usuario]
        if truck_ids:
            filters.append(Notificacao.id_caminhao.in_(truck_ids))

        notifs = (
            Notificacao.query
            .filter(or_(*filters))
            .order_by(Notificacao.data_envio.desc())
            .all()
        )
        return jsonify([n.to_dict() for n in notifs])

    # --- Outros perfis: filtra só pelo usuário (admin, mecânico, gestor) ---
    else:
        notifs = (
            Notificacao.query
            .filter_by(id_usuario=user.id_usuario)
            .order_by(Notificacao.data_envio.desc())
            .all()
        )

    return jsonify([n.to_dict() for n in notifs])

@notification_bp.route("/", methods=["POST"])
def create_notification():
    data = request.get_json() or {}

    notif = Notificacao(
        id_usuario=data.get("userId"),   # pode ser None para notificação global
        titulo=data.get("title"),
        mensagem=data.get("message"),
        tipo=data.get("type", "info"),
    )

    db.session.add(notif)
    db.session.commit()

    return jsonify(notif.to_dict()), 201


@notification_bp.route("/<int:notif_id>/read", methods=["PATCH"])
def mark_notification_as_read(notif_id):
    notif = Notificacao.query.get_or_404(notif_id)
    notif.visualizado = True
    db.session.commit()
    return jsonify(notif.to_dict())


@notification_bp.route("/<int:notif_id>", methods=["DELETE"])
def delete_notification(notif_id):
    notif = Notificacao.query.get_or_404(notif_id)
    db.session.delete(notif)
    db.session.commit()
    return jsonify({"message": "Notificação removida com sucesso"}), 200
