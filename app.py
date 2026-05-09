from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-esta-chave-em-producao-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///precifica.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── MODELS ──────────────────────────────────────────────────────────────────

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    admin = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    custo = db.Column(db.Float, nullable=False)
    frete = db.Column(db.Float, default=0.0)
    tipo = db.Column(db.String(20), nullable=False)  # nacional / importado
    uf_destino = db.Column(db.String(2), nullable=False)
    icms_aliq = db.Column(db.Float, nullable=False)
    icms_regra = db.Column(db.String(200))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref='produtos')

# ── AUTH ────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        u = Usuario.query.get(session['usuario_id'])
        if not u or not u.admin:
            return jsonify({'erro': 'Acesso negado'}), 403
        return f(*args, **kwargs)
    return decorated

# ── ICMS ────────────────────────────────────────────────────────────────────

SE_SUL = ['SP','RJ','MG','ES','PR','RS']

def calcular_icms(uf_dest, tipo):
    if uf_dest == 'SC':
        return 17.0, 'Operação interna SC'
    if tipo == 'importado':
        return 4.0, 'Importado com conteúdo estrangeiro (Res. 13/2012)'
    if uf_dest in SE_SUL:
        return 12.0, 'Interestadual SC → Sul/Sudeste'
    return 7.0, 'Interestadual SC → N/NE/CO'

PIS = 0.0065
COFINS = 0.03
CSLL = 0.0108
IRPJ = 0.012
TOTAL_VENDA = PIS + COFINS + CSLL + IRPJ
MKS = [10, 20, 30, 40, 50, 60]

def calcular_markups(custo, frete, icms_pct):
    ct = custo + frete
    resultados = []
    for mk in MKS:
        preco = ct / (1 - mk / 100)
        tributos = preco * (icms_pct / 100 + TOTAL_VENDA)
        margem = preco - ct - tributos
        margem_pct = (margem / preco * 100) if preco else 0
        resultados.append({
            'mk': mk,
            'preco': round(preco, 2),
            'tributos': round(tributos, 2),
            'margem': round(margem, 2),
            'margem_pct': round(margem_pct, 1),
        })
    return resultados

def calcular_icms_comparativo(custo, frete):
    ct = custo + frete
    comp = {}
    for ic in [4, 7, 12]:
        rows = []
        for mk in MKS:
            preco = ct / (1 - mk / 100)
            trib = preco * (ic / 100 + TOTAL_VENDA)
            mg = preco - ct - trib
            rows.append({
                'mk': mk,
                'preco': round(preco, 2),
                'tributos': round(trib, 2),
                'margem': round(mg, 2),
                'margem_pct': round(mg / preco * 100, 1) if preco else 0,
            })
        comp[ic] = rows
    return comp

# ── ROTAS ───────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return render_template('index.html', usuario=session.get('usuario_nome'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        u = Usuario.query.filter_by(email=data.get('email','').lower()).first()
        if u and u.check_senha(data.get('senha','')):
            session['usuario_id'] = u.id
            session['usuario_nome'] = u.nome
            session['admin'] = u.admin
            return jsonify({'ok': True})
        return jsonify({'erro': 'E-mail ou senha incorretos'}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── API PRODUTOS ─────────────────────────────────────────────────────────────

@app.route('/api/produtos', methods=['GET'])
@login_required
def listar_produtos():
    produtos = Produto.query.order_by(Produto.criado_em.desc()).all()
    return jsonify([{
        'id': p.id,
        'codigo': p.codigo,
        'descricao': p.descricao,
        'custo': p.custo,
        'frete': p.frete,
        'tipo': p.tipo,
        'uf_destino': p.uf_destino,
        'icms_aliq': p.icms_aliq,
        'icms_regra': p.icms_regra,
        'criado_em': p.criado_em.strftime('%d/%m/%Y %H:%M'),
        'usuario': p.usuario.nome if p.usuario else '',
        'markups': calcular_markups(p.custo, p.frete, p.icms_aliq),
        'comparativo': calcular_icms_comparativo(p.custo, p.frete),
    } for p in produtos])

@app.route('/api/produtos', methods=['POST'])
@login_required
def criar_produto():
    d = request.get_json()
    codigo = d.get('codigo','').strip()
    descricao = d.get('descricao','').strip()
    custo = float(d.get('custo', 0))
    frete = float(d.get('frete', 0))
    tipo = d.get('tipo', 'nacional')
    uf_destino = d.get('uf_destino','').upper()

    if not codigo or not descricao or custo <= 0 or not uf_destino:
        return jsonify({'erro': 'Campos obrigatórios faltando'}), 400

    aliq, regra = calcular_icms(uf_destino, tipo)
    p = Produto(
        codigo=codigo, descricao=descricao, custo=custo,
        frete=frete, tipo=tipo, uf_destino=uf_destino,
        icms_aliq=aliq, icms_regra=regra,
        usuario_id=session['usuario_id']
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'ok': True, 'id': p.id})

@app.route('/api/produtos/<int:pid>', methods=['DELETE'])
@login_required
def deletar_produto(pid):
    p = Produto.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/icms', methods=['POST'])
@login_required
def calcular_icms_api():
    d = request.get_json()
    uf = d.get('uf_destino','').upper()
    tipo = d.get('tipo', 'nacional')
    aliq, regra = calcular_icms(uf, tipo)
    return jsonify({'aliq': aliq, 'regra': regra})

# ── API USUÁRIOS (admin) ─────────────────────────────────────────────────────

@app.route('/api/usuarios', methods=['GET'])
@admin_required
def listar_usuarios():
    return jsonify([{
        'id': u.id, 'nome': u.nome, 'email': u.email,
        'admin': u.admin, 'criado_em': u.criado_em.strftime('%d/%m/%Y')
    } for u in Usuario.query.all()])

@app.route('/api/usuarios', methods=['POST'])
@admin_required
def criar_usuario():
    d = request.get_json()
    if Usuario.query.filter_by(email=d['email'].lower()).first():
        return jsonify({'erro': 'E-mail já cadastrado'}), 400
    u = Usuario(nome=d['nome'], email=d['email'].lower(), admin=d.get('admin', False))
    u.set_senha(d['senha'])
    db.session.add(u)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@admin_required
def deletar_usuario(uid):
    if uid == session['usuario_id']:
        return jsonify({'erro': 'Não pode deletar a si mesmo'}), 400
    u = Usuario.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'ok': True})

# ── INIT ─────────────────────────────────────────────────────────────────────

def init_db():
    db.create_all()
    if not Usuario.query.filter_by(email='admin@empresa.com').first():
        admin = Usuario(nome='Administrador', email='admin@empresa.com', admin=True)
        admin.set_senha('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Usuário admin criado: admin@empresa.com / admin123')

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)
