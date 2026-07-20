from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timedelta
from models import db, Dentista, Servico, Agendamento

# Inicializar Flask
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Configuração do banco de dados (PostgreSQL via DATABASE_URL, ou fallback para SQLite local)
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    database_url = 'sqlite:///database.db'
else:
    # Ajuste para SQLAlchemy (postgres:// -> postgresql://)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Criar tabelas e dados iniciais (se necessário)
with app.app_context():
    db.create_all()
    # Inserir dados de exemplo se não houver
    if Dentista.query.count() == 0:
        d1 = Dentista(nome='Dra. Ana', especialidade='Ortodontia')
        d2 = Dentista(nome='Dr. Carlos', especialidade='Implantodontia')
        db.session.add_all([d1, d2])
        db.session.commit()
    if Servico.query.count() == 0:
        s1 = Servico(nome='Limpeza', duracao_minutos=30)
        s2 = Servico(nome='Obturação', duracao_minutos=45)
        s3 = Servico(nome='Clareamento', duracao_minutos=60)
        db.session.add_all([s1, s2, s3])
        db.session.commit()

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/agendar', methods=['GET', 'POST'])
def agendar():
    if request.method == 'POST':
        # Processar formulário
        nome = request.form['nome']
        email = request.form.get('email')
        telefone = request.form['telefone']
        dentista_id = int(request.form['dentista_id'])
        servico_id = int(request.form['servico_id'])
        data_hora_str = request.form['data_hora']  # formato ISO: "2025-07-20T10:30"
        data_hora = datetime.fromisoformat(data_hora_str)

        # Verificar disponibilidade
        conflito = Agendamento.query.filter_by(
            dentista_id=dentista_id,
            data_hora=data_hora
        ).first()
        if conflito:
            # Re-renderizar com erro
            dentistas = Dentista.query.all()
            servicos = Servico.query.all()
            return render_template('agendar.html', dentistas=dentistas, servicos=servicos,
                                   erro='Horário indisponível. Escolha outro.', 
                                   dados_form=request.form)

        # Criar agendamento
        novo = Agendamento(
            cliente_nome=nome,
            cliente_email=email,
            cliente_telefone=telefone,
            dentista_id=dentista_id,
            servico_id=servico_id,
            data_hora=data_hora
        )
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('sucesso', id=novo.id))

    # GET: exibir formulário
    dentistas = Dentista.query.all()
    servicos = Servico.query.all()
    return render_template('agendar.html', dentistas=dentistas, servicos=servicos, erro=None)

@app.route('/sucesso')
def sucesso():
    agendamento_id = request.args.get('id')
    agendamento = Agendamento.query.get(agendamento_id)
    return render_template('sucesso.html', agendamento=agendamento)

# API para buscar horários disponíveis (usado via AJAX)
@app.route('/api/horarios')
def api_horarios():
    data_str = request.args.get('data')  # formato "2025-07-20"
    dentista_id = request.args.get('dentista_id')
    if not data_str or not dentista_id:
        return jsonify({'erro': 'Parâmetros faltando'}), 400

    data = datetime.strptime(data_str, '%Y-%m-%d')
    dentista_id = int(dentista_id)

    # Definir slots: das 9h às 17h com intervalo de 30 minutos
    slots = []
    start = data.replace(hour=9, minute=0, second=0)
    end = data.replace(hour=17, minute=0, second=0)
    current = start
    while current < end:
        slots.append(current)
        current += timedelta(minutes=30)

    # Buscar agendamentos existentes para esse dentista nesse dia
    agendamentos = Agendamento.query.filter(
        Agendamento.dentista_id == dentista_id,
        Agendamento.data_hora >= start,
        Agendamento.data_hora < end
    ).all()
    ocupados = {a.data_hora for a in agendamentos}

    # Filtrar slots disponíveis
    disponiveis = [s.isoformat() for s in slots if s not in ocupados]
    return jsonify({'horarios': disponiveis})

# (Opcional) Rota para listar agendamentos (admin)
@app.route('/admin')
def admin():
    agendamentos = Agendamento.query.order_by(Agendamento.data_hora).all()
    return render_template('admin.html', agendamentos=agendamentos)
