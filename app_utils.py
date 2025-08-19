import streamlit as st
import pandas as pd
from datetime import date, timedelta
from models import Movement
from db_helpers import get_profile, load_buckets

def safe_dataframe(df, **kwargs):
    """st.dataframe sem column_config (evita JSON serializable error no Streamlit Cloud)."""
    kwargs.pop("column_config", None)
    st.dataframe(df, use_container_width=True, **kwargs)

def distribute_by_buckets(
    db, user_id: int, buckets: list, valor: float, tipo: str, data_mov: date, desc: str,
    auto: bool = True, bucket_id: int | None = None
):
    """Divide Entrada/Despesa por percentuais ou lança num balde específico."""
    if valor <= 0:
        st.error("Informe um valor maior que zero.")
        return

    if auto or not bucket_id:
        total_percent = sum(max(b.percent, 0) for b in buckets)
        if total_percent <= 0:
            st.error("Configure percentuais dos baldes em 'Baldes'.")
            return
        for b in buckets:
            part = round(valor * (b.percent / total_percent), 2)
            db.add(Movement(
                user_id=user_id, bucket_id=b.id,
                kind=("Receita" if tipo == "Entrada" else "Despesa"),
                amount=part, description=f"{desc} (auto {b.percent:.1f}%)",
                date=data_mov
            ))
            if tipo == "Entrada": b.balance += part
            else: b.balance -= part
    else:
        b = next((x for x in buckets if x.id == bucket_id), None)
        if not b:
            st.error("Balde inválido.")
            return
        db.add(Movement(
            user_id=user_id, bucket_id=b.id,
            kind=("Receita" if tipo == "Entrada" else "Despesa"),
            amount=valor, description=desc, date=data_mov
        ))
        b.balance += (valor if tipo == "Entrada" else -valor)

    db.commit()
    st.cache_data.clear()
    st.toast("Lançamento salvo!", icon="✅")
    st.rerun()

def dias_do_mes(d: date) -> int:
    """Retorna o número de dias no mês da data informada."""
    from calendar import monthrange
    return monthrange(d.year, d.month)[1]

def ensure_daily_allocation(db, user):
    """Gera receitas diárias proporcionais aos percentuais desde a última execução."""
    profile = get_profile(db, user.id)
    if not profile.monthly_income:
        return

    today = date.today()
    if not getattr(profile, "last_allocation_date", None):
        # primeira execução: não retroagir demais; começa de ontem
        profile.last_allocation_date = today - timedelta(days=1)

    start = profile.last_allocation_date + timedelta(days=1)
    if start > today:
        return

    buckets = load_buckets(db, user.id)
    total_percent = sum(max(b.percent, 0) for b in buckets)
    if not buckets or total_percent <= 0:
        return

    daily = round(profile.monthly_income / dias_do_mes(today), 2)
    d = start
    while d <= today:
        for b in buckets:
            part = round(daily * (b.percent / total_percent), 2)
            db.add(Movement(
                user_id=user.id, bucket_id=b.id, kind="Receita",
                amount=part, description="Auto diária", date=d
            ))
            b.balance += part
        d += timedelta(days=1)

    profile.last_allocation_date = today
    db.commit()
    st.cache_data.clear()

def daily_budget_for_giants(db, user, buckets):
    """Calcula o orçamento diário disponível para os gigantes."""
    # prioriza buckets com type "giant" (case-insensitive)
    share = sum(b.percent for b in buckets if (b.type or "").lower() == "giant")
    today = date.today()
    if share > 0 and st.session_state.user:
        return (get_profile(db, user.id).monthly_income * (share/100.0)) / dias_do_mes(today)

    prof = get_profile(db, user.id)
    sobrando = max(prof.monthly_income - prof.monthly_expense, 0.0)
    return sobrando / max(dias_do_mes(today), 1)

def celebrate_victory(nome):
    """Exibe animações e mensagens de vitória."""
    st.success(f"🎉 Vitória! Você derrotou **{nome}**!")
    st.balloons()
    st.toast("Meta alcançada!", icon="🎯")
