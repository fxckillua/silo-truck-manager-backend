from database import db
from datetime import datetime, date

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.Enum('administrador', 'gestor', 'motorista', 'mecanico'), nullable=False)
    status = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": str(self.id_usuario),
            "name": self.nome,
            "email": self.email,
            "profile": self.perfil
        }

class Caminhao(db.Model):
    __tablename__ = "caminhoes"
    
    id_caminhao = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), unique=True, nullable=False)
    modelo = db.Column(db.String(50))
    quilometragem_atual = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum('liberado', 'bloqueado', 'pendente'), default='liberado')
    data_ultima_manutencao = db.Column(db.Date, nullable=True)
    data_proxima_manutencao = db.Column(db.Date, nullable=True)

    def to_dict(self):
        return {
            "id": self.id_caminhao,
            "plate": self.placa,
            "model": self.modelo,
            "mileage": self.quilometragem_atual,
            "status": self.status,
            "lastMaintenance": self.data_ultima_manutencao.isoformat() if self.data_ultima_manutencao else None,
            "nextMaintenance": self.data_proxima_manutencao.isoformat() if self.data_proxima_manutencao else None,
            "driverName": self.condutor.nome if hasattr(self, "condutor") and self.condutor else None,
            "driverId": self.condutor.id_condutor if hasattr(self, "condutor") and self.condutor else None,
        }


class Condutor(db.Model):
    __tablename__ = "condutores"

    id_condutor = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cnh = db.Column(db.String(20), nullable=False, unique=True)
    telefone = db.Column(db.String(15))
    email = db.Column(db.String(100))

    id_usuario = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id_usuario"),
        unique=True,
        nullable=True,
    )
    # Mantém referência direta apenas para o caminhão principal atual.
    id_caminhao = db.Column(
        db.Integer,
        db.ForeignKey("caminhoes.id_caminhao"),
        nullable=True,
    )

    usuario = db.relationship("Usuario", backref=db.backref("condutor", uselist=False))
    caminhao = db.relationship("Caminhao", backref=db.backref("condutor", uselist=False))

    vinculos = db.relationship(
        "CaminhaoCondutor",
        back_populates="condutor",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id_condutor,
            "nome": self.nome,
            "cnh": self.cnh,
            "telefone": self.telefone,
            "email": self.email,
            "usuarioId": self.id_usuario,
            "caminhaoId": self.id_caminhao,
            "caminhaoPlaca": self.caminhao.placa if self.caminhao else None,
        }


class CaminhaoCondutor(db.Model):
    __tablename__ = "caminhoes_condutores"

    id_vinculo = db.Column(db.Integer, primary_key=True)
    id_caminhao = db.Column(
        db.Integer,
        db.ForeignKey("caminhoes.id_caminhao"),
        nullable=False,
    )
    id_condutor = db.Column(
        db.Integer,
        db.ForeignKey("condutores.id_condutor"),
        nullable=False,
    )
    data_inicio = db.Column(db.Date, nullable=False, default=date.today)
    data_fim = db.Column(db.Date, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

    condutor = db.relationship("Condutor", back_populates="vinculos")
    caminhao = db.relationship(
        "Caminhao",
        backref=db.backref("vinculos_condutor", cascade="all, delete-orphan"),
    )

    def to_dict(self):
        return {
            "id": self.id_vinculo,
            "truckId": self.id_caminhao,
            "driverId": self.id_condutor,
            "active": self.ativo,
            "start": self.data_inicio.isoformat() if self.data_inicio else None,
            "end": self.data_fim.isoformat() if self.data_fim else None,
        }

class Manutencao(db.Model):
    __tablename__ = 'manutencoes'
    id_manutencao = db.Column(db.Integer, primary_key=True)
    id_caminhao = db.Column(db.Integer, db.ForeignKey('caminhoes.id_caminhao'), nullable=False)
    data_manutencao = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.Enum('preventiva', 'corretiva'), nullable=False)
    quilometragem = db.Column(db.Integer)
    descricao = db.Column(db.Text)
    nome_mecanico = db.Column(db.String(100))

    caminhao = db.relationship('Caminhao', backref='manutencoes')

    def to_dict(self):
        return {
            "id": self.id_manutencao,
            "truckId": self.id_caminhao,
            "truckPlate": self.caminhao.placa if self.caminhao else "N/A",
            "date": self.data_manutencao.isoformat() if self.data_manutencao else None,
            "type": self.tipo,
            "mileage": self.quilometragem,
            "description": self.descricao,
            "mechanicName": self.nome_mecanico
        }

# class Notificacao(db.Model):
#     __tablename__ = 'notificacoes'
#     id_notificacao = db.Column(db.Integer, primary_key=True)
#     id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False)
#     titulo = db.Column(db.String(150), nullable=False)
#     mensagem = db.Column(db.Text, nullable=False)
#     tipo = db.Column(db.Enum('alerta', 'info', 'manutencao', 'sistema'), default='info') 
#     data_envio = db.Column(db.DateTime, default=datetime.now)
#     visualizado = db.Column(db.Boolean, default=False)

#     def to_dict(self):
#         # Default para info (azul)
#         frontend_type = 'info'
        
#         # Verifica se o título contém palavras chave para mudar a cor
#         titulo_lower = self.titulo.lower() if self.titulo else ""

#         if self.tipo == 'alerta':
#             # AGORA VERIFICA "BLOQUE" EM GERAL (bloqueado, bloqueio, Bloqueado...)
#             if 'bloque' in titulo_lower:
#                 frontend_type = 'error'  # Ícone X Vermelho
#             else:
#                 frontend_type = 'warning' # Ícone ! Amarelo
#         elif self.tipo == 'manutencao':
#             frontend_type = 'info'
        
#         return {
#             "id": self.id_notificacao,
#             "userId": str(self.id_usuario),
#             "title": self.titulo,
#             "message": self.mensagem,
#             "type": frontend_type,
#             "date": self.data_envio.isoformat(),
#             "read": self.visualizado
#         }

class Notificacao(db.Model):
    __tablename__ = "notificacoes"

    id_notificacao = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuarios.id_usuario"), nullable=False)
    id_caminhao = db.Column(db.Integer, db.ForeignKey("caminhoes.id_caminhao"), nullable=True)

    titulo = db.Column(db.String(150), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.Enum('alerta', 'info', 'manutencao', 'sistema'), default='info')
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    visualizado = db.Column(db.Boolean, default=False)

    usuario = db.relationship("Usuario", backref=db.backref("notificacoes", lazy=True))
    caminhao = db.relationship("Caminhao", backref=db.backref("notificacoes", lazy=True))

    def to_dict(self):
        return {
            "id": self.id_notificacao,
            "userId": self.id_usuario,
            "truckId": self.id_caminhao,
            "title": self.titulo,
            "message": self.mensagem,
            "type": self.tipo,
            "date": self.data_envio.isoformat() if self.data_envio else None,
            "read": self.visualizado,
        }
