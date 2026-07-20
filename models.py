from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Dentista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especialidade = db.Column(db.String(100))

class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    duracao_minutos = db.Column(db.Integer, default=30)

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(100), nullable=False)
    cliente_email = db.Column(db.String(100))
    cliente_telefone = db.Column(db.String(20), nullable=False)
    dentista_id = db.Column(db.Integer, db.ForeignKey('dentista.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))
    data_hora = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='agendado')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

# Opcional: modelo para histórico de conversas do bot
class Conversa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50), index=True)
    mensagem = db.Column(db.Text)
    resposta = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
