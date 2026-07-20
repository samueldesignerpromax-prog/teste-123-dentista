from flask import Flask, render_template, request, jsonify, session
from models import db, Dentista, Servico, Agendamento, Conversa
from datetime import datetime, timedelta
import re
import uuid

app = Flask(__name__)
app.secret_key = 'chave-secreta-para-session'  # Mude para uma chave real

# Configuração do banco (SQLite para desenvolvimento)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Cria as tabelas e insere dados de exemplo
with app.app_context():
    db.create_all()
    if not Dentista.query.first():
        d1 = Dentista(nome='Dra. Ana', especialidade='Ortodontia')
        d2 = Dentista(nome='Dr. Carlos', especialidade='Implantodontia')
        db.session.add_all([d1, d2])
        db.session.commit()
    if not Servico.query.first():
        s1 = Servico(nome='Limpeza', duracao_minutos=30)
        s2 = Servico(nome='Obturação', duracao_minutos=45)
        s3 = Servico(nome='Clareamento', duracao_minutos=60)
        db.session.add_all([s1, s2, s3])
        db.session.commit()

# ------------------ Lógica do Bot ------------------
class DentBot:
    """
    Bot baseado em regras para agendamento.
    Mantém estado da conversa via session.
    """
    def __init__(self, session_id):
        self.session_id = session_id
        # Estado: 'inicio', 'aguardando_nome', 'aguardando_telefone', 'aguardando_servico', 'aguardando_data', 'aguardando_confirmacao'
        self.estado = 'inicio'
        self.dados = {}

    def processar(self, mensagem):
        mensagem = mensagem.strip().lower()
        respostas = []

        if self.estado == 'inicio':
            respostas.append("Olá! Sou o DentBot, assistente da Clínica Sorriso. Posso ajudar com agendamentos ou informações.")
            respostas.append("Para agendar, diga 'agendar'. Para ver serviços, diga 'serviços'. Ou 'dentistas' para ver os profissionais.")
            self.estado = 'menu'
            return "\n".join(respostas)

        elif self.estado == 'menu':
            if 'agendar' in mensagem:
                respostas.append("Ótimo! Vamos agendar. Qual o seu nome completo?")
                self.estado = 'aguardando_nome'
                return "\n".join(respostas)
            elif 'serviço' in mensagem or 'servicos' in mensagem:
                servicos = Servico.query.all()
                lista = ", ".join([s.nome for s in servicos])
                respostas.append(f"Oferecemos os seguintes serviços: {lista}.")
                respostas.append("Deseja agendar algum? Diga 'agendar'.")
                # Continua no menu
                return "\n".join(respostas)
            elif 'dentista' in mensagem:
                dentistas = Dentista.query.all()
                lista = ", ".join([f"{d.nome} ({d.especialidade})" for d in dentistas])
                respostas.append(f"Nossos dentistas: {lista}.")
                respostas.append("Deseja agendar? Diga 'agendar'.")
                return "\n".join(respostas)
            else:
                respostas.append("Não entendi. Você pode dizer 'agendar', 'serviços' ou 'dentistas'.")
                return "\n".join(respostas)

        elif self.estado == 'aguardando_nome':
            # Salva nome
            self.dados['nome'] = mensagem.title()
            respostas.append(f"Obrigado, {self.dados['nome']}. Agora, qual o seu telefone para contato?")
            self.estado = 'aguardando_telefone'
            return "\n".join(respostas)

        elif self.estado == 'aguardando_telefone':
            # Validação simples (pelo menos 8 dígitos)
            if re.search(r'\d{8,}', mensagem):
                self.dados['telefone'] = mensagem
                # Perguntar serviço
                servicos = Servico.query.all()
                lista = ", ".join([s.nome for s in servicos])
                respostas.append(f"Qual serviço você deseja? Temos: {lista}.")
                self.estado = 'aguardando_servico'
                return "\n".join(respostas)
            else:
                respostas.append("Telefone inválido. Digite um número com pelo menos 8 dígitos.")
                return "\n".join(respostas)

        elif self.estado == 'aguardando_servico':
            # Tentar encontrar o serviço digitado
            servicos = Servico.query.all()
            servico_encontrado = None
            for s in servicos:
                if s.nome.lower() in mensagem:
                    servico_encontrado = s
                    break
            if servico_encontrado:
                self.dados['servico_id'] = servico_encontrado.id
                respostas.append(f"Serviço '{servico_encontrado.nome}' selecionado. Agora, qual dentista prefere?")
                dentistas = Dentista.query.all()
                lista = ", ".join([d.nome for d in dentistas])
                respostas.append(f"Dentistas: {lista}.")
                self.estado = 'aguardando_dentista'
                return "\n".join(respostas)
            else:
                lista_serv = ", ".join([s.nome for s in servicos])
                respostas.append(f"Não reconheci. Digite um dos serviços: {lista_serv}.")
                return "\n".join(respostas)

        elif self.estado == 'aguardando_dentista':
            dentistas = Dentista.query.all()
            dentista_encontrado = None
            for d in dentistas:
                if d.nome.lower() in mensagem:
                    dentista_encontrado = d
                    break
            if dentista_encontrado:
                self.dados['dentista_id'] = dentista_encontrado.id
                respostas.append(f"Dentista {dentista_encontrado.nome} selecionado. Agora, em qual data e horário?")
                respostas.append("Por favor, digite no formato DD/MM/AAAA HH:MM (ex: 25/12/2025 14:30).")
                self.estado = 'aguardando_data'
                return "\n".join(respostas)
            else:
                lista_dent = ", ".join([d.nome for d in dentistas])
                respostas.append(f"Escolha um dentista: {lista_dent}.")
                return "\n".join(respostas)

        elif self.estado == 'aguardando_data':
            # Tenta parsear data/hora
            try:
                # Aceita formato DD/MM/AAAA HH:MM
                partes = re.split(r'[ /:]', mensagem)
                if len(partes) >= 5:
                    dia, mes, ano, hora, minuto = int(partes[0]), int(partes[1]), int(partes[2]), int(partes[3]), int(partes[4])
                    data_hora = datetime(ano, mes, dia, hora, minuto)
                    # Verifica se é futuro
                    if data_hora < datetime.now():
                        respostas.append("A data precisa ser futura. Tente novamente.")
                        return "\n".join(respostas)
                    # Verifica disponibilidade (simplificado)
                    ocupados = Agendamento.query.filter_by(
                        dentista_id=self.dados['dentista_id'],
                        data_hora=data_hora
                    ).first()
                    if ocupados:
                        respostas.append("Esse horário já está ocupado. Escolha outro.")
                        return "\n".join(respostas)
                    # Salva
                    self.dados['data_hora'] = data_hora
                    # Resumo
                    servico = Servico.query.get(self.dados['servico_id'])
                    dentista = Dentista.query.get(self.dados['dentista_id'])
                    respostas.append(f"Resumo do agendamento:")
                    respostas.append(f"Nome: {self.dados['nome']}")
                    respostas.append(f"Telefone: {self.dados['telefone']}")
                    respostas.append(f"Serviço: {servico.nome if servico else 'N/A'}")
                    respostas.append(f"Dentista: {dentista.nome if dentista else 'N/A'}")
                    respostas.append(f"Data/Hora: {data_hora.strftime('%d/%m/%Y %H:%M')}")
                    respostas.append("Confirma o agendamento? Responda 'sim' ou 'não'.")
                    self.estado = 'aguardando_confirmacao'
                    return "\n".join(respostas)
                else:
                    respostas.append("Formato inválido. Use DD/MM/AAAA HH:MM.")
                    return "\n".join(respostas)
            except Exception as e:
                respostas.append("Formato inválido. Use DD/MM/AAAA HH:MM.")
                return "\n".join(respostas)

        elif self.estado == 'aguardando_confirmacao':
            if 'sim' in mensagem:
                # Cria o agendamento
                novo = Agendamento(
                    cliente_nome=self.dados['nome'],
                    cliente_telefone=self.dados['telefone'],
                    dentista_id=self.dados['dentista_id'],
                    servico_id=self.dados['servico_id'],
                    data_hora=self.dados['data_hora']
                )
                db.session.add(novo)
                db.session.commit()
                respostas.append(f"✅ Agendamento confirmado! ID: {novo.id}. Obrigado!")
                self.estado = 'inicio'
                self.dados = {}
                return "\n".join(respostas)
            elif 'não' in mensagem or 'nao' in mensagem:
                respostas.append("Agendamento cancelado. Deseja tentar novamente? Diga 'agendar'.")
                self.estado = 'menu'
                self.dados = {}
                return "\n".join(respostas)
            else:
                respostas.append("Responda 'sim' para confirmar ou 'não' para cancelar.")
                return "\n".join(respostas)

        else:
            return "Desculpe, não entendi. Vamos recomeçar. Diga 'agendar'."

# Roteamento
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/agendar')
def agendar():
    dentistas = Dentista.query.all()
    servicos = Servico.query.all()
    return render_template('agendar.html', dentistas=dentistas, servicos=servicos)

@app.route('/api/chat', methods=['POST'])
def chat():
    mensagem = request.json.get('mensagem')
    if not mensagem:
        return jsonify({'erro': 'Mensagem vazia'}), 400

    # Gera ou recupera session_id
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
    # Armazena o estado do bot na session do Flask (ou em banco)
    # Vou usar a session do Flask para simplificar
    if 'bot_estado' not in session:
        session['bot_estado'] = 'inicio'
        session['bot_dados'] = {}
    # Recupera o estado
    estado = session.get('bot_estado', 'inicio')
    dados = session.get('bot_dados', {})

    # Instancia o bot com o estado atual
    bot = DentBot(session_id)
    bot.estado = estado
    bot.dados = dados

    resposta = bot.processar(mensagem)

    # Salva novo estado
    session['bot_estado'] = bot.estado
    session['bot_dados'] = bot.dados

    # Salvar conversa (opcional)
    conv = Conversa(session_id=session_id, mensagem=mensagem, resposta=resposta)
    db.session.add(conv)
    db.session.commit()

    resp = jsonify({'resposta': resposta})
    resp.set_cookie('session_id', session_id)
    return resp

# API para obter horários disponíveis (para o formulário)
@app.route('/api/horarios', methods=['GET'])
def horarios():
    data_str = request.args.get('data')
    dentista_id = request.args.get('dentista_id')
    if not data_str or not dentista_id:
        return jsonify([])
    try:
        data = datetime.strptime(data_str, '%Y-%m-%d')
    except:
        return jsonify([])
    # Gera slots das 9h às 17h com intervalo de 30min
    slots = []
    start = data.replace(hour=9, minute=0)
    end = data.replace(hour=17, minute=0)
    while start < end:
        slots.append(start.strftime('%H:%M'))
        start += timedelta(minutes=30)
    # Filtra ocupados
    ocupados = Agendamento.query.filter(
        Agendamento.dentista_id == dentista_id,
        Agendamento.data_hora >= data,
        Agendamento.data_hora < data + timedelta(days=1)
    ).all()
    ocupados_set = {a.data_hora.strftime('%H:%M') for a in ocupados}
    disponiveis = [s for s in slots if s not in ocupados_set]
    return jsonify(disponiveis)

@app.route('/api/agendar', methods=['POST'])
def criar_agendamento():
    dados = request.json
    try:
        data_hora = datetime.fromisoformat(dados['data_hora'])
    except:
        return jsonify({'erro': 'Data inválida'}), 400
    novo = Agendamento(
        cliente_nome=dados['nome'],
        cliente_email=dados.get('email'),
        cliente_telefone=dados['telefone'],
        dentista_id=dados['dentista_id'],
        servico_id=dados['servico_id'],
        data_hora=data_hora
    )
    db.session.add(novo)
    db.session.commit()
    return jsonify({'status': 'sucesso', 'id': novo.id})

if __name__ == '__main__':
    app.run(debug=True)
