import streamlit as st
from pathlib import Path
import pandas as pd
from datetime import date, timedelta
import time, math, io, hashlib, os
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, text, inspect
from db import engine, SessionLocal, Base
from models import (
    User, Bucket, Giant, Movement, Bill,
    UserProfile, GiantPayment
)
from babel.numbers import format_currency
from babel.dates import format_date
import matplotlib.pyplot as plt

# Configurar estilo do Matplotlib
plt.style.use('default')  # Usar estilo padrão
plt.rcParams.update({
    'axes.facecolor': '#FFFFFF',
    'figure.facecolor': '#FFFFFF',
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.color': '#E5E7EB',
    'axes.labelcolor': '#111827',
    'xtick.color': '#6B7280',
    'ytick.color': '#6B7280',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.autolayout': True,
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 14
})

# ============ Helpers BR ============
def money_br(v: float) -> str:
    try:
        return format_currency(v, 'BRL', locale='pt_BR')
    except Exception:
        s = f"{v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {s}"

def card(title: str, content: str, metrics: dict = None):
    """Renderiza um card personalizado"""
    st.markdown(f'''
        <div class="custom-card">
            <h3 style="margin:0;color:var(--text-dark)">{title}</h3>
            <p style="color:var(--text-light)">{content}</p>
            {_render_metrics(metrics) if metrics else ""}
        </div>
    ''', unsafe_allow_html=True)

def _render_metrics(metrics: dict) -> str:
    """Renderiza métricas dentro de um card"""
    if not metrics:
        return ""
    html = '<div style="display:flex;justify-content:space-between;margin-top:1rem">'
    for label, value in metrics.items():
        html += f'''
            <div>
                <p style="margin:0;color:var(--text-light);font-size:0.875rem">{label}</p>
                <p style="margin:0;color:var(--primary);font-weight:600">{value}</p>
            </div>
        '''
    html += '</div>'
    return html

def pill(text: str, kind: str = "success"):
    """Renderiza uma pill de status"""
    st.markdown(f'<span class="status-pill pill-{kind}">{text}</span>', unsafe_allow_html=True)

def date_br(d) -> str:
    try:
        return format_date(d, format='short', locale='pt_BR')
    except Exception:
        return d.strftime('%d/%m/%y')

def parse_money_br(s: str) -> float:
    if s is None: return 0.0
    s = s.strip().replace('.', '').replace(',', '.')
    try: return float(s)
    except Exception: return 0.0

# ============ App Config ============
st.set_page_config(
    page_title="DAVI",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': 'App DAVI - Controle Financeiro Inteligente'
    }
)

# Otimização de performance para mobile
st.markdown("""
    <style>
        /* Otimização de fonte e carregamento */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap&text=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789');
        
        /* Ajustes para mobile */
        @media (max-width: 640px) {
            .stApp {
                padding: 0.5rem !important;
            }
            
            /* Campos de texto e senha mais legíveis */
            input[type="text"], input[type="password"] {
                font-size: 16px !important;
                background-color: white !important;
                color: #111827 !important;
                -webkit-text-fill-color: #111827 !important;
                opacity: 1 !important;
                border: 1px solid #E5E7EB !important;
            }
            
            /* Melhorar toque em botões */
            button {
                min-height: 44px !important;
                margin: 0.25rem 0 !important;
            }
            
            /* Reduzir tamanho de elementos não essenciais */
            .stMarkdown p {
                margin-bottom: 0.5rem !important;
            }
            
            /* Otimizar tabelas */
            .stDataFrame {
                font-size: 14px !important;
            }
        }
        
        /* Melhorias gerais de performance */
        * {
            -webkit-font-smoothing: antialiased;
            box-sizing: border-box;
        }
        
        /* Desativar animações em conexões lentas */
        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
        }
    </style>
""", unsafe_allow_html=True)

def inject_styles():
    """Injeta estilos CSS personalizados e fonte Inter"""
    css_path = Path("styles.css")
    if css_path.exists():
        css_text = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)
    
    # Configurações adicionais de estilo
    st.markdown('''
        <style>
        /* Esconder menu hamburger e rodapé */
        #MainMenu, footer { visibility: hidden; }
        /* Remover padding extra */
        .main > div { padding-top: 1rem; }
        </style>
    ''', unsafe_allow_html=True)

inject_styles()

# ============ Session State Initialization ============
def init_session_state():
    # Verificar cookie de autenticação
    if "authenticated" not in st.session_state:
        saved_user = st.session_state.get("saved_user", None)
        if saved_user:
            st.session_state.authenticated = True
            st.session_state.user = saved_user
        else:
            st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "menu" not in st.session_state:
        st.session_state.menu = "Dashboard"
    if "confirmar_exclusao" not in st.session_state:
        st.session_state.confirmar_exclusao = {}
    if "confirmar_exclusao_balde" not in st.session_state:
        st.session_state.confirmar_exclusao_balde = {}
    if "confirmar_limpar" not in st.session_state:
        st.session_state.confirmar_limpar = False
    if "editing_balances" not in st.session_state:
        st.session_state.editing_balances = False
    if "editing_total" not in st.session_state:
        st.session_state.editing_total = False
        
def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.saved_user = None
    st.rerun()
    if "menu" not in st.session_state:
        st.session_state.menu = "Dashboard"
    if "confirmar_exclusao" not in st.session_state:
        st.session_state.confirmar_exclusao = {}
    if "confirmar_exclusao_balde" not in st.session_state:
        st.session_state.confirmar_exclusao_balde = {}
    if "confirmar_limpar" not in st.session_state:
        st.session_state.confirmar_limpar = False
    if "editing_balances" not in st.session_state:
        st.session_state.editing_balances = False
    if "editing_total" not in st.session_state:
        st.session_state.editing_total = False
    if "menu" not in st.session_state:
        st.session_state.menu = "Dashboard"
    if "confirmar_exclusao" not in st.session_state:
        st.session_state.confirmar_exclusao = {}
    if "confirmar_exclusao_balde" not in st.session_state:
        st.session_state.confirmar_exclusao_balde = {}
    if "confirmar_limpar" not in st.session_state:
        st.session_state.confirmar_limpar = False
    if "editing_balances" not in st.session_state:
        st.session_state.editing_balances = False
    if "editing_total" not in st.session_state:
        st.session_state.editing_total = False

# ============ DB bootstrap ============
def init_db():
    try:
        db_exists = os.path.exists("./sql_app.db")
        columns = set()
        
        # Criar banco de dados se não existir
        if not db_exists:
            Base.metadata.create_all(bind=engine)
            st.success("Banco de dados criado com sucesso!")
            return
        
        # Verificar e adicionar novas colunas
        with engine.connect() as conn:
            try:
                # Verificar se a tabela existe usando inspect (método moderno)
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                if 'giants' in tables:
                    columns = {col['name'] for col in inspector.get_columns('giants')}
                    needed_columns = {'weekly_goal', 'interest_rate', 'payoff_efficiency'}
                    missing_columns = needed_columns - columns
                    
                    # Adicionar colunas faltantes
                    for col in missing_columns:
                        try:
                            conn.execute(text(f"ALTER TABLE giants ADD COLUMN {col} FLOAT DEFAULT 0.0"))
                            st.success(f"Coluna {col} adicionada com sucesso!")
                        except Exception as col_error:
                            st.warning(f"Erro ao adicionar coluna {col}: {str(col_error)}")
                    
                    if missing_columns:
                        conn.commit()
                        st.success("Banco de dados atualizado com sucesso!")
                
            except Exception as table_error:
                st.error(f"Erro ao verificar tabelas: {str(table_error)}")
                try:
                    # Tentar recriar o banco em caso de erro grave
                    Base.metadata.create_all(bind=engine)
                    st.success("Banco de dados recriado com sucesso!")
                except Exception as recreate_error:
                    st.error(f"Erro ao recriar banco de dados: {str(recreate_error)}")
                    
    except Exception as e:
        st.error(f"Erro crítico na inicialização do banco: {str(e)}")
        raise

init_db()

def get_db() -> Session:
    return SessionLocal()

def get_or_create_user(db: Session, name: str) -> User:
    u = db.execute(select(User).where(User.name == name)).scalar_one_or_none()
    if u: return u
    u = User(name=name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

# ============ Data loaders ============
def load_buckets(db: Session, user_id: int):
    return db.execute(select(Bucket).where(Bucket.user_id == user_id)).scalars().all()

def load_giants(db: Session, user_id: int):
    return db.execute(select(Giant).where(Giant.user_id == user_id)).scalars().all()

def load_movements(db: Session, user_id: int):
    return db.execute(
        select(Movement).where(Movement.user_id == user_id).order_by(Movement.date.desc())
    ).scalars().all()

def load_bills(db: Session, user_id: int):
    return db.execute(
        select(Bill).where(Bill.user_id == user_id).order_by(Bill.due_date.asc())
    ).scalars().all()

def get_profile(db: Session, user_id: int) -> UserProfile:
    prof = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    if not prof:
        prof = UserProfile(user_id=user_id, monthly_income=0.0, monthly_expense=0.0)
        db.add(prof)
        db.commit()
        db.refresh(prof)
    return prof

def hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()

def auth_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.execute(select(User).where(User.name == username)).scalar_one_or_none()
    if user and user.password_hash == hash_password(password):
        return user
    return None

def create_user(db: Session, username: str, password: str) -> User:
    hashed_pwd = hash_password(password)
    user = User(name=username, password_hash=hashed_pwd)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@st.cache_data(ttl=300)
def load_cached_data(user_id: int):
    with get_db() as db:
        profile = get_profile(db, user_id)
        buckets = load_buckets(db, user_id)
        giants = load_giants(db, user_id)
        movements = load_movements(db, user_id)
        bills = load_bills(db, user_id)
        return profile, buckets, giants, movements, bills

@st.cache_resource
def get_cached_db():
    return SessionLocal()

def main():
    # Inicializar todas as variáveis de estado
    init_session_state()
    
    if not st.session_state.authenticated:
        # ==== Seção de Título e Slogan ====
        st.markdown("""
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@800;900&family=Poppins:wght@700;800;900&display=swap');
                
                [data-testid="stForm"] {
                    max-width: 400px;
                    margin: 0 auto;
                }
                .hero-section {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    margin: 1.5rem auto;
                    padding: 1.5rem;
                    max-width: 600px;
                    text-align: center;
                    animation: fadeIn 0.8s ease-out;
                }
                .brand-emoji {
                    font-size: 2.5em;
                    margin-bottom: 0.5rem;
                    opacity: 0.9;
                }
                .brand-title {
                    font-family: 'Poppins', sans-serif;
                    font-weight: 900;
                    font-size: 5em;
                    line-height: 1;
                    background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin: 0;
                    padding: 0;
                    letter-spacing: -0.02em;
                }
                .brand-slogan {
                    font-family: 'Inter', sans-serif;
                    font-weight: 600;
                    font-size: 1.1em;
                    color: #10B981;
                    margin: 0.75rem 0 0 0;
                    opacity: 0.9;
                    letter-spacing: -0.01em;
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes float {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-10px); }
                }
                @keyframes pulse {
                    0%, 100% { transform: scale(1); opacity: 0.5; }
                    50% { transform: scale(1.1); opacity: 0.7; }
                }
            </style>
            <div class="hero-section">
                <div class="brand-emoji">🎯</div>
                <h1 class="brand-title">DAVI</h1>
                <h3 class="brand-slogan">Vença seus gigantes financeiros</h3>
            </div>
        """, unsafe_allow_html=True)
        # ================================

        # Tabs de Login/Cadastro
        tab1, tab2 = st.tabs(["Login", "Cadastro"])
        
        with tab1:
            with st.form("login_form", clear_on_submit=True):
                st.markdown("""
                    <style>
                        input[type="text"], input[type="password"] {
                            padding: 0.75rem !important;
                            font-size: 16px !important;
                            background-color: white !important;
                            color: #111827 !important;
                            -webkit-text-fill-color: #111827 !important;
                            opacity: 1 !important;
                            border: 2px solid #E5E7EB !important;
                            border-radius: 0.5rem !important;
                            width: 100% !important;
                            margin-bottom: 1rem !important;
                        }
                        input[type="text"]:focus, input[type="password"]:focus {
                            border-color: #1E40AF !important;
                            box-shadow: 0 0 0 2px rgba(30, 64, 175, 0.2) !important;
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                username = st.text_input("Usuário", key="login_username")
                password = st.text_input("Senha", type="password", key="login_password")
                
                manter_login = st.checkbox("Manter conectado", key="manter_login")
                
                if st.form_submit_button("Entrar", use_container_width=True):
                    with get_db() as db:
                        user = auth_user(db, username, password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.user = user
                            if manter_login:
                                st.session_state.saved_user = user
                            st.rerun()
                        else:
                            st.error("Usuário ou senha inválidos")
        
        with tab2:
            with st.form("signup_form"):
                new_username = st.text_input("Novo Usuário")
                new_password = st.text_input("Nova Senha", type="password")
                confirm_password = st.text_input("Confirmar Senha", type="password")
                
                if st.form_submit_button("Cadastrar"):
                    if not new_username:
                        st.error("Preencha o nome de usuário")
                    else:
                        with get_db() as db:
                            existing_user = db.execute(
                                select(User).where(User.name == new_username)
                            ).scalar_one_or_none()
                            
                            if existing_user:
                                st.error("Usuário já existe")
                            else:
                                user = create_user(db, new_username, new_password)
                                st.success("Cadastro realizado com sucesso! Faça login para continuar.")
        
        st.stop()
    
    with get_db() as db:
        user = st.session_state.user
        
        # Carregar dados do usuário
        profile, buckets, giants, movements, bills = load_cached_data(user.id)
        
        # Calcular saldo disponível
        saldo = profile.monthly_income - profile.monthly_expense
        
        # Menu lateral com estilo personalizado
        # Adicionar botão de logout no topo direito
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("⨯", type="secondary", help="Sair", key="logout_btn"):
                logout()
                
        with st.sidebar:
            st.markdown('<h1 style="color: #1E40AF; font-size: 1.5rem; margin-bottom: 1rem;">☰ Menu</h1>', unsafe_allow_html=True)
            st.divider()
            
            menu_options = {
                "Dashboard": "📊 Dashboard",
                "Plano de Ataque": "🎯 Plano de Ataque",
                "Baldes": "🪣 Baldes",
                "Entrada e Saída": "💰 Entrada e Saída",
                "Livro Caixa": "📚 Livro Caixa",
                "Calendário": "📅 Calendário",
                "Atrasos & Riscos": "⚠️ Atrasos & Riscos",
                "Importar Extrato": "📥 Importar Extrato",
                "Configurações": "⚙️ Configurações"
            }
            
            if 'menu' not in st.session_state:
                st.session_state.menu = "Dashboard"
                
            st.markdown("""
                <style>
                    section[data-testid="stSidebar"] {
                        width: 300px !important;
                    }
                    section[data-testid="stSidebar"] .stButton button {
                        color: #1E40AF !important;
                        font-weight: 500 !important;
                        text-align: left !important;
                        padding: 0.5rem 1rem !important;
                        margin: 0.25rem 0 !important;
                        border-radius: 0.375rem !important;
                        width: 100% !important;
                    }
                    section[data-testid="stSidebar"] .stButton button:hover {
                        background-color: rgba(30, 64, 175, 0.08) !important;
                    }
                </style>
            """, unsafe_allow_html=True)
            
            if 'menu' not in st.session_state:
                st.session_state.menu = "Dashboard"
                
            # Menu único com chaves garantidamente únicas
            for label, value in menu_options.items():
                if st.sidebar.button(value, key=f"sidebar_menu_{label}", use_container_width=True):
                    st.session_state.menu = label
                    st.rerun()
            
            menu = st.session_state.menu
        
        # Dashboard
        if menu == "Dashboard":
            st.markdown('<h1 class="animate-slide-in">📊 Visão Geral</h1>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            
            # Calcular métricas com base nos movimentos
            total_receitas = sum(m.amount for m in movements if m.kind == "Receita")
            total_despesas = sum(m.amount for m in movements if m.kind == "Despesa")
            saldo_atual = total_receitas - total_despesas
            
            # Métricas principais com estilos personalizados
            st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "💰 Total Receitas",
                    money_br(total_receitas),
                    delta="Entradas",
                    delta_color="normal"
                )
            
            with col2:
                st.metric(
                    "💸 Total Despesas",
                    money_br(total_despesas),
                    delta="Saídas",
                    delta_color="inverse"
                )
            
            with col3:
                delta = saldo_atual - (profile.monthly_income - profile.monthly_expense)
                st.metric(
                    "📊 Saldo Atual",
                    money_br(saldo_atual),
                    delta=money_br(delta) if delta else None,
                    delta_color="normal" if saldo_atual >= 0 else "inverse"
                )
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Gráficos
            if movements:
                df = pd.DataFrame([
                    {
                        "data": m.date,
                        "valor": m.amount if m.kind == "Receita" else -m.amount,
                        "tipo": m.kind,
                        "descrição": m.description
                    }
                    for m in movements
                ]).sort_values("data")
                
                # Gráfico de linha - Evolução diária
                st.subheader("📈 Evolução de Movimentações")
                fig, ax = plt.subplots(figsize=(10, 4))
                
                df_receitas = df[df["tipo"] == "Receita"]
                df_despesas = df[df["tipo"] == "Despesa"]
                
                ax.plot(df_receitas["data"], df_receitas["valor"], 
                       color="green", label="Receitas", marker="o")
                ax.plot(df_despesas["data"], -df_despesas["valor"], 
                       color="red", label="Despesas", marker="o")
                
                ax.set_xlabel("Data")
                ax.set_ylabel("Valor (R$)")
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig)
                
                # Gráfico de área - Saldo acumulado
                st.subheader("📊 Saldo Acumulado")
                fig2, ax2 = plt.subplots(figsize=(10, 4))
                
                df["saldo_acumulado"] = df["valor"].cumsum()
                ax2.fill_between(df["data"], df["saldo_acumulado"], 
                               alpha=0.3, color="blue")
                ax2.plot(df["data"], df["saldo_acumulado"], 
                        color="blue", label="Saldo")
                
                ax2.set_xlabel("Data")
                ax2.set_ylabel("Saldo (R$)")
                ax2.legend()
                ax2.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig2)
                
                st.subheader("📝 Movimentações Recentes")
                st.dataframe(df.tail(10).sort_values("data", ascending=False))
        
        # Plano de Ataque
        elif menu == "Plano de Ataque":
            st.header("🎯 Plano de Ataque")
            
            # Lista de Giants existentes
            if giants:
                st.subheader("Gigantes Ativos")
                
                # Preparar dados para a tabela
                giant_data = []
                for giant in giants:
                    total_pago = sum(p.amount for p in db.query(GiantPayment).filter_by(giant_id=giant.id).all())
                    restante = giant.total_to_pay - total_pago
                    progresso = (total_pago / giant.total_to_pay) if giant.total_to_pay > 0 else 0
                    
                    ultima_semana = date.today() - timedelta(days=7)
                    aportes = db.query(GiantPayment).filter_by(giant_id=giant.id).all()
                    depositos_semana = sum(p.amount for p in aportes if p.date >= ultima_semana)
                    meta_atingida = depositos_semana >= giant.weekly_goal if giant.weekly_goal else False
                    
                    giant_data.append({
                        "ID": giant.id,
                        "Nome": giant.name,
                        "Total": giant.total_to_pay,
                        "Pago": total_pago,
                        "Restante": restante,
                        "Progresso": progresso,
                        "Meta Semanal": f"{money_br(depositos_semana)} / {money_br(giant.weekly_goal)}" if giant.weekly_goal else "-",
                        "Status": "✅" if progresso >= 0.95 else "⏳",
                        "Taxa": f"{giant.interest_rate:.1f}%" if giant.interest_rate else "-"
                    })
                
                # Criar DataFrame e formatar valores monetários antes
                df_giants = pd.DataFrame(giant_data)
                df_giants["Total"] = df_giants["Total"].apply(money_br)
                df_giants["Pago"] = df_giants["Pago"].apply(money_br)
                df_giants["Restante"] = df_giants["Restante"].apply(money_br)
                
                # Configurar colunas da tabela
                st.dataframe(
                    df_giants,
                    column_config={
                        "ID": "ID",
                        "Nome": "Nome",
                        "Total": "Total",
                        "Pago": "Pago",
                        "Restante": "Restante",
                        "Progresso": st.column_config.ProgressColumn(
                            "Progresso",
                            help="Progresso do pagamento",
                            format="%.0f%%",
                            min_value=0,
                            max_value=1
                        ),
                        "Meta Semanal": "Meta Semanal",
                        "Status": "Status",
                        "Taxa": "Taxa Mensal"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Botão de excluir
                selected_giant = st.selectbox("Selecione um gigante para excluir:", options=df_giants["Nome"].tolist(), key="select_giant_delete")
                if selected_giant:
                    giant_id = df_giants[df_giants["Nome"] == selected_giant]["ID"].iloc[0]
                    if st.button("🗑️ Excluir Gigante", key=f"del_giant_{giant_id}", type="secondary"):
                        st.session_state.confirmar_exclusao[giant_id] = True
                    
                    if st.session_state.confirmar_exclusao.get(giant.id):
                        col_confirm1, col_confirm2 = st.columns(2)
                        with col_confirm1:
                            if st.button("✅ Confirmar", key=f"confirm_yes_{giant.id}"):
                                try:
                                    # Primeiro excluir os pagamentos
                                    db.query(GiantPayment).filter_by(giant_id=giant.id).delete()
                                    # Depois excluir o gigante
                                    db.delete(giant)
                                    db.commit()
                                    st.success("Gigante excluído com sucesso!")
                                    # Limpar o estado de confirmação
                                    del st.session_state.confirmar_exclusao[giant.id]
                                    time.sleep(0.5)  # Pequena pausa para garantir que a UI atualize
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {str(e)}")
                                    db.rollback()
                        with col_confirm2:
                            if st.button("❌ Cancelar", key=f"confirm_no_{giant.id}"):
                                del st.session_state.confirmar_exclusao[giant.id]
                                st.rerun()
                    
                    # Form para aporte
                    with st.form(f"aporte_giant_{giant.id}"):
                        ap_col1, ap_col2, ap_col3 = st.columns([2,2,1])
                        with ap_col1:
                            valor_aporte = st.number_input("Valor", min_value=0.0, step=100.0)
                        with ap_col2:
                            obs_aporte = st.text_input("Observação")
                        with ap_col3:
                            data_aporte = st.date_input("Data", value=date.today())
                        
                        if st.form_submit_button("💰 Registrar Aporte"):
                            if valor_aporte > 0:
                                aporte = GiantPayment(
                                    user_id=user.id,
                                    giant_id=giant.id,
                                    amount=valor_aporte,
                                    date=data_aporte,
                                    note=obs_aporte
                                )
                                db.add(aporte)
                                if total_pago + valor_aporte >= giant.total_to_pay:
                                    giant.status = "defeated"
                                    st.balloons()
                                db.commit()
                                st.success("Aporte registrado!")
                                st.rerun()
                            else:
                                st.error("Informe um valor maior que zero")
                    
                    # Histórico resumido
                    aportes = db.query(GiantPayment).filter_by(giant_id=giant.id).order_by(GiantPayment.date.desc()).limit(3).all()
                    if aportes:
                        st.caption("Últimos aportes:")
                        for aporte in aportes:
                            st.text(f"- {date_br(aporte.date)}: {money_br(aporte.amount)}")
                    
                    st.divider()
            
            st.markdown("### ➕ Novo Gigante")
            # Form para criar novo Giant
            with st.form("novo_giant"):
                col1, col2 = st.columns(2)
                with col1:
                    nome_giant = st.text_input("Nome do Gigante", placeholder="Ex: Cartão Nubank")
                    valor_total = st.number_input("Valor Total a Quitar", min_value=0.0, step=100.0)
                    deposito_semanal = st.number_input("Meta de Depósito Semanal", min_value=0.0, step=50.0)
                with col2:
                    parcelas = st.number_input("Número de Parcelas", min_value=0, step=1)
                    prioridade = st.number_input("Prioridade (1 = maior)", min_value=1, step=1)
                    taxa_juros = st.number_input("Taxa de Juros Mensal (%)", min_value=0.0, step=0.1, format="%.2f")
                
                if st.form_submit_button("Criar Gigante"):
                    if nome_giant and valor_total > 0:
                        # Calcular Payoff Efficiency (R$/1k)
                        montante_final = valor_total * (1 + taxa_juros/100) ** parcelas
                        payoff_efficiency = (montante_final - valor_total) / (valor_total/1000)
                        
                        giant = Giant(
                            user_id=user.id,
                            name=nome_giant,
                            total_to_pay=valor_total,
                            parcels=parcelas,
                            priority=prioridade,
                            status="active",
                            weekly_goal=deposito_semanal,
                            interest_rate=taxa_juros,
                            payoff_efficiency=payoff_efficiency
                        )
                        db.add(giant)
                        db.commit()
                        st.success("Gigante criado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Preencha o nome e valor do Giant")
            
            st.divider()
        
        # Baldes
        elif menu == "Baldes":
            st.header("🪣 Baldes")
            
            # Form para criar novo balde no topo
            st.markdown("### ➕ Novo Balde")
            with st.form("novo_balde"):
                col1, col2 = st.columns(2)
                with col1:
                    nome = st.text_input("Nome do Balde", placeholder="Ex: C6")
                    tipo = st.text_input("Tipo do Balde", placeholder="Ex: Dízimo")
                with col2:
                    prioridade = st.number_input("Prioridade", min_value=1, step=1)
                    perc = st.number_input("Porcentagem (%)", min_value=0, max_value=100, step=1)
                
                if st.form_submit_button("Criar Balde"):
                    if nome and tipo:
                        bucket = Bucket(
                            user_id=user.id,
                            name=f"{nome} - {tipo}",
                            description=f"Prioridade: {prioridade}",
                            percent=float(perc),
                            type=tipo.lower()
                        )
                        db.add(bucket)
                        db.commit()
                        st.success(f"Balde criado: {nome} - {tipo} - {perc}%")
                        st.rerun()
                    else:
                        st.error("Preencha o nome e tipo do balde")
            
            st.markdown("<hr style='margin: 1.5rem 0'>", unsafe_allow_html=True)
            
            if buckets:
                if "confirmar_exclusao_balde" not in st.session_state:
                    st.session_state.confirmar_exclusao_balde = {}
                
                # Mostrar baldes com opção de exclusão
                for bucket in buckets:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.metric(
                            f"{bucket.name} ({bucket.percent}%)", 
                            money_br(bucket.balance),
                            help=f"Prioridade: {bucket.description}"
                        )
                    with col2:
                        if st.button("⨯", key=f"del_bucket_{bucket.id}", type="secondary", help="Excluir"):
                            st.session_state.confirmar_exclusao_balde[bucket.id] = True
                        
                        if st.session_state.confirmar_exclusao_balde.get(bucket.id):
                            st.warning("Tem certeza que deseja excluir este Balde?")
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("✅ Sim", key=f"confirm_bucket_yes_{bucket.id}"):
                                    db.delete(bucket)
                                    db.commit()
                                    st.success("Balde excluído com sucesso!")
                                    st.session_state.confirmar_exclusao_balde[bucket.id] = False
                                    st.rerun()
                            with col_b:
                                if st.button("❌ Não", key=f"confirm_bucket_no_{bucket.id}"):
                                    st.session_state.confirmar_exclusao_balde[bucket.id] = False
                                    st.rerun()
                    st.markdown("<hr style='margin: 0.5rem 0'>", unsafe_allow_html=True)
        
        # Entrada e Saída
        elif menu == "Entrada e Saída":
            st.header("� Entrada e Saída")
            
            # Mostrar saldo atual dos baldes
            if buckets:
                st.subheader("📊 Saldo dos Baldes")
                total_baldes = sum(b.balance for b in buckets)
                
                # Botão para editar saldos
                col_total, col_edit, col_edit_total, col_space = st.columns([1, 0.5, 0.5, 1.5])
                with col_total:
                    st.metric("Saldo Total", money_br(total_baldes))
                with col_edit:
                    if st.button("✏️ Editar Baldes", key="edit_balances"):
                        st.session_state["editing_balances"] = True
                with col_edit_total:
                    if st.button("💰 Editar Total", key="edit_total"):
                        st.session_state["editing_total"] = True
                
                # Form para editar saldo total
                if st.session_state.get("editing_total", False):
                    with st.form("editar_total"):
                        novo_total = st.number_input("Novo Saldo Total", value=float(total_baldes), step=100.0, format="%.2f")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Salvar"):
                                if novo_total >= 0:
                                    # Distribuir proporcionalmente pelos baldes
                                    total_percent = sum(b.percent for b in buckets)
                                    for bucket in buckets:
                                        perc_norm = (bucket.percent / total_percent) if total_percent > 0 else 0
                                        bucket.balance = novo_total * perc_norm
                                    db.commit()
                                    st.success("Saldo total ajustado e distribuído!")
                                    st.session_state["editing_total"] = False
                                    st.rerun()
                                else:
                                    st.error("O saldo total não pode ser negativo")
                        with col2:
                            if st.form_submit_button("❌ Cancelar"):
                                st.session_state["editing_total"] = False
                                st.rerun()
                
                # Form para editar saldos
                if st.session_state.get("editing_balances", False):
                    with st.form("editar_saldos"):
                        st.write("Ajustar saldos dos baldes:")
                        new_balances = {}
                        cols = st.columns(3)
                        for idx, bucket in enumerate(buckets):
                            with cols[idx % 3]:
                                new_value = st.number_input(
                                    f"Saldo {bucket.name}",
                                    value=float(bucket.balance),
                                    step=10.0,
                                    format="%.2f"
                                )
                                new_balances[bucket.id] = new_value
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Salvar"):
                                for bucket in buckets:
                                    bucket.balance = new_balances[bucket.id]
                                db.commit()
                                st.session_state["editing_balances"] = False
                                st.success("Saldos atualizados!")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("❌ Cancelar"):
                                st.session_state["editing_balances"] = False
                                st.rerun()
                
                cols = st.columns(3)
                for idx, bucket in enumerate(buckets):
                    with cols[idx % 3]:
                        st.metric(
                            f"{bucket.name} ({bucket.percent}%)", 
                            money_br(bucket.balance),
                            help=f"Prioridade: {bucket.description}"
                        )
            
            st.divider()
            
            with st.form("nova_entrada"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    tipo = st.selectbox("Tipo", ["Entrada", "Saída", "Retirada"])
                    valor = st.number_input("Valor", min_value=0.0, step=10.0)
                    desc = st.text_input("Descrição")
                with col2:
                    data_mov = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
                
                # Se for despesa, seleciona o balde
                if tipo == "Despesa":
                    bucket_id = st.selectbox(
                        "Balde",
                        options=[b.id for b in buckets],
                        format_func=lambda x: next(b.name for b in buckets if b.id == x)
                    ) if buckets else None
                
                if st.form_submit_button("Registrar"):
                    if tipo == "Entrada":
                        # Calcular distribuição pelos baldes
                        total_percent = sum(b.percent for b in buckets)
                        if total_percent > 0:
                            for bucket in buckets:
                                # Calcular valor proporcional para este balde
                                perc_normalizado = (bucket.percent / total_percent) * 100
                                valor_balde = (valor * perc_normalizado) / 100
                                
                                # Criar movimento para este balde
                                mov = Movement(
                                    user_id=user.id,
                                    bucket_id=bucket.id,
                                    kind="Receita",
                                    amount=valor_balde,
                                    description=f"{desc} (Distribuição: {perc_normalizado:.1f}%)",
                                    date=data_mov
                                )
                                db.add(mov)
                                
                                # Atualizar saldo do balde
                                bucket.balance += valor_balde
                            
                            db.commit()
                            
                            # Mostrar detalhes da distribuição
                            st.success(f"Receita de {money_br(valor)} distribuída entre os baldes!")
                            st.write("📊 Distribuição realizada:")
                            cols_dist = st.columns(3)
                            for idx, bucket in enumerate(buckets):
                                with cols_dist[idx % 3]:
                                    perc_norm = (bucket.percent / total_percent) * 100
                                    valor_dist = (valor * perc_norm) / 100
                                    st.metric(
                                        f"{bucket.name}",
                                        money_br(valor_dist),
                                        f"{perc_norm:.1f}%"
                                    )
                            st.rerun()
                    else:  # Saída ou Retirada
                        if bucket_id:
                            bucket = next((b for b in buckets if b.id == bucket_id), None)
                            if bucket and bucket.balance >= valor:
                                mov = Movement(
                                    user_id=user.id,
                                    bucket_id=bucket_id,
                                    kind="Despesa",
                                    amount=valor,
                                    description=f"{desc} ({tipo})",
                                    date=data_mov
                                )
                                db.add(mov)
                                
                                # Atualizar saldo do balde
                                if tipo == "Retirada":
                                    bucket.balance -= valor
                                    msg = f"Retirada de {money_br(valor)} registrada em {date_br(data_mov)}! Novo saldo do balde {bucket.name}: {money_br(bucket.balance)}"
                                else:
                                    bucket.balance -= valor
                                    msg = f"Saída de {money_br(valor)} registrada em {date_br(data_mov)}! Novo saldo do balde {bucket.name}: {money_br(bucket.balance)}"
                                
                                db.commit()
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(f"Saldo insuficiente no balde {bucket.name if bucket else ''}")
                        else:
                            st.error("Selecione um balde para a operação")
        
        # Livro Caixa
        elif menu == "Livro Caixa":
            st.header("📚 Livro Caixa")
            
            # Botões de ação no topo
            col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
            with col1:
                if st.button("🧹 Limpar Tudo"):
                    if movements:
                        st.session_state["confirmar_limpar"] = True
            with col2:
                if movements:
                    csv = pd.DataFrame([
                        {
                            "Data": m.date,
                            "Descrição": m.description,
                            "Tipo": m.kind,
                            "Valor": m.amount if m.kind == "Receita" else -m.amount,
                            "Balde": next((b.name for b in buckets if b.id == m.bucket_id), None)
                        }
                        for m in movements
                    ]).to_csv(index=False, sep=';').encode('utf-8')
                    
                    st.download_button(
                        "📥 Exportar CSV",
                        csv,
                        "extrato.csv",
                        "text/csv",
                        key="download-csv"
                    )
            
            # Confirmação para limpar
            if st.session_state.get("confirmar_limpar", False):
                st.warning("⚠️ Tem certeza que deseja limpar todo o histórico?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Sim"):
                        with get_db() as db:
                            db.query(Movement).filter_by(user_id=user.id).delete()
                            db.commit()
                            st.success("Histórico limpo com sucesso!")
                            st.session_state["confirmar_limpar"] = False
                            time.sleep(1)
                            st.rerun()
                with col2:
                    if st.button("❌ Não"):
                        st.session_state["confirmar_limpar"] = False
                        st.rerun()
            
            if movements:
                # Mostrar totais
                total_receitas = sum(m.amount for m in movements if m.kind == "Receita")
                total_despesas = sum(m.amount for m in movements if m.kind == "Despesa")
                saldo = total_receitas - total_despesas
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("💰 Total Receitas", money_br(total_receitas))
                with col2:
                    st.metric("💸 Total Despesas", money_br(total_despesas))
                with col3:
                    st.metric("📊 Saldo", money_br(saldo), 
                             delta=money_br(saldo),
                             delta_color="normal" if saldo >= 0 else "inverse")
                
                st.divider()
                
                # Tabela de movimentações
                st.subheader("📝 Histórico de Movimentações")
                df = pd.DataFrame([
                    {
                        "Data": date_br(m.date),
                        "Descrição": m.description,
                        "Tipo": "➕ Receita" if m.kind == "Receita" else "➖ Despesa",
                        "Valor": money_br(m.amount if m.kind == "Receita" else -m.amount),
                        "Balde": next((b.name for b in buckets if b.id == m.bucket_id), None),
                        "ID": m.id
                    }
                    for m in movements
                ]).sort_values("Data", ascending=False)
                
                # Criar tabela unificada e organizada
                df_styled = df.copy()
                df_styled["Ações"] = df_styled["ID"].apply(lambda x: "🗑️")
                
                # Reordenar e renomear colunas
                df_styled = df_styled[["Data", "Descrição", "Tipo", "Valor", "Balde", "Ações"]]
                
                # Aplicar estilos condicionais
                def highlight_row(row):
                    color = "#10B98120" if "Receita" in row["Tipo"] else "#EF444420"
                    return [f"background-color: {color}" for _ in range(len(row))]
                
                # Mostrar tabela estilizada
                st.dataframe(
                    df_styled,
                    column_config={
                        "Data": st.column_config.TextColumn(
                            "Data",
                            width="small",
                        ),
                        "Descrição": st.column_config.TextColumn(
                            "Descrição",
                            width="medium",
                        ),
                        "Tipo": st.column_config.TextColumn(
                            "Tipo",
                            width="small",
                        ),
                        "Valor": st.column_config.TextColumn(
                            "Valor",
                            width="small",
                        ),
                        "Balde": st.column_config.TextColumn(
                            "Balde",
                            width="small",
                        ),
                        "Ações": st.column_config.Column(
                            "Ações",
                            width="small",
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                )
                
                # Handler para exclusão
                clicked = st.button("Excluir Selecionado", type="secondary")
                if clicked:
                    with get_db() as db:
                        selected_rows = st.session_state.get("selected_rows", [])
                        for row_index in selected_rows:
                            mov_id = df.iloc[row_index]["ID"]
                            mov = db.query(Movement).get(mov_id)
                            if mov:
                                db.delete(mov)
                        db.commit()
                        st.success("Movimentações selecionadas excluídas!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.info("Nenhuma movimentação registrada ainda.")
        
        # Calendário
        elif menu == "Calendário":
            st.header("📅 Calendário")
            
            # Form para adicionar nova conta
            st.markdown("### ➕ Nova Conta")
            with st.form("nova_conta"):
                col1, col2 = st.columns(2)
                with col1:
                    descricao = st.text_input("Descrição da Conta")
                    valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")
                with col2:
                    data_venc = st.date_input("Data de Vencimento", value=date.today(), format="DD/MM/YYYY")
                    is_important = st.checkbox("Conta Importante (Cartão/Empréstimo)")
                    
                if st.form_submit_button("Adicionar Conta"):
                        if not descricao.strip():
                            st.error("Preencha a descrição da conta")
                        elif valor <= 0:
                            st.error("O valor deve ser maior que zero")
                        else:
                            bill = Bill(
                                user_id=user.id,
                                title=descricao,
                                amount=valor,
                                due_date=data_venc,
                                is_critical=is_important,
                                paid=False
                            )
                            db.add(bill)
                            db.commit()
                            st.success(f"Conta {descricao} adicionada para {date_br(data_venc)}")
                            st.rerun()
            
            if bills:
                # Criar DataFrame para o calendário
                # Mostrar alertas de vencimentos próximos
                amanha = date.today() + timedelta(days=1)
                contas_amanha = [b for b in bills if b.due_date == amanha]
                if contas_amanha:
                    st.warning("⚠️ Contas que vencem amanhã:")
                    for conta in contas_amanha:
                        importance_mark = "🔴" if conta.is_critical else "⚪"
                        st.warning(f"{importance_mark} {conta.title}: {money_br(conta.amount)}")
                
                # DataFrame de todas as contas
                df_bills = pd.DataFrame([
                    {
                        "Data": b.due_date,
                        "Descrição": f"{'🔴' if b.is_critical else '⚪'} {b.title}",
                        "Valor": b.amount,
                        "Status": "✅ Pago" if b.paid else "❌ Pendente",
                        "ID": b.id
                    }
                    for b in bills
                ])
                
                # Exibir calendário
                st.subheader("Próximos Vencimentos")
                
                # Adicionar opção de marcar como pago e excluir
                for index, row in df_bills.iterrows():
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 0.3, 0.3])
                    with col1:
                        st.write(f"{row['Descrição']}")
                    with col2:
                        st.write(money_br(row['Valor']))
                    with col3:
                        st.write(date_br(row['Data']))
                    with col4:
                        if row['Status'] == "❌ Pendente":
                            if st.button("✅", key=f"pay_bill_{row['ID']}"):
                                bill = db.query(Bill).get(row['ID'])
                                if bill:
                                    bill.paid = True
                                    db.commit()
                                    st.success("Conta marcada como paga!")
                                    st.rerun()
                        else:
                            st.write("✓")
                    with col5:
                        if st.button("⨯", key=f"del_bill_{row['ID']}", type="secondary", help="Excluir"):
                            bill = db.query(Bill).get(row['ID'])
                            if bill:
                                db.delete(bill)
                                db.commit()
                                st.success("Conta excluída!")
                                st.rerun()
                
                # Sumário de valores
                st.subheader("Total de Contas")
                total = df_bills["Valor"].sum()
                total_pendente = df_bills[df_bills["Status"] == "❌ Pendente"]["Valor"].sum()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total", money_br(total))
                with col2:
                    st.metric("Pendente", money_br(total_pendente))
        
        # Atrasos & Riscos
        elif menu == "Atrasos & Riscos":
            st.header("⚠️ Atrasos & Riscos")
            
            if bills:
                # Filtrar contas atrasadas
                hoje = date.today()
                df_atrasadas = pd.DataFrame([
                    {
                        "Descrição": b.title,
                        "Valor": b.amount,
                        "Vencimento": b.due_date,
                        "Status": "Atrasada"
                    }
                    for b in bills if b.due_date < hoje
                ])
                
                if not df_atrasadas.empty:
                    st.subheader("Contas Atrasadas")
                    st.dataframe(df_atrasadas)
                else:
                    st.success("Nenhuma conta atrasada!")
                
                # Risco de Atraso
                st.subheader("Risco de Atraso")
                df_risco = pd.DataFrame([
                    {
                        "Descrição": b.title,
                        "Valor": b.amount,
                        "Vencimento": b.due_date,
                        "Dias para Vencimento": (b.due_date - hoje).days,
                        "Status": "Em Risco"
                    }
                    for b in bills if 0 <= (b.due_date - hoje).days <= 7
                ])
                
                if not df_risco.empty:
                    st.dataframe(df_risco)
                else:
                    st.success("Nenhum risco de atraso identificado!")
        
        # Importar Extrato
        elif menu == "Importar Extrato":
            st.header("📥 Importar Extrato")
            
            uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
            if uploaded_file is not None:
                # Ler o arquivo CSV
                df_import = pd.read_csv(uploaded_file, sep=';')
                
                # Validar colunas
                required_columns = {"Data", "Descrição", "Tipo", "Valor", "Balde"}
                if not required_columns.issubset(df_import.columns):
                    st.error("O arquivo CSV deve conter as colunas: " + ", ".join(required_columns))
                else:
                    # Inserir dados no banco
                    for _, row in df_import.iterrows():
                        mov = Movement(
                            user_id=user.id,
                            date=row["Data"],
                            description=row["Descrição"],
                            kind=row["Tipo"],
                            amount=row["Valor"],
                            bucket_id=row["Balde"]
                        )
                        db.add(mov)
                    db.commit()
                    st.success("Extrato importado com sucesso!")
                    st.rerun()
        
        # Configurações
        elif menu == "Configurações":
            st.header("⚙️ Configurações")
            
            # Form para editar perfil
            with st.form("editar_perfil"):
                st.subheader("Perfil")
                renda_mensal = st.number_input("Renda Mensal", value=profile.monthly_income, min_value=0.0, step=100.0)
                despesa_mensal = st.number_input("Despesa Mensal", value=profile.monthly_expense, min_value=0.0, step=100.0)
                
                if st.form_submit_button("Salvar"):
                    profile.monthly_income = renda_mensal
                    profile.monthly_expense = despesa_mensal
                    db.commit()
                    st.success("Perfil atualizado com sucesso!")
                    st.rerun()
        
        # Outras seções
        else:
            st.info("Seção em desenvolvimento!")

if __name__ == "__main__":
    main()

