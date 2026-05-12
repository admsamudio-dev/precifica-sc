from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'troque-esta-chave-em-producao-123')

# Render usa "postgres://" mas SQLAlchemy exige "postgresql://"
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///precifica.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── MODELS ───────────────────────────────────────────────────────────────────

class Usuario(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    admin      = db.Column(db.Boolean, default=False)
    criado_em  = db.Column(db.DateTime, default=datetime.utcnow)

    def set_senha(self, s):  self.senha_hash = generate_password_hash(s)
    def check_senha(self, s): return check_password_hash(self.senha_hash, s)

class Produto(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    codigo    = db.Column(db.String(50),  nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    custo     = db.Column(db.Float,       nullable=False)
    frete     = db.Column(db.Float,       default=0.0)
    origem    = db.Column(db.String(20),  nullable=False)   # 'nacional' | 'importado'
    criado_por= db.Column(db.String(100), default='')
    criado_em = db.Column(db.DateTime,    default=datetime.utcnow)

# ── DECORATORS ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('usuario_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── INIT DB ──────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not Usuario.query.filter_by(email='admin@empresa.com').first():
            u = Usuario(nome='Administrador', email='admin@empresa.com', admin=True)
            u.set_senha('admin123')
            db.session.add(u)
            db.session.commit()

# ── ROTAS PRINCIPAIS ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    return render_template('index.html',
                           nome=session.get('nome',''),
                           is_admin=session.get('admin', False))

@app.route('/login', methods=['GET','POST'])
def login():
    erro = None
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        senha = request.form.get('senha','')
        u = Usuario.query.filter_by(email=email).first()
        if u and u.check_senha(senha):
            session['usuario_id'] = u.id
            session['nome']       = u.nome
            session['admin']      = u.admin
            return redirect(url_for('index'))
        erro = 'E-mail ou senha incorretos.'
    return render_template('login.html', erro=erro)

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
        'id': p.id, 'codigo': p.codigo, 'descricao': p.descricao,
        'custo': p.custo, 'frete': p.frete, 'origem': p.origem,
        'criado_por': p.criado_por,
        'criado_em': p.criado_em.strftime('%d/%m/%Y %H:%M')
    } for p in produtos])

@app.route('/api/produtos', methods=['POST'])
@login_required
def criar_produto():
    d = request.get_json()
    if not d or not d.get('descricao') or not d.get('origem'):
        return jsonify({'erro': 'Campos obrigatórios faltando.'}), 400
    p = Produto(
        codigo     = d.get('codigo','').strip(),
        descricao  = d.get('descricao','').strip(),
        custo      = float(d.get('custo', 0)),
        frete      = float(d.get('frete', 0)),
        origem     = d.get('origem','nacional'),
        criado_por = session.get('nome','')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'id': p.id}), 201

@app.route('/api/produtos/<int:pid>', methods=['DELETE'])
@login_required
def deletar_produto(pid):
    p = Produto.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'ok': True})

# ── API USUÁRIOS (só admin) ───────────────────────────────────────────────────

@app.route('/api/usuarios', methods=['GET'])
@login_required
def listar_usuarios():
    if not session.get('admin'):
        return jsonify({'erro': 'Acesso negado.'}), 403
    return jsonify([{
        'id': u.id, 'nome': u.nome, 'email': u.email, 'admin': u.admin
    } for u in Usuario.query.all()])

@app.route('/api/usuarios', methods=['POST'])
@login_required
def criar_usuario():
    if not session.get('admin'):
        return jsonify({'erro': 'Acesso negado.'}), 403
    d = request.get_json()
    if Usuario.query.filter_by(email=d['email']).first():
        return jsonify({'erro': 'E-mail já cadastrado.'}), 400
    u = Usuario(nome=d['nome'], email=d['email'], admin=d.get('admin', False))
    u.set_senha(d['senha'])
    db.session.add(u)
    db.session.commit()
    return jsonify({'id': u.id}), 201

@app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
@login_required
def deletar_usuario(uid):
    if not session.get('admin'):
        return jsonify({'erro': 'Acesso negado.'}), 403
    if uid == session.get('usuario_id'):
        return jsonify({'erro': 'Não pode remover a si mesmo.'}), 400
    u = Usuario.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'ok': True})

# ── MAIN ─────────────────────────────────────────────────────────────────────

init_db()

if __name__ == '__main__':
    app.run(debug=False)
