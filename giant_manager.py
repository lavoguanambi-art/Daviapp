import streamlit as st
from sqlalchemy.orm import Session
from sqlalchemy import select, text, inspect
from datetime import date, datetime, timedelta
import pandas as pd
import time
from models import Giant, GiantPayment
from utils import money_br, date_br
from text_utils import clean_emoji_text, get_giant_status_text

# Melhorias de Performance e Cache
@st.cache_data(ttl=300)
def get_giant_payments(giant_id):
    with get_db() as db:
        return db.query(GiantPayment).filter_by(giant_id=giant_id).all()

@st.cache_data(ttl=300)
def get_total_paid(giant_id):
    payments = get_giant_payments(giant_id)
    return sum(p.amount for p in payments)

from contextlib import contextmanager

@contextmanager
def tx(db):
    """Gerenciador de contexto para transações seguras."""
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise

def safe_db_operation(db, operation, on_error="Erro na operação"):
    """Executa uma operação no banco com tratamento de erro."""
    try:
        with tx(db):
            operation()
        return True
    except Exception as e:
        st.error(f"{on_error}: {str(e)}")
        return False

def delete_giant_with_confirm(giant_id: int, giant_name: str):
    """Deletar gigante com confirmação"""
    if st.session_state.confirmar_exclusao_giant.get(giant_id, False):
        st.markdown("""
            <div class='confirm-delete'>
                <h4 class='confirm-delete__title'>⚠️ Confirmar Exclusão</h4>
                <p>Esta ação não pode ser desfeita.</p>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Sim, excluir", key=f"confirm_del_{giant_id}"):
                def delete_operation(db):
                    # Primeiro excluir os pagamentos
                    db.query(GiantPayment).filter_by(giant_id=giant_id).delete()
                    # Depois excluir o gigante
                    giant = db.query(Giant).get(giant_id)
                    if giant:
                        db.delete(giant)
                    db.commit()
                    return True
                
                if safe_db_operation(delete_operation):
                    st.success(f"Gigante {giant_name} excluído com sucesso!")
                    del st.session_state.confirmar_exclusao_giant[giant_id]
                    time.sleep(1)
                    st.rerun()
        
        with col2:
            if st.button("❌ Não, cancelar", key=f"cancel_del_{giant_id}"):
                del st.session_state.confirmar_exclusao_giant[giant_id]
                st.rerun()

def get_db():
    """Get database session"""
    from db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def render_giant_card(giant_data, db):
    """Renderizar card do gigante com design otimizado"""
    status_text = clean_emoji_text(giant_data['Status'])
    
    st.markdown(f"""
        <div class='giant-card'>
            <div class='giant-card__header'>
                <h3 class='giant-card__title'>{giant_data['Nome']} {status_text}</h3>
                <div class='giant-card__controls'>
                    <button class='giant-card__button giant-card__button--delete'
                            onclick="document.dispatchEvent(new CustomEvent('delete_giant', {{detail: {giant_data['ID']}}}))"
                            title="Excluir Gigante">
                        Excluir
                    </button>
                </div>
            </div>
            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem;'>
                <div>
                    <small style='color: #6B7280;'>Total:</small><br>
                    <strong>{money_br(giant_data['Total'])}</strong>
                </div>
                <div>
                    <small style='color: #6B7280;'>Pago:</small><br>
                    <strong>{money_br(giant_data['Pago'])}</strong>
                </div>
                <div>
                    <small style='color: #6B7280;'>Restante:</small><br>
                    <strong>{money_br(giant_data['Restante'])}</strong>
                </div>
                <div>
                    <small style='color: #6B7280;'>Meta Semanal:</small><br>
                    <strong>{giant_data['Meta Semanal']}</strong>
                </div>
            </div>
            <div style='margin-top: 0.5rem;'>
                <div class='stProgress' style='height: 0.5rem; background: #E5E7EB; border-radius: 0.25rem;'>
                    <div style='width: {giant_data["Progresso"]*100}%; height: 100%; background: #10B981; border-radius: 0.25rem;'></div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Form de aporte otimizado
    with st.expander(f"Adicionar Aporte para {giant_data['Nome']}", expanded=False):
        with st.form(f"aporte_giant_{giant_data['ID']}", clear_on_submit=True):
            col1, col2, col3 = st.columns([2,2,1])
            with col1:
                valor_aporte = st.number_input("Valor", min_value=0.0, step=50.0, format="%.2f")
            with col2:
                obs_aporte = st.text_input("Observação", placeholder="Opcional")
            with col3:
                data_aporte = st.date_input("Data", value=date.today())
            
            if st.form_submit_button("Registrar Aporte", use_container_width=True):
                if valor_aporte > 0:
                    def add_payment(db):
                        giant = db.query(Giant).get(giant_data['ID'])
                        if giant:
                            aporte = GiantPayment(
                                user_id=st.session_state.user.id,
                                giant_id=giant_data['ID'],
                                amount=valor_aporte,
                                date=data_aporte,
                                note=obs_aporte
                            )
                            db.add(aporte)
                            
                            # Verificar se derrotou o gigante
                            total_pago_atual = giant_data['Pago'] + valor_aporte
                            if total_pago_atual >= giant_data['Total']:
                                giant.status = "defeated"
                                st.balloons()
                            
                            db.commit()
                            return True
                        return False
                    
                    if safe_db_operation(add_payment):
                        st.success("Aporte registrado com sucesso!")
                        time.sleep(1)
                        st.rerun()
                else:
                        st.error("Informe um valor maior que zero")

def render_plano_ataque(db, giants):
    """Renderizar seção completa do Plano de Ataque"""
    st.header("🎯 Plano de Ataque")
    
    # Estilos otimizados para mobile
    st.markdown("""
        <style>
            .giant-card {
                background: white;
                padding: 1rem;
                border-radius: 0.5rem;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                border: 1px solid #e5e7eb;
                margin: 0.5rem 0;
            }
            .giant-card__header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 0.5rem;
            }
            .giant-card__title {
                margin: 0;
                font-size: 1.125rem;
                color: #111827;
            }
            .giant-card__controls {
                display: flex;
                gap: 0.5rem;
            }
            .giant-card__button {
                padding: 0.5rem;
                border: none;
                background: none;
                cursor: pointer;
                transition: opacity 0.2s;
            }
            .giant-card__button:hover {
                opacity: 0.8;
            }
            .giant-card__button--delete {
                color: #EF4444;
            }
            .confirm-delete {
                background: #FEF2F2;
                border: 1px solid #FCA5A5;
                padding: 1rem;
                border-radius: 0.5rem;
                margin: 0.5rem 0;
            }
            .confirm-delete__title {
                color: #DC2626;
                font-size: 1rem;
                margin: 0 0 0.5rem 0;
            }
            @media (max-width: 640px) {
                .giant-card {
                    padding: 0.75rem;
                }
                .stForm {
                    padding: 0.75rem !important;
                }
                button {
                    min-height: 44px !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)
    
    if giants:
        # Inicializar estado de confirmação
        if 'confirmar_exclusao_giant' not in st.session_state:
            st.session_state.confirmar_exclusao_giant = {}
            
        giant_data = []
        for giant in giants:
            # Usar funções cacheadas para melhor performance
            total_pago = get_total_paid(giant.id)
            restante = giant.total_to_pay - total_pago
            progresso = (total_pago / giant.total_to_pay) if giant.total_to_pay > 0 else 0
            
            ultima_semana = date.today() - timedelta(days=7)
            aportes = get_giant_payments(giant.id)
            depositos_semana = sum(p.amount for p in aportes if p.date >= ultima_semana)
            meta_atingida = depositos_semana >= giant.weekly_goal if giant.weekly_goal else False
            
            giant_data.append({
                "ID": giant.id,
                "Nome": giant.name,
                "Total": giant.total_to_pay,
                "Pago": total_pago,
                "Restante": restante,
                "Progresso": progresso,
                "Meta Semanal": money_br(giant.weekly_goal) if giant.weekly_goal else "N/A",
                "Status": get_giant_status_text(giant.status, meta_atingida),
                "Taxa": f"{giant.interest_rate:.1f}%" if giant.interest_rate else "0%"
            })
        
        # Ordenar gigantes por prioridade e status
        df_giants = pd.DataFrame(giant_data)
        df_giants = df_giants.sort_values(by=['Status', 'Restante'], ascending=[True, False])
        
        # Renderizar cada gigante
        for _, giant in df_giants.iterrows():
            render_giant_card(giant, db)
            
            # Verificar exclusão
            if st.session_state.confirmar_exclusao_giant.get(giant['ID'], False):
                delete_giant_with_confirm(giant['ID'], giant['Nome'])
