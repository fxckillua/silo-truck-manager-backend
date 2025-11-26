# backend/services/maintenance_alerts.py

from datetime import date, timedelta
from database import db
from models import Caminhao, Notificacao, Usuario, Condutor, CaminhaoCondutor
from sqlalchemy import or_


# def update_truck_status_and_notifications():
#     """Atualiza status dos caminhões e gera notificações automáticas
#     com base na data_proxima_manutencao.
#     - 2 dias antes: status 'pendente' + notificação de manutenção próxima
#     - No dia: status 'pendente' + notificação de dia de manutenção
#     - Após a data: status 'bloqueado' + notificação de caminhão bloqueado
#     Para perfis: administrador, mecanico e motorista.
#     """
#     today = date.today()

#     # Apenas caminhões que têm data_proxima_manutencao definida
#     trucks = Caminhao.query.filter(Caminhao.data_proxima_manutencao.isnot(None)).all()

#     # Usuários que devem receber as notificações
#     users = Usuario.query.filter(
#         Usuario.perfil.in_(["administrador", "mecanico", "motorista"])
#     ).all()

#     for truck in trucks:
#         next_date = truck.data_proxima_manutencao
#         diff_days = (next_date - today).days

#         # Começa assumindo o status atual
#         new_status = truck.status
#         notif_type = None
#         title = None
#         message = None

#         # Mais de 2 dias antes → mantém status atual.
#         # Se estava pendente (setado automaticamente), voltamos para liberado.
#         if diff_days > 2:
#             if truck.status == "pendente":
#                 new_status = "liberado"
#             else:
#                 # Se estava "bloqueado" manualmente, continua bloqueado.
#                 # Se estava "liberado", continua liberado.
#                 new_status = truck.status

#         # Exatamente 2 dias antes → pendente + notificação de "manutenção próxima"
#         elif diff_days == 2:
#             new_status = "pendente"
#             notif_type = "alerta"  # mapeado para "warning" no to_dict
#             title = f"Manutenção próxima - Caminhão {truck.placa}"
#             message = (
#                 f"Atenção: a manutenção do caminhão {truck.placa} "
#                 f"está agendada para {next_date.strftime('%d/%m/%Y')}."
#             )

#         # No dia da manutenção → pendente + notificação de "dia de manutenção"
#         elif diff_days == 0:
#             new_status = "pendente"
#             notif_type = "manutencao"  # mapeado para "error"
#             title = f"Dia de manutenção - Caminhão {truck.placa}"
#             message = (
#                 f"Hoje é o dia programado para a manutenção do caminhão "
#                 f"{truck.placa} ({next_date.strftime('%d/%m/%Y')})."
#             )

#         # Após a data → bloqueado + notificação de "caminhão bloqueado"
#         elif diff_days < 0:
#             new_status = "bloqueado"
#             notif_type = "manutencao"  # também em vermelho
#             title = f"Caminhão bloqueado - {truck.placa}"
#             message = (
#                 f"O caminhão {truck.placa} foi bloqueado por estar com a "
#                 f"manutenção vencida desde {next_date.strftime('%d/%m/%Y')}."
#             )

#         # Atualiza o status do caminhão, se mudou
#         if new_status != truck.status:
#             truck.status = new_status

#         # Gera notificações (evitando duplicar a mesma notificação no mesmo dia)
#         if notif_type and title and message and users:
#             for user in users:
#                 exists = (
#                     Notificacao.query.filter_by(
#                         id_usuario=user.id_usuario,
#                         titulo=title,
#                         mensagem=message,
#                         tipo=notif_type,
#                     )
#                     .filter(func.date(Notificacao.data_envio) == today)
#                     .first()
#                 )

#                 if not exists:
#                     notif = Notificacao(
#                         id_usuario=user.id_usuario,
#                         id_caminhao=truck.id_caminhao,
#                         titulo=title,
#                         mensagem=message,
#                         tipo=notif_type,
#                     )
#                     db.session.add(notif)

#     db.session.commit()

def get_truck_driver_users(truck_id: int, include_history_days: int = 30):
    """Retorna usuários motoristas vinculados (ativos ou recentes) a um caminhão."""
    if not truck_id:
        return []

    cutoff = date.today() - timedelta(days=include_history_days)
    vinculos = (
        CaminhaoCondutor.query
        .join(Condutor)
        .join(Usuario)
        .filter(
            CaminhaoCondutor.id_caminhao == truck_id,
            or_(
                CaminhaoCondutor.ativo == True,  # noqa: E712
                CaminhaoCondutor.data_fim.is_(None),
                CaminhaoCondutor.data_fim >= cutoff,
            ),
        )
        .all()
    )

    users = []
    seen_ids = set()
    for vinculo in vinculos:
        usuario = vinculo.condutor.usuario if vinculo.condutor else None
        if usuario and usuario.id_usuario not in seen_ids:
            users.append(usuario)
            seen_ids.add(usuario.id_usuario)

    # Fallback para bases antigas sem registro em caminhões_condutores
    if not users:
        condutor = Condutor.query.filter_by(id_caminhao=truck_id).first()
        if condutor and condutor.usuario and condutor.usuario.id_usuario not in seen_ids:
            users.append(condutor.usuario)

    return users


def update_truck_status_and_notifications():
    """Atualiza status dos caminhões e gera notificações automáticas
    com base na data_proxima_manutencao.
    - 2 dias antes: status 'pendente' + notificação de manutenção próxima
    - No dia: status 'pendente' + notificação de dia de manutenção
    - Após a data: status 'bloqueado' + notificação de caminhão bloqueado

    Admins e mecânicos recebem de todos os caminhões.
    Motorista recebe apenas do caminhão vinculado a ele (via tabela condutores).
    """
    today = date.today()

    # Apenas caminhões que têm data_proxima_manutencao definida
    trucks = Caminhao.query.filter(Caminhao.data_proxima_manutencao.isnot(None)).all()

    # Usuários base (recebem de todos os caminhões)
    base_users = Usuario.query.filter(
        Usuario.perfil.in_(["administrador", "mecanico"])  # coloque "gestor" se usar
    ).all()

    for truck in trucks:
        next_date = truck.data_proxima_manutencao
        diff_days = (next_date - today).days

        if truck.status == "bloqueado" and diff_days >= 0:
        # mantém bloqueado e segue para o próximo caminhão
            continue

        # Começa assumindo o status atual
        new_status = truck.status
        notif_type = None
        title = None
        message = None

        # Mais de 2 dias antes → mantém status atual.
        # Se estava pendente (setado automaticamente), voltamos para liberado.
        if diff_days > 2:
            if truck.status == "pendente":
                new_status = "liberado"

        # Exatamente 2 dias antes → pendente + notificação de "manutenção próxima"
        elif diff_days == 2:
            
            notif_type = "alerta"  # mapeado para "warning" no frontend
            title = f"Manutenção próxima - Caminhão {truck.placa}"
            message = (
                f"Atenção: a manutenção do caminhão {truck.placa} "
                f"está agendada para {next_date.strftime('%d/%m/%Y')}."
            )

        # No dia da manutenção → pendente + notificação de "dia de manutenção"
        elif diff_days == 0:
            
            notif_type = "info"  # mapeado para "error"
            title = f"Dia de manutenção - Caminhão {truck.placa}"
            message = (
                f"Hoje é o dia programado para a manutenção do caminhão "
                f"{truck.placa} ({next_date.strftime('%d/%m/%Y')})."
            )

        # Após a data → bloqueado + notificação de "caminhão bloqueado"
        elif diff_days < 0:
            new_status = "bloqueado"
            notif_type = "manutencao"  # também em vermelho
            title = f"Caminhão bloqueado - {truck.placa}"
            message = (
                f"O caminhão {truck.placa} foi bloqueado por estar com a "
                f"manutenção vencida desde {next_date.strftime('%d/%m/%Y')}."
            )

        # Atualiza o status do caminhão, se mudou
        if new_status != truck.status:
            truck.status = new_status

        # Se não há notificação pra esse caminhão, passa pro próximo
        if not (notif_type and title and message):
            continue

        # ---- DEFINIÇÃO DE DESTINATÁRIOS POR CAMINHÃO ----
        # Começa com admins/mecânicos
        recipients = list(base_users)

        motoristas = get_truck_driver_users(truck.id_caminhao)
        for motorista in motoristas:
            if all(u.id_usuario != motorista.id_usuario for u in recipients):
                recipients.append(motorista)

        # Gera notificações (evitando duplicar a mesma notificação enquanto não lida)
        for user in recipients:
            exists = (
                Notificacao.query.filter_by(
                    id_usuario=user.id_usuario,
                    id_caminhao=truck.id_caminhao,
                    tipo=notif_type,
                    titulo=title,
                )
                .filter(Notificacao.visualizado == False)
                .first()
            )

            if not exists:
                notif = Notificacao(
                    id_usuario=user.id_usuario,
                    id_caminhao=truck.id_caminhao,
                    titulo=title,
                    mensagem=message,
                    tipo=notif_type,
                )
                db.session.add(notif)

    db.session.commit()

def send_unlock_notification(caminhao):
    if not caminhao:
        return

    motoristas = get_truck_driver_users(caminhao.id_caminhao, include_history_days=90)
    if not motoristas:
        return

    for motorista in motoristas:
        notificacao = Notificacao(
            id_usuario=motorista.id_usuario,
            id_caminhao=caminhao.id_caminhao,
            titulo=f"Caminhão {caminhao.placa} desbloqueado",
            mensagem=(
                f"O caminhão {caminhao.placa} foi desbloqueado e agora pode ser utilizado novamente."
            ),
            tipo="info",
        )
        db.session.add(notificacao)

    db.session.commit()


