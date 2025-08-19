# ==== IMPORTS INICIAIS (SEM DUPLICATAS) ====
import os, sys, time, math, io, hashlib
from pathlib import Path
from datetime import date, datetime, timedelta
from contextlib import contextmanager

# --- Bibliotecas externas ---
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ==== HELPER FUNCTIONS ====
def format_currency(value, format_str="R$ {:.2f}"):
    """Format a number as currency"""
    return format_str.format(abs(value)).replace(".", ",")

def money_br(value):
    """Format a number as Brazilian currency"""
    return format_currency(value)

def create_bucket(db, user, name, tipo, description, percent):
    """Create a new bucket"""
    bucket = Bucket(
        user_id=user.id,
        name=name,
        description=description,
        percent=float(percent),
        type=tipo.lower()
    )
    db.add(bucket)
    db.commit()
    return bucket
from babel.numbers import format_currency
from babel.dates import format_date

# --- DB robusto: importa local e como pacote (Cloud) ---
try:
    from db import engine, SessionLocal, Base
except (ImportError, ModuleNotFoundError):
    from .db import engine, SessionLocal, Base  # fallback quando rodar como pacote

from sqlalchemy.orm import Session
from sqlalchemy import select, text, inspect

# --- Serviços/UI já existentes no projeto (mantidos) ---
from services.giants import delete_giant
from services.movements import create_income
from services.buckets import split_income_by_buckets
from ui import inject_mobile_ui, hamburger, bottom_nav
from models import (
    User, Bucket, Giant, Movement, Bill,
    UserProfile, GiantPayment
)
from ui_utils import (
    mobile_friendly_button,
    mobile_friendly_table,
    show_confirmation_dialog,
    show_action_buttons
)
from utils import money_br, date_br
from giant_manager import render_plano_ataque, get_giant_payments, get_total_paid
from db_helpers import (
    tx, init_db_pragmas, delete_giant, distribuir_por_baldes,
    giant_forecast, check_giant_victory
)
from app_utils import (
    safe_dataframe, dias_do_mes, ensure_daily_allocation,
    daily_budget_for_giants, celebrate_victory
)

# ==== CONFIGURAÇÃO DE PÁGINA (ALINHADA À ESQUERDA, FORA DE FUNÇÕES) ====
st.set_page_config(
    page_title="App DAVI",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'About': 'App DAVI - Controle Financeiro Inteligente'}
)

# --- configuração da UI mobile ---
inject_mobile_ui()
hamburger()

from contextlib import contextmanager

@st.cache_resource
def _session_factory():
    return SessionLocal  # classe de sessão

@contextmanager
def get_db():
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()

def show_giants_table(df: pd.DataFrame):
    # tipagem segura
    for col in ("ID", "total", "paid", "remaining"):
        if col in df.columns:
            if col == "ID":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", format="%d", width="small"),
            "name": st.column_config.TextColumn("Nome"),
            "total": st.column_config.NumberColumn("Total", format="R$ %,.2f"),
            "paid": st.column_config.NumberColumn("Pago", format="R$ %,.2f"),
            "remaining": st.column_config.NumberColumn("Restante", format="R$ %,.2f"),
        },
    )

def load_user_data(db: Session, user_id: int) -> dict:
    """Carrega todos os dados do usuário."""
    try:
        # Carrega dados do usuário
        profile = db.get(User, user_id)
        if not profile:
            raise Exception("Usuário não encontrado")

        # Carrega configurações e dados associados
        buckets = load_user_buckets(user_id) 
        giants = load_user_giants(user_id)
        movements, total = load_user_movements(user_id)
        bills = load_user_bills(user_id)

        return {
            'profile': profile,
            'buckets': buckets,
            'giants': giants, 
            'movements': movements,
            'total': total,
            'bills': bills
        }

    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return None

# --- Login e autenticação ---
def init_auth():
    """Inicializa o sistema de autenticação."""
    if "user" not in st.session_state:
        st.session_state.user = None
        
    if "login_error" not in st.session_state:
        st.session_state.login_error = None

def auth_required(func):
    """Decorator para garantir que o usuário está autenticado."""
    def wrapper(*args, **kwargs):
        init_auth()
        if not st.session_state.user:
            show_login()
            return
        return func(*args, **kwargs)
    return wrapper

def logout():
    """Faz logout do usuário."""
    if "user" in st.session_state:
        del st.session_state.user
    if "user_data" in st.session_state:
        del st.session_state.user_data
    st.rerun()

def show_login():
    """Exibe o formulário de login."""
    inject_mobile_ui()
    
    # Adiciona menu hamburguer para mobile
    hamburger()
    
    with st.form("login_form", clear_on_submit=True):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        col1, col2 = st.columns([3,1])
        with col1:
            submitted = st.form_submit_button("Login")
        with col2:
            st.markdown("*Contate o admin*")
            
        if submitted:
            try:
                db = get_db()
                user = auth_user(db, username, password)
                if user:
                    st.session_state.user = user.id
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos")
            except Exception as e:
                st.error(f"Erro ao fazer login: {str(e)}")

# Importar funções otimizadas
from utils import money_br, date_br
from giant_manager import render_plano_ataque, get_giant_payments, get_total_paid
from db_helpers import (tx, init_db_pragmas, delete_giant, distribuir_por_baldes, 
                       giant_forecast, check_giant_victory)
from app_utils import (safe_dataframe, dias_do_mes, ensure_daily_allocation, 
                      daily_budget_for_giants, celebrate_victory)

# Mobile first & UI improvements
st.markdown("""
<style>
div.block-container{max-width:900px;padding:0.5rem 1rem;}
@media (max-width:480px){
  div.block-container{padding:0.25rem 0.5rem;}
  .stTextInput input,.stNumberInput input,.stDateInput input{height:44px;font-size:16px;}
  .stButton button{height:44px}
}
.stCheckbox > label{display:flex;gap:.5rem;align-items:center;white-space:nowrap;}
.header-bar{display:flex;align-items:center;gap:.5rem;margin:.5rem 0 1rem;}
.burger{font-size:24px;line-height:24px;padding:.25rem .5rem;border-radius:8px;border:1px solid #1f293733;}
.brand{color:#1E40AF;font-weight:800;letter-spacing:.5px;}
.slogan{color:#10B981;opacity:.9;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-bar">
  <span class="burger">☰</span>
  <div>
    <div class="brand">DAVI</div>
    <div class="slogan">Vença seus gigantes financeiros</div>
  </div>
</div>
""", unsafe_allow_html=True)

# Cache functions to improve performance
@st.cache_data(ttl=300)
def get_giant_payments(giant_id):
    with get_db() as db:
        return db.query(GiantPayment).filter_by(giant_id=giant_id).all()

@st.cache_data(ttl=300)
def get_total_paid(giant_id):
    payments = get_giant_payments(giant_id)
    return sum(p.amount for p in payments)

# Função segura para operações no banco de dados
def safe_operation(operation_func):
    try:
        with get_db() as db:
            result = operation_func(db)
            return result
    except Exception as e:
        st.error(f"Erro na operação: {str(e)}")
        return False

# Performance Optimizations
st.markdown("""
<style>
    /* Performance Optimizations */
    * {
        -webkit-font-smoothing: antialiased;
        text-rendering: optimizeLegibility;
        box-sizing: border-box;
    }

    /* Reduce Repaints */
    .stApp {
        transform: translateZ(0);
        backface-visibility: hidden;
        perspective: 1000px;
    }

    /* Form Input Styles */
    div[data-testid="stTextInput"] {
        width: 100% !important;
        max-width: 400px !important;
        margin: 0 auto !important;
    }
    
    div[data-testid="stForm"] {
        max-width: 400px !important;
        margin: 0 auto !important;
        padding: 1rem !important;
    }

    /* Mobile Optimizations */
    [data-testid="stSidebar"] {
        min-width: unset !important;
        width: auto !important;
        flex-shrink: 0 !important;
        will-change: transform;
    }

    /* Optimize touch interactions */
    button, [role="button"], a {
        touch-action: manipulation;
        -webkit-tap-highlight-color: transparent;
    }

    /* Responsive layout */
    @media (max-width: 640px) {
        .main { padding: 0.5rem !important; }
        .stApp { overflow: auto !important; }
        div[data-testid="stForm"] { padding: 0.5rem !important; }
        div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
        
        /* Optimize scrolling */
        .main > div:first-child {
            overflow-x: hidden;
            -webkit-overflow-scrolling: touch;
        }

        /* Optimize tables for mobile */
        [data-testid="stDataFrame"] {
            width: 100%;
            max-width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            background:
                linear-gradient(to right, white 30%, rgba(255,255,255,0)),
                linear-gradient(to right, rgba(255,255,255,0), white 70%) 100% 0,
                radial-gradient(farthest-side at 0% 50%, rgba(0,0,0,.2), rgba(0,0,0,0)),
                radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.2), rgba(0,0,0,0)) 100% 0;
            background-repeat: no-repeat;
            background-size: 40px 100%, 40px 100%, 14px 100%, 14px 100%;
            background-attachment: local, local, scroll, scroll;
        }

        /* Optimize forms */
        input, select, textarea {
            font-size: 16px !important; /* Prevent zoom on iOS */
        }
    }

    /* Reduce layout shifts */
    [data-testid="stMetricValue"] {
        min-height: 1.5em;
    }

    /* Hide decorations */
    [data-testid="stDecoration"],
    footer,
    #MainMenu { 
        display: none !important;
    }

    /* Optimize data editor */
    [data-testid="stDataEditor"] {
        max-height: 70vh;
        overflow: auto;
    }
</style>
""", unsafe_allow_html=True)
from database import (
    engine, get_db, safe_operation,
    batch_operation, retry_operation
)
from models import Base
from models import (
    User, Bucket, Giant, Movement, Bill,
    UserProfile, GiantPayment
)
from babel.numbers import format_currency
from babel.dates import format_date
import matplotlib.pyplot as plt
from ui_utils import (
    mobile_friendly_button,
    mobile_friendly_table,
    show_confirmation_dialog,
    show_action_buttons
)

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
    'figure.autolayout': True,
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 14
})

# Otimizações de CSS global para formulários
st.markdown("""
<style>
    /* Reset de formulário */
    div[data-testid="stForm"] {
        width: 100% !important;
        max-width: 420px !important;
        margin: 0 auto !important;
        padding: 0 !important;
    }

    /* Container de input consistente */
    .stTextInput, 
    div[data-baseweb="input"],
    div[data-baseweb="base-input"] {
        margin: 0 0 1rem 0 !important;
    }

    /* Altura consistente para inputs */
    .stTextInput > div > div > input,
    .stTextInput input,
    div[data-baseweb="input"] div,
    div[data-baseweb="base-input"] div,
    [data-testid="stFormSubmitButton"] button {
        box-sizing: border-box !important;
        height: 44px !important;
        min-height: 44px !important;
        max-height: 44px !important;
        font-size: 16px !important;
    }

    /* Estilos consistentes para inputs */
    .stTextInput > div > div > input,
    div[data-baseweb="input"] input {
        padding: 8px 12px !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 6px !important;
        background: white !important;
        color: #111827 !important;
        width: 100% !important;
        margin: 0 !important;
        line-height: normal !important;
    }

    /* Container do botão */
    [data-testid="stFormSubmitButton"] {
        margin-top: 1rem !important;
    }

    /* Botão de submit */
    [data-testid="stFormSubmitButton"] button {
        width: 100% !important;
        margin: 0 !important;
        border-radius: 6px !important;
        background: #1E40AF !important;
        color: white !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
    }

    /* Otimização para toque */
    input, button {
        touch-action: manipulation !important;
        -webkit-tap-highlight-color: transparent !important;
    }

    /* Prevenção de zoom */
    @media (max-width: 480px) {
        input, select, textarea {
            font-size: 16px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

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


st.markdown("""
<style>
/* Reset visual noise */
[data-testid="stDecoration"], footer, #MainMenu, div[data-testid="stStatusWidget"] { display: none !important; }
.block-container { padding-top: .25rem; padding-bottom: .5rem; }

/* Simple and readable typography */
html, body, [data-testid], .stMarkdown, .stText, .stButton, .stDataFrame {
  -webkit-font-smoothing: antialiased;
  font-family: -apple-system, system-ui, "Inter", "Segoe UI", Roboto, sans-serif;
}

/* Forms: full width and no text breaking */
[data-testid="stForm"] { max-width: 420px; margin: .5rem auto; padding: .75rem .75rem; }
.stTextInput > div > div > input,
.stPassword > div > div > input,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    height: 44px !important;
    font-size: 16px !important;
    background: white !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 6px !important;
}
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

load_css()  # chamar uma vez
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            text-rendering: optimizeLegibility;
        }
        
        /* Input otimizado para mobile */
        input, button {
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
        }
        
        /* Fix para flickering em mobile */
        .stApp {
            overflow-x: hidden;
            max-width: 100vw;
        }
        
        /* Prevenção de zoom indesejado em iOS */
        input[type="text"],
        input[type="password"] {
            font-size: 16px !important;
        }
        
        /* Otimizações mobile */
        @media (max-width: 480px) {
            .stApp {
                padding: 0.25rem;
            }
            
            .element-container {
                margin: 0.25rem 0;
            }
            
            .stButton > button {
                width: 100%;
                margin: 0.25rem 0;
            }
        }
    </style>
    """

# Aplicar estilos otimizados
st.markdown(get_cached_styles(), unsafe_allow_html=True)
st.markdown("""
    <style>
        /* Performance */
        [data-testid="stDecoration"] { display: none }
        div.block-container { padding-top: 0; padding-bottom: 0; }
        div[data-testid="stToolbar"] { display: none }
        
        /* Responsividade para mobile */
        @media (max-width: 640px) {
            .stApp {
                padding: 0.5rem !important;
            }
            
            /* Campos de formulário */
            div[data-testid="stForm"] {
                padding: 0.5rem !important;
                max-width: 100% !important;
            }
            
            div[data-testid="stForm"] > div:first-child {
                padding: 0 !important;
            }
            
            /* Inputs */
            .stTextInput input, .stTextInput div[data-baseweb="input"] {
                height: 2.5rem !important;
                min-height: 2.5rem !important;
                padding: 0.5rem !important;
                font-size: 16px !important;
                background-color: white !important;
                border: 1px solid #E5E7EB !important;
                border-radius: 0.375rem !important;
            }
            
            .stTextInput label {
                background: none !important;
                padding: 0 !important;
                font-size: 0.875rem !important;
            }
            
            /* Botões */
            .stButton button {
                width: 100% !important;
                padding: 0.625rem !important;
                height: 2.75rem !important;
                margin: 0.25rem 0 !important;
            }
            
            /* Textos */
            .stMarkdown p {
                font-size: 0.875rem !important;
                margin: 0.25rem 0 !important;
            }
            
            /* DataFrames */
            .stDataFrame {
                font-size: 0.75rem !important;
            }
            
            .stDataFrame [data-testid="stDataFrameDataCell"] {
                padding: 0.375rem !important;
            }
        }
        
        /* Otimizações gerais */
        * {
            -webkit-font-smoothing: antialiased;
            box-sizing: border-box;
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdown"] {
            min-height: 0;
        }
        
        .stSpinner {
            opacity: 0.5;
        }
        
        /* Redução de animações */
        @media (prefers-reduced-motion: reduce) {
            * {
                animation: none !important;
                transition: none !important;
            }
        }
    </style>
""", unsafe_allow_html=True)

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
    """Initialize session state variables."""
    # Garante que temos um usuário autenticado
    if 'user' not in st.session_state or not st.session_state.user:
        return

    # Set up default session state values
    if 'user_data' not in st.session_state:
        db = get_db()
        st.session_state.user_data = load_user_data(db, st.session_state.user)
        
    # Inicializa eventos
    if 'events' not in st.session_state:
        st.session_state.events = []
        
def handle_delete_giant(giant_id: int):
    """Manipula o evento de exclusão de gigante."""
    try:
        db = get_db()
        if delete_giant(db, st.session_state.user, giant_id):
            st.success(f"Gigante excluído com sucesso!")
            st.rerun()
        else:
            st.error("Não foi possível excluir o gigante.")
    except Exception as e:
        st.error(f"Erro ao excluir: {str(e)}")

def init_session_data():
    """Inicializa dados da sessão."""
    if 'user_data' not in st.session_state:
        db = get_db()
        st.session_state.user_data = load_user_data(db, st.session_state.user)
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
        
# Função logout() já definida anteriormente
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
        
        # Create database if it doesn't exist
        if not db_exists:
            Base.metadata.create_all(bind=engine)
            st.success("Banco de dados criado com sucesso!")
            return
        
        # Check and add new columns using context manager
        with get_db_session() as db:
            try:
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                # Verificar e adicionar colunas em giants
                if 'giants' in tables:
                    columns = {col['name'] for col in inspector.get_columns('giants')}
                    needed_columns = {'weekly_goal', 'interest_rate', 'payoff_efficiency'}
                    missing_columns = needed_columns - columns
                    
                    # Add missing columns in giants
                    for col in missing_columns:
                        try:
                            db.execute(text(f"ALTER TABLE giants ADD COLUMN {col} FLOAT DEFAULT 0.0"))
                            st.success(f"Coluna {col} adicionada à tabela giants")
                        except Exception as col_error:
                            st.warning(f"Erro ao adicionar coluna {col} em giants: {str(col_error)}")
                
                # Verificar e adicionar last_allocation_date em user_profiles
                if 'user_profiles' in tables:
                    columns = {col['name'] for col in inspector.get_columns('user_profiles')}
                    if 'last_allocation_date' not in columns:
                        try:
                            db.execute(text("ALTER TABLE user_profiles ADD COLUMN last_allocation_date DATE"))
                            st.success("Coluna last_allocation_date adicionada à tabela user_profiles")
                        except Exception as col_error:
                            st.warning(f"Erro ao adicionar last_allocation_date: {str(col_error)}")
                    
                    if missing_columns or 'last_allocation_date' not in columns:
                        st.success("Banco de dados atualizado com sucesso!")
                
            except Exception as table_error:
                st.error(f"Erro ao verificar tabelas: {str(table_error)}")
                try:
                    Base.metadata.create_all(bind=engine)
                    st.success("Banco de dados recriado com sucesso!")
                except Exception as recreate_error:
                    st.error(f"Erro ao recriar banco de dados: {str(recreate_error)}")
                    
    except Exception as e:
        st.error(f"Erro crítico na inicialização do banco: {str(e)}")
        raise

init_db()

def get_or_create_user(name: str) -> User:
    with get_db_session() as db:
        u = db.execute(select(User).where(User.name == name)).scalar_one_or_none()
        if u: 
            return u
        u = User(name=name)
        db.add(u)
        return u  # Session will be committed by context manager

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

@retry_operation(retries=3)
def auth_user(db: Session, username: str, password: str) -> Optional[User]:
    try:
        user = db.execute(select(User).where(User.name == username)).scalar_one_or_none()
        if user and user.password_hash == hash_password(password):
            return user
        return None
    except Exception as e:
        st.error(f"Erro ao autenticar: {str(e)}")
        return None

def create_user(db: Session, username: str, password: str) -> User:
    hashed_pwd = hash_password(password)
    user = User(name=username, password_hash=hashed_pwd)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@st.cache_resource
def get_cached_engine():
    """Cache database engine to reuse connections"""
    return engine

@st.cache_data(ttl=300)
def load_user_profile(user_id: int):
    """Cache user profile separately as it changes rarely"""
    with get_db() as db:
        return get_profile(db, user_id)

@st.cache_data(ttl=60)
def load_user_buckets(user_id: int):
    """Cache buckets with shorter TTL as they change more often"""
    with get_db() as db:
        return load_buckets(db, user_id)

@st.cache_data(ttl=60)
def load_user_giants(user_id: int):
    """Cache giants separately"""
    with get_db() as db:
        return load_giants(db, user_id)

@st.cache_data(ttl=60)
def load_user_bills(user_id: int):
    """Cache bills separately"""
    with get_db() as db:
        return load_bills(db, user_id)

@st.cache_data(ttl=30)
def load_user_movements(user_id: int, page: int = 1, per_page: int = 50):
    """Cache movements with pagination for better performance"""
    with get_db() as db:
        total = db.query(Movement).filter(Movement.user_id == user_id).count()
        movements = db.query(Movement).filter(Movement.user_id == user_id)\
            .order_by(Movement.date.desc())\
            .offset((page-1) * per_page)\
            .limit(per_page)\
            .all()
        return movements, total

@st.cache_data(ttl=300)
def load_cached_data(user_id: int):
    """Load data efficiently with separate caches"""
    profile = load_user_profile(user_id)
    buckets = load_user_buckets(user_id)
    giants = load_user_giants(user_id)
    bills = load_user_bills(user_id)
    movements, _ = load_user_movements(user_id, page=1)
    return profile, buckets, giants, movements, bills

def render_dashboard_header():
    st.markdown('<h1 class="animate-slide-in">📊 Visão Geral</h1>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)

def format_currency(value, format_str="R$ {:.2f}"):
    """Format a number as currency"""
    return format_str.format(abs(value)).replace(".", ",")

def money_br(value):
    """Format a number as Brazilian currency"""
    return format_currency(value)

def render_financial_metrics(movements):
    # Calcular métricas com base nos movimentos
    total_receitas = sum(m.amount for m in movements if m.kind == "Receita")
    total_despesas = sum(m.amount for m in movements if m.kind == "Despesa")
    saldo_atual = total_receitas - total_despesas
    
    # Métricas principais com estilos personalizados
    st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Receitas", money_br(total_receitas))
    with col2:
        st.metric("Total de Despesas", money_br(total_despesas))
    with col3:
        st.metric("Saldo", money_br(saldo_atual))
    return total_receitas, total_despesas, saldo_atual

def render_recent_movements(movements):
    if movements:
        st.subheader("📝 Movimentações Recentes")
        df = pd.DataFrame([{
            "Data": m.created_at.strftime("%d/%m/%Y"),
            "Tipo": m.kind,
            "Valor": money_br(m.amount),
            "Descrição": m.description
        } for m in movements])
        df = df.sort_values("Data", ascending=False)
        st.dataframe(df.head(10), use_container_width=True)

def handle_dashboard(db, user, profile, buckets, giants, movements, bills):
    render_dashboard_header()
    total_receitas, total_despesas, saldo_atual = render_financial_metrics(movements)
    render_recent_movements(movements)

def handle_livro_caixa(db, user, profile, buckets, giants, movements, bills):
    st.header("📚 Livro Caixa")
            
    # Botões de ação no topo
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        if st.button("🧹 Limpar Tudo"):
            if movements:
                st.session_state["confirmar_limpar"] = True
    with col2:
        if movements:
            csv = pd.DataFrame([{
                "ID": m.id,
                "Data": m.created_at.strftime("%d/%m/%Y"),
                "Tipo": m.kind,
                "Balde": next((b.name for b in buckets if b.id == m.bucket_id), ""),
                "Valor": money_br(m.amount),
                "Descrição": m.description
            } for m in movements])
            download_csv(csv, "livro_caixa.csv", "📥 Exportar CSV", use_container_width=True)
    with col3:
        if st.button("↻ Atualizar", type="primary"):
            st.cache_data.clear()
            st.rerun()
    with col4:
        st.markdown(custom_css.text_right, unsafe_allow_html=True)
        
    # Add confirmation dialog for cleanup
    if st.session_state.get("confirmar_limpar", False):
        if st.warning("⚠️ Tem certeza que deseja limpar todo o livro caixa?"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✓ Sim, limpar tudo"):
                    with db.begin():
                        db.query(Movement).filter_by(user_id=user.id).delete()
                    st.success("Livro caixa limpo com sucesso!")
                    st.session_state["confirmar_limpar"] = False
                    st.cache_data.clear()
                    st.rerun()
            with col2:
                if st.button("✗ Não, cancelar"):
                    st.session_state["confirmar_limpar"] = False
                    st.rerun()

def handle_calendario(db, user, profile):
    st.header("📅 Calendário")
    # Add Calendario specific content here

def handle_atrasos_riscos(db, user, profile):
    st.header("⚠️ Atrasos & Riscos")
    # Add Atrasos & Riscos specific content here

def handle_importar_extrato(db, user):
    st.header("📥 Importar Extrato")
    # Add Importar Extrato specific content here

def handle_configuracoes(db, user, profile):
    st.header("⚙️ Configurações")
    # Add Configuracoes specific content here

def handle_baldes(db, user):
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

def handle_plano_ataque(db, user, profile, buckets, giants, movements, bills):
    # Usar a nova versão otimizada do Plano de Ataque
    render_plano_ataque(db, giants)
    
    # Mobile-optimized styles
    st.markdown("""
        <style>
            .stDataFrame {
                font-size: 0.875rem !important;
            }
            @media (max-width: 640px) {
                .stDataFrame {
                    font-size: 0.75rem !important;
                }
                div[data-testid="column"] {
                    width: 100% !important;
                    flex: 1 1 100% !important;
                    margin-bottom: 0.5rem !important;
                }
            }
            div[data-testid="stForm"] {
                background: white;
                padding: 1rem;
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                margin: 0.5rem 0;
            }
        </style>
    """, unsafe_allow_html=True)

    # Lista de Giants existentes
    if giants:
        st.subheader("Gigantes Ativos")
        
        # Previsões
        st.caption("⏱️ Previsões")
        for g in giants:
            restante, diaria, dias = giant_forecast(g, db)
            txt = f"• **{g.name}** — Restante: {money_br(restante)} | Meta diária: {money_br(diaria)}"
            txt += f" | ~ **{math.ceil(dias)}** dias" if dias else " | defina a Meta semanal"
            st.markdown(txt)
        
        # Usar expander para mostrar/esconder instruções em mobile
        with st.expander("ℹ️ Como usar"):
            st.markdown("""
                - Toque nos botões ✏️ para editar
                - Toque em 🗑️ para excluir
                - Deslize para ver mais informações
            """)

def handle_entrada_saida(db, user, profile, buckets, giants, movements, bills):
    st.header("💰 Entrada e Saída")
            
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

def handle_calendario(db, user, profile):
    """Handle the Calendar section"""
    st.header("📅 Calendário")
    
    # Exibir data atual no calendário
    hoje = date.today()
    amanha = hoje + timedelta(days=1)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"📆 **{hoje.strftime('%d/%m/%Y')}**")
    with col2:
        st.markdown(f"⏰ **{amanha.strftime('%d/%m/%Y')}** (amanhã)")
    
    # Exibir contas do dia
    contas = load_user_bills(db, user.id)
    if contas:
        contas_hoje = [b for b in contas if b.due_date == hoje]
        contas_amanha = [b for b in contas if b.due_date == amanha]
        
        if contas_hoje:
            st.subheader("Contas de Hoje")
            for conta in contas_hoje:
                st.markdown(f"• {conta.name}: {money_br(conta.amount)}")
                
        if contas_amanha:
            st.subheader("Contas de Amanhã")
            for conta in contas_amanha:
                st.markdown(f"• {conta.name}: {money_br(conta.amount)}")

def handle_atrasos_riscos(db, user, profile):
    """Handle the Delays & Risks section"""
    st.header("⚠️ Atrasos & Riscos")
    
    hoje = date.today()
    contas = load_user_bills(db, user.id)
    if contas:
        contas_atrasadas = [b for b in contas if b.due_date < hoje and not b.paid]
        contas_futuras = [b for b in contas if b.due_date > hoje]
        
        # Tabela de atrasos
        if contas_atrasadas:
            st.subheader("📊 Contas Atrasadas")
            st.caption(f"{len(contas_atrasadas)} contas em atraso")
            df = pd.DataFrame([{
                "ID": b.id,
                "Nome": b.name,
                "Valor": money_br(b.amount),
                "Vencimento": b.due_date.strftime("%d/%m/%Y"),
                "Atraso": f"{(hoje - b.due_date).days} dias"
            } for b in contas_atrasadas])
            st.dataframe(df.sort_values("Vencimento"), use_container_width=True)
        
        # Próximos vencimentos
        if contas_futuras:
            st.subheader("📅 Próximos Vencimentos")
            df = pd.DataFrame([{
                "ID": b.id,
                "Nome": b.name,
                "Valor": money_br(b.amount),
                "Vencimento": b.due_date.strftime("%d/%m/%Y"),
                "Dias": f"{(b.due_date - hoje).days} dias"
            } for b in contas_futuras])
            st.dataframe(df.sort_values("Vencimento").head(5), use_container_width=True)
    else:
        st.info("Nenhuma conta cadastrada ainda!")

def handle_importar_extrato(db, user):
    """Handle the Import Statement section"""
    st.header("📥 Importar Extrato")
    st.info("Funcionalidade em desenvolvimento!")

def handle_configuracoes(db, user, profile):
    """Handle the Settings section"""
    st.header("⚙️ Configurações")
    
    # Form para editar perfil
    with st.form("editar_perfil"):
        st.subheader("Perfil")
        renda_mensal = st.number_input("Renda Mensal", value=profile.monthly_income, min_value=0.0, step=100.0)
        despesa_mensal = st.number_input("Despesa Mensal", value=profile.monthly_expense, min_value=0.0, step=100.0)
        if st.form_submit_button("💾 Salvar"):
            profile.monthly_income = renda_mensal
            profile.monthly_expense = despesa_mensal
            db.commit()
            st.success("Perfil atualizado!")
            st.rerun()

def get_menu_handler(menu):
    """Get the appropriate menu handler function based on menu name"""
    menu_mapping = {
        "Dashboard": handle_dashboard,
        "Baldes": handle_baldes,
        "Plano de Ataque": handle_plano_ataque,
        "Entrada e Saída": handle_entrada_saida,
        "Livro Caixa": handle_livro_caixa,
        "Calendário": handle_calendario,
        "Atrasos & Riscos": handle_atrasos_riscos,
        "Importar Extrato": handle_importar_extrato,
        "Configurações": handle_configuracoes
    }
    return menu_mapping.get(menu)

def handle_menu_items(menu, user, db, profile, buckets, giants, movements, bills):
    """Handle menu navigation and render appropriate content"""
    # Handle menu navigation
    if menu == "Dashboard":
        handle_dashboard(db, user, profile, buckets, giants, movements, bills)
    elif menu == "Baldes":
        handle_baldes(db, user)
    elif menu == "Plano de Ataque":
        handle_plano_ataque(db, user, profile, buckets, giants, movements, bills)
    elif menu == "Entrada e Saída":
        handle_entrada_saida(db, user, profile, buckets, giants, movements, bills)
    elif menu == "Livro Caixa":
        handle_livro_caixa(db, user, profile, buckets, giants, movements, bills)
    elif menu == "Calendário":
        handle_calendario(db, user, profile)
    elif menu == "Atrasos & Riscos":
        handle_atrasos_riscos(db, user, profile)
    elif menu == "Importar Extrato":
        handle_importar_extrato(db, user)
    elif menu == "Configurações":
        handle_configuracoes(db, user, profile)
    else:
        st.info("Seção em desenvolvimento!")
    
    handler = menu_handlers.get(menu)
    if handler:
        handler()
    else:
        st.info("Seção em desenvolvimento!")

@auth_required
def main():
    # Initialize all state variables and database session
    init_session_state()
    inject_mobile_ui() # Injeta CSS mobile-first
    
    # Add mobile viewport meta tag
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            [data-testid="stSidebar"] {
                min-width: unset !important;
                width: auto !important;
                flex-shrink: 0 !important;
            }
            
            @media (max-width: 640px) {
                .main {
                    padding: 0.5rem !important;
                }
                
                .stApp {
                    overflow: auto !important;
                }
                
                div[data-testid="stForm"] {
                    padding: 0.5rem !important;
                }
                
                div[data-testid="stVerticalBlock"] {
                    gap: 0.5rem !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    if not st.session_state.authenticated:
        # ==== Seção de Título e Slogan ====
        st.markdown("""
            <style>
                /* Estilo minimalista e otimizado */
                .compact-login {
                    margin: 0 auto;
                    padding: 0.5rem;
                    max-width: 100%;
                    text-align: center;
                }
                
                .brand {
                    color: #1E40AF;
                    font-family: system-ui, -apple-system, sans-serif;
                    font-weight: 600;
                    font-size: 1.75rem;
                    margin: 0.5rem 0;
                    padding: 0;
                }
                
                .slogan {
                    color: #10B981;
                    font-family: system-ui, -apple-system, sans-serif;
                    font-size: 0.875rem;
                    margin: 0.25rem 0 1rem 0;
                    opacity: 0.9;
                }
                
                /* Form container */
                [data-testid="stForm"] {
                    background: white;
                    padding: 1rem;
                    border-radius: 0.5rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    margin: 0.5rem auto;
                    max-width: 320px;
                }

                /* Login form specific styles */
                .element-container:has(> [data-testid="stTextInput"]),
                .element-container:has(> [data-testid="stPasswordInput"]) {
                    width: 100% !important;
                    max-width: none !important;
                    margin-bottom: 1rem !important;
                }

                [data-testid="stForm"] [data-testid="stTextInput"] > div,
                [data-testid="stForm"] [data-testid="stPasswordInput"] > div {
                    width: 100% !important;
                    max-width: none !important;
                }

                [data-testid="stForm"] input {
                    width: 100% !important;
                    height: 44px !important;
                    padding: 0.5rem 1rem !important;
                    font-size: 16px !important;
                    border: 1px solid #E5E7EB !important;
                    border-radius: 6px !important;
                    background: white !important;
                }

                /* Fix for checkbox alignment */
                [data-testid="stForm"] [data-testid="stCheckbox"] {
                    margin-top: 0.5rem !important;
                    margin-bottom: 1rem !important;
                }
                
                /* Mobile otimizado */
                @media (max-width: 480px) {
                    .compact-login {
                        padding: 0.25rem;
                    }
                    .brand {
                        font-size: 1.5rem;
                    }
                    .slogan {
                        font-size: 0.75rem;
                    }
                    [data-testid="stForm"] {
                        padding: 0.75rem;
                        margin: 0.25rem auto;
                    }
                }
            </style>
            <div class="compact-login">
                <h1 class="brand">DAVI</h1>
                <p class="slogan">Vença seus gigantes financeiros</p>
            </div>
        """, unsafe_allow_html=True)
        # ================================

        # Tabs de Login/Cadastro
        tab1, tab2 = st.tabs(["Login", "Cadastro"])
        
        with tab1:
            # Container para melhor organização do formulário
            with st.container():
                with st.form("login_form", clear_on_submit=True):
                    # Estilo otimizado para formulário e verificação de carregamento
                    st.markdown("<!-- Form loaded -->", unsafe_allow_html=True)
                st.markdown("""
                    <style>
                        /* Reset Form Styles */
                        div[data-testid="stForm"] > div:first-child {
                            width: 100% !important;
                            max-width: 320px !important;
                            margin: 0 auto !important;
                            background: white;
                            border-radius: 8px;
                            padding: 1.25rem !important;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        }

                        /* Consistent Input Styling */
                        .stTextInput > div,
                        .stTextInput div[data-baseweb="input"],
                        div[data-baseweb="base-input"],
                        [data-testid="stTextInput"] input,
                        [data-testid="stTextInput"] div[data-baseweb="input"] {
                            width: 100% !important;
                            min-height: 44px !important;
                            height: 44px !important;
                            max-height: 44px !important;
                            line-height: 44px !important;
                            box-sizing: border-box !important;
                        }

                        /* Força todos os inputs a terem o mesmo tamanho */
                        [data-testid="stTextInput"],
                        [data-testid="stPasswordInput"] {
                            width: 100% !important;
                            margin: 0 auto 1rem auto !important;
                        }

                        /* Estilo consistente para todos os inputs */
                        .stTextInput input,
                        .stPasswordInput input,
                        input[type="text"],
                        input[type="password"] {
                            width: 100% !important;
                            padding: 8px 12px !important;
                            font-size: 16px !important;
                            border: 1px solid #E5E7EB !important;
                            border-radius: 6px !important;
                            background: white !important;
                            color: #111827 !important;
                            margin: 4px 0 !important;
                            appearance: none !important;
                            -webkit-appearance: none !important;
                            box-sizing: border-box !important;
                        }

                        /* Fix Password Input */
                        div[data-baseweb="input"] {
                            height: 44px !important;
                            min-height: 44px !important;
                            background: white !important;
                        }

                        /* Consistent Label Styling */
                        .stTextInput label,
                        .stPassword label {
                            color: #374151 !important;
                            font-size: 14px !important;
                            margin-bottom: 4px !important;
                        }

                        /* Button Styling */
                        .stButton > button {
                            width: 100% !important;
                            height: 44px !important;
                            background: #1E40AF !important;
                            color: white !important;
                            border: none !important;
                            border-radius: 6px !important;
                            font-size: 16px !important;
                            font-weight: 500 !important;
                            margin: 8px 0 !important;
                            cursor: pointer !important;
                            transition: background-color 0.2s ease;
                        }

                        .stButton > button:hover {
                            background: #1C3879 !important;
                        }

                        /* Fix Input Spacing */
                        .stTextInput,
                        .stPassword {
                            margin-bottom: 1rem !important;
                        }

                        /* Checkbox Alignment */
                        [data-testid="stCheckbox"] {
                            margin: 0.5rem 0 1rem !important;
                        }

                        /* Mobile Optimization */
                        @media (max-width: 480px) {
                            div[data-testid="stForm"] > div:first-child {
                                padding: 1rem !important;
                            }
                            
                            .stTextInput input,
                            .stPassword input,
                            div[data-baseweb="input"],
                            .stButton > button {
                                height: 44px !important;
                                font-size: 16px !important; /* Prevent zoom on iOS */
                            }
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                # Inputs com tamanho consistente
                username = st.text_input(
                    "Usuário",
                    key="login_username",
                    placeholder="Digite seu usuário",
                    help="Nome de usuário para acesso"
                )
                
                password = st.text_input(
                    "Senha",
                    type="password",
                    key="login_password",
                    placeholder="Digite sua senha"
                )
                
                # Espaçador para garantir alinhamento
                st.markdown('<div style="height: 8px"></div>', unsafe_allow_html=True)
                
                manter_login = st.checkbox(
                    "Manter conectado",
                    key="manter_login",
                    help="Mantenha-se conectado neste dispositivo"
                )
                
                if st.form_submit_button("Entrar", use_container_width=True):
                    if not username.strip() or not password:
                        st.error("Preencha usuário e senha.")
                    else:
                        with get_db() as db:
                            user = auth_user(db, username.strip(), password)
                            if user:
                                st.session_state.authenticated = True
                                st.session_state.user = user
                                if manter_login:
                                    st.session_state.saved_user = user
                                
                                # Executar alocação automática após login
                                ensure_daily_allocation(db, user)
                                st.rerun()
                            else:
                                st.error("Usuário ou senha inválidos.")
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
                        with get_db_session() as db:
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
            # Menu Header
            col1, col2 = st.columns([3,1])
            with col1:
                st.markdown('<h1 style="color: #1E40AF; font-size: 1.5rem; margin-bottom: 1rem;">☰ Menu</h1>', unsafe_allow_html=True)
            with col2:
                if st.button("Sair", key="btn_logout", type="primary"):
                    logout()
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
            
            # Handle menu navigation
            handle_menu_items(menu, user, db, profile, buckets, giants, movements, bills)
        
        # Barra de navegação mobile no rodapé
        bottom_nav(active="dashboard" if menu == "Dashboard" else
                  "plan" if menu == "Plano de Ataque" else
                  "buckets" if menu == "Baldes" else
                  "income" if menu == "Entrada e Saída" else "home")
        
        # Handle menu navigation
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
                safe_dataframe(df.tail(10).sort_values("data", ascending=False))
        
        elif menu == "Plano de Ataque":
            # Usar a nova versão otimizada do Plano de Ataque
            render_plano_ataque(db, giants)
            
            # Mobile-optimized styles
            st.markdown("""
                <style>
                    .stDataFrame {
                        font-size: 0.875rem !important;
                    }
                    @media (max-width: 640px) {
                        .stDataFrame {
                            font-size: 0.75rem !important;
                        }
                        div[data-testid="column"] {
                            width: 100% !important;
                            flex: 1 1 100% !important;
                            margin-bottom: 0.5rem !important;
                        }
                    }
                    div[data-testid="stForm"] {
                        background: white;
                        padding: 1rem;
                        border-radius: 0.5rem;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        margin: 0.5rem 0;
                    }
                </style>
            """, unsafe_allow_html=True)

            # Lista de Giants existentes
            if giants:
                st.subheader("Gigantes Ativos")
                
                # Previsões
                st.caption("⏱️ Previsões")
                for g in giants:
                    restante, diaria, dias = giant_forecast(g, db)
                    txt = f"• **{g.name}** — Restante: {money_br(restante)} | Meta diária: {money_br(diaria)}"
                    txt += f" | ~ **{math.ceil(dias)}** dias" if dias else " | defina a Meta semanal"
                    st.markdown(txt)
                
                # Usar expander para mostrar/esconder instruções em mobile
                with st.expander("ℹ️ Como usar"):
                    st.markdown("""
                        - Toque nos botões ✏️ para editar
                        - Toque em 🗑️ para excluir
                        - Deslize para ver mais informações
                        - Toque em um gigante para ver detalhes
                    """)

                # Recalcula dados para tabela
                rows = []
                for g in giants:
                    total_pago = sum(p.amount for p in db.query(GiantPayment).filter_by(giant_id=g.id).all())
                    restante = max(0.0, (g.total_to_pay or 0.0) - total_pago)
                    progresso = (total_pago / g.total_to_pay) if (g.total_to_pay or 0) > 0 else 0.0

                    ultima_semana = date.today() - timedelta(days=7)
                    aportes = db.query(GiantPayment).filter_by(giant_id=g.id).all()
                    depositos_semana = sum(p.amount for p in aportes if p.date and p.date >= ultima_semana)
                    meta_txt = "-" if not g.weekly_goal else f"{money_br(depositos_semana)} / {money_br(g.weekly_goal)}"

                    rows.append({
                        "ID": g.id,
                        "Nome": g.name,
                        "Total": g.total_to_pay or 0.0,
                        "Pago": total_pago,
                        "Restante": restante,
                        "Progresso": progresso,  # 0..1
                        "Meta Semanal": meta_txt,
                        "Status": "✅" if progresso >= 0.95 else "⏳",
                        "Taxa": f"{(g.interest_rate or 0):.1f}%" if g.interest_rate else "-"
                    })

                # ------- Formatação e exibição dos gigantes -------
                df_giants = pd.DataFrame(rows)

                # Configurar colunas
                st.dataframe(
                    df_giants,
                    column_config={
                        "Progresso": st.column_config.ProgressColumn(
                            "Progresso",
                            min_value=0.0,
                            max_value=1.0,
                            format="%.0f%%"
                        ),
                        "Meta Semanal": st.column_config.TextColumn("Meta Semanal"),
                        "Status": st.column_config.TextColumn("Status"),
                        "Taxa": st.column_config.TextColumn("Taxa Mensal")
                    }
                )

                # Formatar valores monetários antes
                for colm in ["Total", "Pago", "Restante"]:
                    df_giants[colm] = df_giants[colm].apply(money_br)

                def render_giants_rows(df: pd.DataFrame, user_id: int):
                    for _, row in df.iterrows():
                        c1,c2,c3,c4,c5,c6 = st.columns([2,4,3,3,3,2])
                        with c1: st.write(f"**#{int(row['ID'])}**")
                        with c2: st.write(row["Nome"])
                        with c3: st.write(f"{row['Total']}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with c4: st.write(f"{row['Pago']}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with c5: st.write(f"{row['Restante']}".replace(",", "X").replace(".", ",").replace("X", "."))
                        with c6:
                            b1,b2 = st.columns(2)
                            if b1.button("✏️", key=f"edit_{row['ID']}"):
                                st.session_state.edit_giant_id = int(row["ID"])
                                st.rerun()
                            if b2.button("🗑️", key=f"del_{row['ID']}"):
                                try:
                                    with get_db() as db:
                                        uid = st.session_state.auth["user_id"] if "auth" in st.session_state else st.session_state.user.id
                                        ok = delete_giant(db, int(row["ID"]), uid)
                                        if ok:
                                            st.toast("🗑️ Excluído!")
                                            st.cache_data.clear()
                                            st.rerun()
                                        else:
                                            st.toast("Não foi possível excluir")
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {e}")

                render_giants_rows(df_giants, st.session_state.auth["user_id"])
                st.caption("Ações rápidas")
                for g in rows:
                    c1, c2, c3 = st.columns([5,2,2])
                    with c1:
                        st.write(f"**{g['Nome']}** — Restante: {g['Restante']}")
                    with c2:
                        if st.button("✏️ Editar", key=f"e{g['ID']}"):
                            st.session_state[f"edit_g_{g['ID']}"]=True
                    with c3:
                        if st.button("🗑️ Excluir", key=f"d{g['ID']}"):
                            with get_db() as new_db:  # Nova conexão para exclusão
                                if delete_giant(new_db, user.id, g['ID']):
                                    st.cache_data.clear()  # Limpa cache após exclusão
                                    time.sleep(0.5)  # Pequena pausa para feedback visual
                                    st.rerun()
                    
                    if st.session_state.get(f"edit_g_{g['ID']}"):
                        with st.form(f"form_g_{g['ID']}"):
                            nome = st.text_input("Nome", g['Nome'])
                            total = st.number_input("Total a quitar", value=float(g['Total']), step=100.0)
                            meta = st.number_input("Meta semanal", value=float(g['Meta Semanal'] or 0.0), step=50.0)
                            taxa = st.number_input("Juros (%)", value=float(g['Taxa'] or 0.0), step=0.1, format="%.2f")
                            if st.form_submit_button("Salvar"):
                                with tx(db):
                                    giant = db.get(Giant, g['ID'])
                                    if giant:
                                        giant.name = nome
                                        giant.total_to_pay = total
                                        giant.weekly_goal = meta
                                        giant.interest_rate = taxa
                                st.toast("Atualizado.")
                                st.session_state[f"edit_g_{g['ID']}"]=False
                                st.rerun()

                # Add delete column
                df_show["Excluir"] = False

                edited = st.data_editor(
                    df_show,
                    use_container_width=True,
                    num_rows="fixed",
                    hide_index=True,
                    key="giants_editor",
                )

                # Previsões
                st.subheader("⏱️ Previsões")
                for g in rows:
                    restante, diaria, dias = giant_forecast(Giant(**g), db)
                    txt = f"• **{g['Nome']}** — Restante: {money_br(restante)} | Meta diária: {money_br(diaria)}"
                    txt += f" | ~ **{math.ceil(dias)}** dias" if dias else " | defina a Meta semanal"
                    st.markdown(txt)

                # Process marked deletions
                ids_para_excluir = edited.loc[edited["Excluir"] == True, "ID"].tolist() if edited is not None else []
                if ids_para_excluir:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        confirm = st.button(f"🗑️ Excluir selecionado(s) ({len(ids_para_excluir)})", type="secondary", use_container_width=True)
                    with col2:
                        cancel = st.button("❌ Cancelar", use_container_width=True)
                    
                    if confirm and not cancel:
                        with st.spinner("Excluindo registros..."):
                            ok, fail = 0, 0
                            for gid in ids_para_excluir:
                                try:
                                    with get_db() as db:  # Nova conexão para cada operação
                                        if delete_giant(db, int(gid)):
                                            ok += 1
                                        else:
                                            fail += 1
                                except Exception as e:
                                    st.error(f"Erro ao excluir ID {gid}: {str(e)}")
                                    fail += 1
                            
                            if ok > 0:
                                st.success(f"{ok} gigante(s) excluído(s) com sucesso!")
                            if fail > 0:
                                st.warning(f"{fail} registro(s) não puderam ser excluídos.")
                            
                            st.cache_data.clear()
                            time.sleep(1)  # Pequena pausa para feedback visual
                            st.rerun()

                # Container para o cartão do gigante
                with st.container():
                    # Cabeçalho do cartão
                    st.markdown("""
                        <style>
                            .giant-card {
                                border: 1px solid #e5e7eb;
                                border-radius: 0.5rem;
                                padding: 1rem;
                                margin-bottom: 1rem;
                            }
                            .giant-header {
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                margin-bottom: 0.75rem;
                            }
                            .giant-title {
                                font-size: 1.125rem;
                                color: #111827;
                                margin: 0;
                            }
                            .giant-actions {
                                display: flex;
                                gap: 0.5rem;
                            }
                            .giant-button {
                                padding: 0.25rem 0.5rem;
                                border: none;
                                background: none;
                                cursor: pointer;
                                border-radius: 0.25rem;
                            }
                            .giant-button:hover {
                                background: #f3f4f6;
                            }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    # Layout do cartão
                    col1, col2, col3 = st.columns([6,1,1])
                    with col1:
                        st.markdown(f"<h3 class='giant-title'>{giant['Nome']} {giant['Status']}</h3>", unsafe_allow_html=True)
                    with col2:
                        if st.button("✏️", key=f"edit_{giant['ID']}", help="Editar gigante", 
                                   use_container_width=True, type="secondary"):
                            st.session_state.editing_giant = giant['ID']
                            st.rerun()
                    with col3:
                        # Botão de exclusão com confirmação
                        if st.button("🗑️", key=f"del_{giant['ID']}", help="Excluir gigante",
                                   use_container_width=True, type="secondary"):
                            if "confirming_delete" not in st.session_state:
                                st.session_state.confirming_delete = giant['ID']
                                st.warning(f"Tem certeza que deseja excluir o gigante {giant['Nome']}?")
                                st.button("Sim, excluir", key=f"confirm_del_{giant['ID']}", type="secondary")
                            elif st.session_state.confirming_delete == giant['ID']:
                                try:
                                    db = get_db()
                                    # Garante que temos os parâmetros corretos
                                    user_id = st.session_state.user
                                    if user_id:
                                        result = delete_giant(db, giant['ID'], user_id)
                                    else:
                                        st.error("Usuário não encontrado")
                                        result = False
                                    if result:
                                        st.success(f"Gigante {giant['Nome']} excluído com sucesso!")
                                        st.cache_data.clear()
                                        time.sleep(0.5)  # Feedback visual
                                        del st.session_state.confirming_delete
                                        st.rerun()
                                    else:
                                        st.error("Não foi possível excluir o gigante")
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {str(e)}")
                                finally:
                                    if "confirming_delete" in st.session_state:
                                        del st.session_state.confirming_delete

                        
                        # Handle edit/delete actions via session state
                        if f"edit_{giant['ID']}" not in st.session_state:
                            st.session_state[f"edit_{giant['ID']}"] = False
                            
                        if st.session_state.get(f"edit_{giant['ID']}", False):
                            with st.form(f"edit_giant_{giant['ID']}", clear_on_submit=True):
                                st.markdown("<h4 style='margin:0;'>Editar Gigante</h4>", unsafe_allow_html=True)
                                c1, c2 = st.columns(2)
                                with c1:
                                    new_total = st.number_input("Novo Total", value=float(giant['Total'].replace('R$','').replace('.','').replace(',','.').strip()), step=100.0)
                                with c2:
                                    new_goal = st.number_input("Meta Semanal", value=0.0, step=50.0)
                                
                                if st.form_submit_button("💾 Salvar", use_container_width=True):
                                    def update_giant(session, giant_id, total, goal):
                                        giant = session.query(Giant).get(giant_id)
                                        if giant:
                                            giant.total_to_pay = total
                                            giant.weekly_goal = goal
                                            return True
                                        return False
                                    
                                    if safe_operation(update_giant, giant['ID'], new_total, new_goal):
                                        st.success("Gigante atualizado!")
                                        st.session_state[f"edit_{giant['ID']}"] = False
                                        st.rerun()
                                        
                        if st.session_state.confirmar_exclusao.get(giant['ID']):
                            st.warning("Confirma a exclusão deste Gigante?")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Sim", key=f"confirm_del_{giant['ID']}", use_container_width=True):
                                    def delete_giant(db, giant_id: int):
                                        try:
                                            g = db.get(Giant, giant_id)
                                            if not g:
                                                st.error("Gigante não encontrado.")
                                                return False
                                            # Delete giant's payments quickly
                                            db.query(GiantPayment).filter(GiantPayment.giant_id == g.id).delete(synchronize_session=False)
                                            db.delete(g)
                                            db.commit()
                                            st.cache_data.clear()
                                            return True
                                        except Exception as e:
                                            db.rollback()
                                            st.error(f"Erro ao excluir: {str(e)}")
                                            return False

                                    with get_db() as db:
                                        if delete_giant(db, giant['ID']):
                                            st.success("Gigante excluído!")
                                            st.cache_data.clear()
                                            st.rerun()
                                        else:
                                            st.error("Gigante não encontrado ou já removido.")
                            with c2:
                                if st.button("❌ Não", key=f"cancel_del_{giant['ID']}", use_container_width=True):
                                    st.session_state.confirmar_exclusao.pop(giant['ID'])
                                    st.rerun()
                        
                        if st.session_state.get("editing") == giant['ID']:
                            with st.form(f"edit_giant_{giant['ID']}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    new_total = st.number_input("Novo Total", value=float(giant['Total'].replace('R$','').replace('.','').replace(',','.').strip()))
                                    new_goal = st.number_input("Nova Meta Semanal", value=0.0, step=100.0)
                                with col2:
                                    new_rate = st.number_input("Nova Taxa (%)", value=float(giant['Taxa'].replace('%','').strip()) if giant['Taxa'] != '-' else 0.0)
                                
                                if st.form_submit_button("💾 Salvar"):
                                    with get_db() as db:
                                        g = db.query(Giant).get(giant['ID'])
                                        if g:
                                            g.total_to_pay = new_total
                                            g.weekly_goal = new_goal
                                            g.interest_rate = new_rate
                                        st.session_state.editing = None
                                        st.rerun()
                
                        if st.session_state.confirmar_exclusao.get(giant['ID']):
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ Confirmar", key=f"confirm_{giant['ID']}"):
                                    with get_db_session() as db:
                                        g = db.query(Giant).get(giant['ID'])
                                        if g:
                                            db.delete(g)
                                        st.session_state.confirmar_exclusao.pop(giant['ID'])
                                        st.rerun()
                            with col2:
                                if st.button("❌ Cancelar", key=f"cancel_{giant['ID']}"):
                                    st.session_state.confirmar_exclusao.pop(giant['ID'])
                                    st.rerun()

                # Seleção / Ações sobre um giant específico
                nomes = df_giants["Nome"].tolist()
                selected_name = st.selectbox("Selecione um Gigante:", options=nomes, key="giant_select")
                if selected_name:
                    sel_id = int(pd.DataFrame(rows).query("Nome == @selected_name")["ID"].iloc[0])
                    giant_sel = db.query(Giant).get(sel_id)
                    if not giant_sel:
                        st.error("Gigante não encontrado.")
                    else:
                        # Ações: Excluir (com confirmação)
                        cols_actions = st.columns([1, 1, 6])
                        with cols_actions[0]:
                            if st.button("🗑️ Excluir", key=f"del_giant_btn_{sel_id}", type="secondary"):
                                st.session_state.confirmar_exclusao[sel_id] = True
                        with cols_actions[1]:
                            st.write("")  # espaçador

                        if st.session_state.confirmar_exclusao.get(sel_id):
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Confirmar", key=f"confirm_giant_yes_{sel_id}"):
                                    try:
                                        db.query(GiantPayment).filter_by(giant_id=sel_id).delete()
                                        db.delete(giant_sel)
                                        db.commit()
                                        st.success("Gigante excluído com sucesso!")
                                        st.session_state.confirmar_exclusao.pop(sel_id, None)
                                        st.rerun()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Erro ao excluir: {e}")
                            with c2:
                                if st.button("❌ Cancelar", key=f"confirm_giant_no_{sel_id}"):
                                    st.session_state.confirmar_exclusao.pop(sel_id, None)
                                    st.rerun()

                        # Form de aporte
                        with st.form(f"aporte_giant_{sel_id}"):
                            ap_col1, ap_col2, ap_col3 = st.columns([2, 2, 1])
                            with ap_col1:
                                valor_aporte = st.number_input("Valor", min_value=0.0, step=100.0, format="%.2f")
                            with ap_col2:
                                obs_aporte = st.text_input("Observação", value="")
                            with ap_col3:
                                data_aporte = st.date_input("Data", value=date.today())

                            if st.form_submit_button("💰 Registrar Aporte"):
                                if valor_aporte <= 0:
                                    st.error("Informe um valor maior que zero.")
                                    return

                                try:
                                    with get_db() as new_db:  # Nova conexão
                                        novo = GiantPayment(
                                            user_id=user.id, 
                                            giant_id=sel_id,
                                            amount=valor_aporte, 
                                            date=data_aporte,
                                            note=obs_aporte or f"Aporte {data_aporte.strftime('%d/%m/%Y')}"
                                        )
                                        new_db.add(novo)
                                        giant_sel = new_db.get(Giant, sel_id)  # Recarrega o gigante
                                        if giant_sel:
                                            check_giant_victory(new_db, giant_sel, valor_aporte)
                                            new_db.commit()
                                            st.cache_data.clear()
                                            st.success("✅ Aporte registrado!")
                                            st.toast(f"💰 {money_br(valor_aporte)} aportado", icon="💪")
                                            time.sleep(0.5)
                                            st.rerun()
                                except Exception as e:
                                    db.rollback()
                                    st.error(f"Erro ao registrar aporte: {str(e)}")
                                    st.rerun()
                                else:
                                    st.error("Informe um valor maior que zero.")

                        # Histórico resumido
                        ult = db.query(GiantPayment).filter_by(giant_id=sel_id).order_by(GiantPayment.date.desc()).limit(3).all()
                        if ult:
                            st.caption("Últimos aportes:")
                            for ap in ult:
                                st.text(f"- {date_br(ap.date)}: {money_br(ap.amount)}")

                st.divider()

            # Novo Giant with mobile optimizations
            st.markdown("""
                <h3 style='
                    font-size: 1.25rem;
                    color: #111827;
                    margin: 1.5rem 0 1rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                '>
                    <span style='font-size:1.5rem;'>➕</span> Novo Gigante
                </h3>
            """, unsafe_allow_html=True)
            
            with st.form("novo_giant", clear_on_submit=True):
                st.markdown("""
                    <style>
                        div[data-testid="stForm"] {
                            background: white;
                            padding: 1.5rem;
                            border-radius: 0.75rem;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            border: 1px solid #e5e7eb;
                        }
                        @media (max-width: 640px) {
                            div[data-testid="stForm"] {
                                padding: 1rem;
                            }
                            div[data-testid="column"] {
                                width: 100% !important;
                            }
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                # Split form into sections for better mobile layout
                st.markdown("##### Informações Básicas")
                nome_giant = st.text_input(
                    "Nome do Gigante",
                    placeholder="Ex: Cartão Nubank",
                    help="Digite o nome identificador do Gigante"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    valor_total = st.number_input(
                        "Valor Total a Quitar",
                        min_value=0.0,
                        step=100.0,
                        format="%.2f",
                        help="Valor total da dívida"
                    )
                with col2:
                    parcelas = st.number_input(
                        "Número de Parcelas",
                        min_value=0,
                        step=1,
                        help="Quantidade de parcelas (0 para valor único)"
                    )
                
                st.markdown("##### Metas e Prioridades")
                col3, col4 = st.columns(2)
                with col3:
                    deposito_semanal = st.number_input(
                        "Meta de Depósito Semanal",
                        min_value=0.0,
                        step=50.0,
                        format="%.2f",
                        help="Quanto você planeja depositar por semana"
                    )
                with col4:
                    prioridade = st.number_input(
                        "Prioridade",
                        min_value=1,
                        step=1,
                        help="1 = maior prioridade"
                    )
                
                taxa_juros = st.number_input(
                    "Taxa de Juros Mensal (%)",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    help="Taxa de juros mensal em porcentagem"
                )

                if st.form_submit_button("💾 Criar Gigante", use_container_width=True):
                    if nome_giant and valor_total > 0:
                        # Calculate values
                        montante_final = valor_total * (1 + (taxa_juros / 100.0)) ** parcelas if parcelas > 0 else valor_total
                        payoff_eff = 0.0 if valor_total == 0 else (montante_final - valor_total) / (valor_total / 1000.0)

                        # Create new Giant with safe operation
                        def create_giant(session):
                            novo_g = Giant(
                                user_id=user.id,
                                name=nome_giant,
                                total_to_pay=valor_total,
                                parcels=int(parcelas),
                                priority=int(prioridade),
                                status="active",
                                weekly_goal=deposito_semanal,
                                interest_rate=taxa_juros,
                                payoff_efficiency=payoff_eff
                            )
                            session.add(novo_g)
                            return True

                        if safe_operation(create_giant):
                            st.success(f"✅ Gigante {nome} foi criado!")
                            st.toast("Novo desafio registrado!", icon="🎯")
                            st.balloons()
                            time.sleep(0.5)  # Pequena pausa para efeito visual
                            st.rerun()
                        else:
                            st.error("❌ Erro ao criar o Gigante")
                    else:
                        st.error("⚠️ Preencha o nome e valor do Gigante")
        
# Helper functions for bucket management
def create_bucket(db, user, name, tipo, description, percent):
    """Create a new bucket"""
    bucket = Bucket(
        user_id=user.id,
        name=name,
        description=description,
        percent=float(percent),
        type=tipo.lower()
    )
    db.add(bucket)
    db.commit()
    return bucket
                        st.error("Preencha o nome e tipo do balde")
            
            st.markdown("<hr style='margin: 1.5rem 0'>", unsafe_allow_html=True)
            
            if buckets:
                if "confirmar_exclusao_balde" not in st.session_state:
                    st.session_state.confirmar_exclusao_balde = {}
                
                # Mostrar baldes com opção de exclusão
                for bucket in buckets:
                    # Transform bucket data into a DataFrame for data_editor
                    df_buckets = pd.DataFrame([{
                        "ID": bucket.id,
                        "Nome": bucket.name,
                        "Porcentagem": f"{bucket.percent}%",
                        "Saldo": money_br(bucket.balance),
                        "Prioridade": bucket.description,
                        "Excluir": False
                    }])
                    
                    edited = st.data_editor(
                        df_buckets,
                        use_container_width=True,
                        num_rows="fixed",
                        hide_index=True,
                        key=f"bucket_editor_{bucket.id}",
                    )
                    
                    # Process deletions
                    ids_para_excluir = edited.loc[edited["Excluir"] == True, "ID"].tolist()
                    if ids_para_excluir:
                        if st.button(f"🗑️ Excluir balde", type="secondary", key=f"del_bucket_{bucket.id}"):
                            try:
                                # Delete with synchronize_session=False for better performance
                                db.query(Movement).filter(Movement.bucket_id == bucket.id).delete(synchronize_session=False)
                                db.delete(bucket)
                                db.commit()
                                st.success("Balde excluído com sucesso!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                db.rollback()
                                st.error("Erro ao excluir balde. Tente novamente.")
                    st.markdown("<hr style='margin: 0.5rem 0'>", unsafe_allow_html=True)
        

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
            
            with st.form("nova_entrada", clear_on_submit=True, border=True):
                valor = st.number_input("Valor", min_value=0.0, step=10.0, format="%.2f")
                data  = st.date_input("Data", value=date.today())
                ok = st.form_submit_button("Registrar")

            if ok:
                if valor <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    try:
                        with get_db() as db:
                            uid = st.session_state.auth["user_id"] if "auth" in st.session_state else st.session_state.user.id
                            mid = create_income(db, uid, float(valor), data.isoformat())
                            split_income_by_buckets(db, uid, mid, float(valor))
                            db.commit()
                        st.success("✅ Registrado e dividido nos baldes.")
                        st.toast("💸 Registrado!", icon="💸")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Falha ao registrar: {e}")
                        db.close()
                    st.cache_data.clear()
                    st.rerun()
                    
                    if valor <= 0:
                        st.error("Informe um valor maior que zero.")
                    else:
                        with get_db() as new_db:  # Nova conexão
                            # Tenta distribuir o valor
                            if distribuir_por_baldes(new_db, user.id, valor, desc, date.today(), tipo):
                                st.success(f"✅ {tipo} de {money_br(valor)} distribuída entre baldes.")
                                st.toast("Transação registrada!", icon="💰")
                                st.cache_data.clear()  # Limpa cache para atualizar valores
                                time.sleep(0.5)  # Pequena pausa para feedback
                                st.rerun()
                            else:
                                st.error("Selecione um balde para a despesa.")


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
                
                def delete_movement(db, movement_id: int):
                    """Delete a movement with proper error handling"""
                    movement = db.get(Movement, movement_id)
                    if not movement:
                        return False
                    
                    # Update bucket balance before deleting
                    bucket = db.get(Bucket, movement.bucket_id)
                    if bucket:
                        amount = movement.amount
                        if movement.kind == "Despesa":
                            amount = -amount
                        bucket.balance -= amount
                    
                    db.delete(movement)
                    db.commit()
                    return True

                # Mobile-friendly movements table with pagination
                st.subheader("📝 Histórico de Movimentações")

                # Pagination controls
                items_per_page = 50
                if 'movement_page' not in st.session_state:
                    st.session_state.movement_page = 1

                movements_page, total_movements = load_user_movements(
                    user.id, 
                    page=st.session_state.movement_page,
                    per_page=items_per_page
                )

                df_movements = pd.DataFrame([
                    {
                        "ID": m.id,
                        "Data": date_br(m.date),
                        "Descrição": m.description,
                        "Tipo": "➕ Receita" if m.kind == "Receita" else "➖ Despesa",
                        "Valor": money_br(m.amount if m.kind == "Receita" else -m.amount),
                        "Balde": next((b.name for b in buckets if b.id == m.bucket_id), ""),
                        "Excluir": False
                    }
                    for m in movements_page
                ])

                # Show data editor with delete option
                edited = st.data_editor(
                    df_movements,
                    use_container_width=True,
                    num_rows="fixed",
                    hide_index=True,
                    disabled=["ID", "Data", "Descrição", "Tipo", "Valor", "Balde"],
                    key=f"movements_editor_{st.session_state.movement_page}"
                )

                # Pagination controls
                total_pages = (total_movements + items_per_page - 1) // items_per_page
                if total_pages > 1:
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.session_state.movement_page > 1:
                            if st.button("⬅️ Anterior"):
                                st.session_state.movement_page -= 1
                                st.rerun()
                    with col2:
                        st.write(f"Página {st.session_state.movement_page} de {total_pages}")
                    with col3:
                        if st.session_state.movement_page < total_pages:
                            if st.button("Próxima ➡️"):
                                st.session_state.movement_page += 1
                                st.rerun()

                # Process deletions
                ids_para_excluir = edited.loc[edited["Excluir"] == True, "ID"].tolist()
                if ids_para_excluir:
                    if st.button(f"🗑️ Excluir movimento(s) ({len(ids_para_excluir)})", type="secondary"):
                        ok, fail = 0, 0
                        for mid in ids_para_excluir:
                            try:
                                if delete_movement(db, int(mid)):
                                    ok += 1
                                else:
                                    fail += 1
                            except Exception:
                                db.rollback()
                                fail += 1
                        if ok:
                            st.success(f"{ok} movimento(s) excluído(s).")
                        if fail:
                            st.warning(f"{fail} não encontrado(s) ou já removido(s).")
                        st.cache_data.clear()
                        st.rerun()

                
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
                
                def delete_bill(db, bill_id: int):
                    """Delete a bill with proper error handling"""
                    bill = db.get(Bill, bill_id)
                    if not bill:
                        return False
                    db.delete(bill)
                    db.commit()
                    return True

                # DataFrame optimized for mobile
                df_bills = pd.DataFrame([
                    {
                        "ID": b.id,
                        "Prioridade": "🔴" if b.is_critical else "⚪",
                        "Descrição": b.title,
                        "Valor": money_br(b.amount),
                        "Data": date_br(b.due_date),
                        "Pago": b.paid,
                        "Excluir": False
                    }
                    for b in bills
                ])
                
                # Show compact data editor
                st.subheader("📅 Próximos Vencimentos")
                
                edited = st.data_editor(
                    df_bills,
                    use_container_width=True,
                    num_rows="fixed",
                    hide_index=True,
                    key="bills_editor",
                    disabled=["ID", "Prioridade", "Descrição", "Valor", "Data"],
                )

                # Process payments
                pagamentos = df_bills[~df_bills["Pago"]].index[edited["Pago"] & ~df_bills["Pago"]]
                if not pagamentos.empty:
                    for idx in pagamentos:
                        bill_id = df_bills.iloc[idx]["ID"]
                        bill = db.get(Bill, bill_id)
                        if bill:
                            bill.paid = True
                            db.commit()
                            st.success(f"✅ {bill.title} marcada como paga!")
                            st.cache_data.clear()
                            st.rerun()

                # Process deletions
                ids_para_excluir = edited.loc[edited["Excluir"] == True, "ID"].tolist()
                if ids_para_excluir:
                    if st.button(f"🗑️ Excluir selecionada(s) ({len(ids_para_excluir)})", type="secondary"):
                        ok, fail = 0, 0
                        for bid in ids_para_excluir:
                            try:
                                if delete_bill(db, int(bid)):
                                    ok += 1
                                else:
                                    fail += 1
                            except Exception:
                                db.rollback()
                                fail += 1
                        if ok:
                            st.success(f"{ok} conta(s) excluída(s).")
                        if fail:
                            st.warning(f"{fail} não encontrada(s) ou já removida(s).")
                        st.cache_data.clear()
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
                    safe_dataframe(df_atrasadas)
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
                    safe_dataframe(df_risco)
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

