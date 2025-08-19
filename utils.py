import locale
from datetime import datetime
from pathlib import Path
import streamlit as st

# Configurar locale para formatação de moeda em pt_BR
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        pass

def money_br(value: float) -> str:
    """Formatar valor monetário no padrão brasileiro"""
    try:
        return locale.currency(value, grouping=True, symbol=True)
    except:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def date_br(value: datetime) -> str:
    """Formatar data no padrão brasileiro"""
    try:
        return value.strftime("%d/%m/%Y")
    except:
        return str(value)

def load_css():
    """Carrega os estilos CSS do arquivo styles.css"""
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
