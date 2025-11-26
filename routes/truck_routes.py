from flask import Blueprint, request, jsonify
from models import Caminhao, Manutencao, Notificacao, Usuario, Condutor
from database import db
from datetime import datetime, date
from services.maintenance_alerts import send_unlock_notification, get_truck_driver_users

truck_bp = Blueprint("trucks", __name__, url_prefix="/trucks")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


# def create_system_notification(title, message, db_type):
#     """
#     Cria uma notificação para todos os usuários ADMIN e GESTOR.
#     Evita duplicidade verificando se já existe notificação igual hoje.
#     """
#     admins = Usuario.query.filter(
#         Usuario.perfil.in_(["administrador", "gestor"])
#     ).all()

#     for user in admins:
#         exists = Notificacao.query.filter(
#             Notificacao.id_usuario == user.id_usuario,
#             Notificacao.titulo == title,
#             Notificacao.visualizado == False,
#         ).first()

#         if not exists:
#             notificacao = Notificacao(
#                 id_usuario=user.id_usuario,
#                 titulo=title,
#                 mensagem=message,
#                 tipo=db_type,
#                 data_envio=datetime.now(),
#             )
#             db.session.add(notificacao)

def create_system_notification(title, message, db_type, truck_id=None):
    """
    Cria uma notificação para todos os usuários ADMIN e GESTOR
    e, se truck_id for informado, também para o motorista vinculado
    àquele caminhão.
    """
    admins = Usuario.query.filter(
        Usuario.perfil.in_(["administrador", "gestor", "mecanico"])
    ).all()

    recipients = list(admins)

    # Inclui motoristas vinculados (atuais ou recentes)
    if truck_id is not None:
        motoristas = get_truck_driver_users(truck_id, include_history_days=90)
        for motorista in motoristas:
            if all(u.id_usuario != motorista.id_usuario for u in recipients):
                recipients.append(motorista)

    for user in recipients:
        exists = Notificacao.query.filter(
            Notificacao.id_usuario == user.id_usuario,
            Notificacao.titulo == title,
            Notificacao.visualizado == False,
        ).first()

        if not exists:
            notificacao = Notificacao(
                id_usuario=user.id_usuario,
                id_caminhao=truck_id,
                titulo=title,
                mensagem=message,
                tipo=db_type,
                data_envio=datetime.now(),
            )
            db.session.add(notificacao)


def refresh_truck_status_by_next_maintenance():
    """
    Atualiza status baseado na data e GERA NOTIFICAÇÕES NO BANCO.
    """
    today = date.today()
    trucks = Caminhao.query.filter(
        Caminhao.data_proxima_manutencao.isnot(None)
    ).all()
    status_changed = False

    for truck in trucks:
        diff_days = (truck.data_proxima_manutencao - today).days

        # 1. VENCEU (Data Passou) -> BLOQUEIA
        if diff_days < 0:
            if truck.status != "bloqueado":
                truck.status = "bloqueado"
                status_changed = True
                # Cria notificação de erro/bloqueio
                create_system_notification(
                    title=f"Bloqueio: {truck.placa}",
                    message=(
                        f"O caminhão {truck.placa} foi bloqueado automaticamente. "
                        f"Manutenção vencida em {truck.data_proxima_manutencao}."
                    ),
                    db_type="manutencao",
                    truck_id=truck.id_caminhao,  # No model.py isso vira 'error' se tiver 'Bloqueio' no título
                )

        # 2. PERTO DE VENCER (0 a 2 dias) -> PENDENTE (Warning)
        elif 0 <= diff_days <= 2:
            # Só avisa se ainda estiver liberado
            if truck.status == "liberado":
                truck.status = "pendente"
                status_changed = True
                create_system_notification(
                    title=f"Manutenção Próxima: {truck.placa}",
                    message=(
                        f"Atenção: A manutenção do veículo vence em {diff_days} dias "
                        f"({truck.data_proxima_manutencao})."
                    ),
                    db_type="alerta",  # No model.py isso vira 'warning'
                )

        # 3. PRAZO LONGE -> LIBERA (se estava pendente)
        else:
            if truck.status == "pendente":
                truck.status = "liberado"
                status_changed = True

    if status_changed:
        db.session.commit()


@truck_bp.route("/", methods=["GET"])
def get_trucks():
    # Roda a verificação toda vez que alguém lista a frota
    refresh_truck_status_by_next_maintenance()

    trucks = Caminhao.query.order_by(Caminhao.id_caminhao.desc()).all()
    return jsonify([t.to_dict() for t in trucks])


@truck_bp.route("/<int:truck_id>/status", methods=["PATCH"])
def update_truck_status(truck_id):
    caminhao = Caminhao.query.get_or_404(truck_id)
    data = request.get_json() or {}

    status = data.get("status")
    if status not in ("liberado", "bloqueado", "pendente"):
        return jsonify({"error": "Status inválido"}), 400

    old_status = caminhao.status
    caminhao.status = status

    # Gera notificação específica para alteração manual de status
    if status != old_status:
        if status == "bloqueado":
            create_system_notification(
                title=f"Bloqueio manual: {caminhao.placa}",
                message=f"O caminhão {caminhao.placa} foi bloqueado manualmente.",
                db_type="manutencao",
                truck_id=caminhao.id_caminhao,
            )
        elif status == "liberado":
            create_system_notification(
                title=f"Liberação manual: {caminhao.placa}",
                message=(
                    f"O caminhão {caminhao.placa} foi liberado manualmente para uso."
                ),
                db_type="info",
                truck_id=caminhao.id_caminhao,
            )
        elif status == "pendente":
            create_system_notification(
                title=f"Status pendente: {caminhao.placa}",
                message=(
                    f"O caminhão {caminhao.placa} foi marcado manualmente como "
                    f"pendente de manutenção."
                ),
                db_type="alerta",
            )

    db.session.commit()
    return jsonify(caminhao.to_dict())


@truck_bp.route("/", methods=["POST"])
def create_truck():
    data = request.get_json()
    caminhao = Caminhao(
        placa=data.get("plate"),
        modelo=data.get("model"),
        status=data.get("status", "liberado"),
        quilometragem_atual=data.get("mileage", 0),
        data_ultima_manutencao=parse_date(data.get("lastMaintenance")),
        data_proxima_manutencao=parse_date(data.get("nextMaintenance")),
    )
    db.session.add(caminhao)
    db.session.commit()
    return jsonify(caminhao.to_dict()), 201


@truck_bp.route("/<int:truck_id>", methods=["PUT"])
def update_truck(truck_id):
    caminhao = Caminhao.query.get_or_404(truck_id)
    data = request.get_json()

    old_next_maintenance = caminhao.data_proxima_manutencao

    if "plate" in data:
        caminhao.placa = data["plate"]
    if "model" in data:
        caminhao.modelo = data["model"]
    if "status" in data:
        caminhao.status = data["status"]
    if "mileage" in data:
        caminhao.quilometragem_atual = data["mileage"]
    if "lastMaintenance" in data:
        caminhao.data_ultima_manutencao = parse_date(data["lastMaintenance"])

    # Se atualizou a data da próxima manutenção
    if "nextMaintenance" in data:
        new_date = parse_date(data["nextMaintenance"])
        caminhao.data_proxima_manutencao = new_date

        # Se jogou a data para frente, libera o caminhão automaticamente
        if new_date and new_date > date.today():
            caminhao.status = "liberado"

    # Histórico de manutenção automático quando alterar próxima manutenção
    if (
        old_next_maintenance != caminhao.data_proxima_manutencao
        and caminhao.data_proxima_manutencao
    ):
        manutencao = Manutencao(
            id_caminhao=caminhao.id_caminhao,
            data_manutencao=caminhao.data_proxima_manutencao,
            tipo="preventiva",
            quilometragem=caminhao.quilometragem_atual,
            descricao="Data de próxima manutenção ajustada pela tela de Frota.",
            nome_mecanico="Sistema",
        )
        db.session.add(manutencao)

    db.session.commit()
    return jsonify(caminhao.to_dict())


@truck_bp.route("/<int:truck_id>", methods=["DELETE"])
def delete_truck(truck_id):
    caminhao = Caminhao.query.get_or_404(truck_id)
    db.session.delete(caminhao)
    db.session.commit()
    return jsonify({"message": "Caminhão removido com sucesso"})

@truck_bp.route("/my", methods=["GET"])
def get_my_trucks():
    user_id = request.args.get("userId", type=int)
    if not user_id:
        return jsonify({"error": "userId é obrigatório"}), 400

    condutor = Condutor.query.filter_by(id_usuario=user_id).first()
    if not condutor:
        return jsonify([])

    response = []
    ordered_links = sorted(
        condutor.vinculos,
        key=lambda vinc: (
            0 if vinc.ativo else 1,
            (vinc.data_inicio or date.min)
        ),
    )

    for vinculo in ordered_links:
        caminhao = Caminhao.query.get(vinculo.id_caminhao)
        if not caminhao:
            continue
        payload = caminhao.to_dict()
        payload.update(
            {
                "linkActive": vinculo.ativo,
                "linkStartedAt": vinculo.data_inicio.isoformat()
                if vinculo.data_inicio
                else None,
                "linkEndedAt": vinculo.data_fim.isoformat()
                if vinculo.data_fim
                else None,
            }
        )
        response.append(payload)

    # Fallback para base sem histórico salvo
    if not response and condutor.id_caminhao:
        caminhao = Caminhao.query.get(condutor.id_caminhao)
        if caminhao:
            payload = caminhao.to_dict()
            payload.update(
                {"linkActive": True, "linkStartedAt": None, "linkEndedAt": None}
            )
            response.append(payload)

    return jsonify(response), 200

# Dentro do código de desbloqueio do caminhão
@truck_bp.route('/unlock/<int:id_caminhao>', methods=['POST'])
def unlock_truck(id_caminhao):
    caminhão = Caminhao.query.get(id_caminhao)
    
    if caminhão and caminhão.status == 'bloqueado':
        caminhão.status = 'liberado'
        db.session.commit()
        
        # Enviar notificação para o motorista
        send_unlock_notification(caminhão)  # Função para enviar notificação de desbloqueio
        
        return jsonify({"message": "Caminhão desbloqueado com sucesso!"}), 200
    return jsonify({"message": "Caminhão não encontrado ou já desbloqueado."}), 404

@truck_bp.route('/my-trucks', methods=['GET'])
def legacy_my_trucks():
    """Mantido por compatibilidade: delega para /my."""
    return get_my_trucks()
