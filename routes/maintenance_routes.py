from flask import Blueprint, request, jsonify
from models import Manutencao, Caminhao
from database import db
from datetime import datetime, date
from services.maintenance_alerts import update_truck_status_and_notifications

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/maintenances")


@maintenance_bp.route("/", methods=["GET"])
def get_maintenances():
    """Retorna todas as manutenções cadastradas."""
    maints = Manutencao.query.all()
    return jsonify([m.to_dict() for m in maints])


@maintenance_bp.route("/", methods=["POST"])
def create_maintenance():
    """
    Cria um novo registro de manutenção para um caminhão.

    Espera JSON no formato:
    {
        "truckId": <id do caminhão>,
        "type": "preventiva" | "corretiva",
        "date": "YYYY-MM-DD",          # será usada como PRÓXIMA manutenção
        "mileage": <quilometragem>,
        "description": "texto",
        "mechanicName": "nome do mecânico"
    }
    """
    data = request.get_json() or {}

    truck_id = data.get("truckId")
    if not truck_id:
        return jsonify({"error": "truckId é obrigatório"}), 400

    truck = Caminhao.query.get(truck_id)
    if not truck:
        return jsonify({"error": "Caminhão não encontrado"}), 404

    # Data informada no formulário
    maintenance_date = parse_date(data.get("date"))

    # Tipo de manutenção
    tipo = data.get("type") or "preventiva"

    # Quilometragem (pode vir como string)
    mileage_raw = data.get("mileage")
    mileage = None
    if mileage_raw not in (None, ""):
        try:
            mileage = int(mileage_raw)
        except (TypeError, ValueError):
            mileage = None

    descricao = data.get("description") or ""
    mechanic_name = data.get("mechanicName") or ""

    # 1) Registrar no histórico de manutenções
    manutencao = Manutencao(
        id_caminhao=truck.id_caminhao,
        data_manutencao=maintenance_date,
        tipo=tipo,
        quilometragem=mileage,
        descricao=descricao,
        nome_mecanico=mechanic_name,
    )
    db.session.add(manutencao)

    # 2) Atualizar dados do caminhão

    # Atualiza quilometragem atual se foi informada
    if mileage is not None:
        truck.quilometragem_atual = mileage

    # *** PONTO IMPORTANTE DO SEU BUG ***
    # A data da tela de Manutenções passa a ser tratada como
    # PRÓXIMA manutenção, não como ÚLTIMA.
    if maintenance_date is not None:
        truck.data_proxima_manutencao = maintenance_date
        # NÃO mexemos em truck.data_ultima_manutencao aqui

    db.session.commit()

    # 3) Recalcular status + gerar notificações automáticas
    # (usa data_proxima_manutencao de todos os caminhões)
    update_truck_status_and_notifications()

    return jsonify(manutencao.to_dict()), 201

@maintenance_bp.route("/<int:maintenance_id>", methods=["PUT"])
def update_maintenance(maintenance_id):
    """Atualiza um registro de manutenção existente."""
    manutencao = Manutencao.query.get_or_404(maintenance_id)
    data = request.get_json() or {}

    # Atualiza campos básicos da manutenção
    maintenance_date = parse_date(data.get("date"))
    if maintenance_date:
        manutencao.data_manutencao = maintenance_date

    tipo = data.get("type")
    if tipo:
        tipo = (tipo or "").lower()
        if tipo in ("preventiva", "corretiva"):
            manutencao.tipo = tipo

    mileage_raw = data.get("mileage")
    if mileage_raw not in (None, ""):
        try:
            manutencao.quilometragem = int(mileage_raw)
        except (TypeError, ValueError):
            pass

    descricao = data.get("description")
    if descricao is not None:
        manutencao.descricao = descricao

    mechanic_name = data.get("mechanicName")
    if mechanic_name is not None:
        manutencao.nome_mecanico = mechanic_name

    # Atualiza também os campos do caminhão ligado a essa manutenção
    caminhao = Caminhao.query.get(manutencao.id_caminhao)
    if caminhao:
        today = date.today()

        # Atualiza quilometragem atual se tiver
        if manutencao.quilometragem is not None:
            caminhao.quilometragem_atual = manutencao.quilometragem

        # Mesma lógica da criação:
        # • data FUTURA -> próxima manutenção
        # • data HOJE/passado -> última
        if maintenance_date:
            if maintenance_date >= today:
                caminhao.data_proxima_manutencao = maintenance_date
                if caminhao.data_ultima_manutencao is None:
                    caminhao.data_ultima_manutencao = maintenance_date
            else:
                caminhao.data_ultima_manutencao = maintenance_date

    db.session.commit()
    return jsonify(manutencao.to_dict())

@maintenance_bp.route("/<int:maintenance_id>", methods=["DELETE"])
def delete_maintenance(maintenance_id):
    """Remove um registro de manutenção pelo ID."""
    manutencao = Manutencao.query.get_or_404(maintenance_id)
    db.session.delete(manutencao)
    db.session.commit()
    return jsonify({"message": "Manutenção removida com sucesso"})


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None
