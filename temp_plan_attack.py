elif menu == "Plano de Ataque":
    st.header("🎯 Plano de Ataque")
    
    # Mobile-optimized styles
    st.markdown("""
        <style>
            .giant-card {
                background: white;
                padding: 1rem;
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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
                padding: 0.375rem;
                border: none;
                background: none;
                cursor: pointer;
                transition: opacity 0.2s;
            }
            .giant-card__button:hover {
                opacity: 0.8;
            }
            .giant-card__button--edit {
                color: #4B5563;
            }
            .giant-card__button--delete {
                color: #EF4444;
            }
            .confirm-delete {
                background: #FEF2F2;
                border: 1px solid #EF4444;
                padding: 1rem;
                border-radius: 0.5rem;
                margin: 1rem 0;
            }
            .confirm-delete__title {
                color: #EF4444;
                font-size: 1rem;
                margin: 0 0 0.5rem 0;
            }
            @media (max-width: 640px) {
                .giant-card {
                    padding: 0.75rem;
                }
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Lista de Giants existentes
    if giants:
        # Inicializar estado de confirmação
        if 'confirmar_exclusao_giant' not in st.session_state:
            st.session_state.confirmar_exclusao_giant = {}
            
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
                "Meta Semanal": money_br(giant.weekly_goal) if giant.weekly_goal else "N/A",
                "Status": "🏆 Derrotado!" if giant.status == "defeated" else ("✅ Meta Atingida" if meta_atingida else "⚔️ Em Batalha"),
                "Taxa": f"{giant.interest_rate:.1f}%" if giant.interest_rate else "0%"
            })
        
        # Converter para DataFrame e ordenar
        df_giants = pd.DataFrame(giant_data)
        
        # Exibir cada gigante como um card
        for _, giant in df_giants.iterrows():
            st.markdown(f"""
                <div class='giant-card'>
                    <div class='giant-card__header'>
                        <h3 class='giant-card__title'>{giant['Nome']} {giant['Status']}</h3>
                        <div class='giant-card__controls'>
                            <button class='giant-card__button giant-card__button--delete' 
                                    onclick="document.dispatchEvent(new CustomEvent('delete_giant', {{detail: {giant['ID']}}}))"
                                    title="Excluir Gigante">
                                🗑️
                            </button>
                        </div>
                    </div>
                    <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.5rem;'>
                        <div>
                            <small style='color: #6B7280;'>Total:</small><br>
                            <strong>{money_br(giant['Total'])}</strong>
                        </div>
                        <div>
                            <small style='color: #6B7280;'>Pago:</small><br>
                            <strong>{money_br(giant['Pago'])}</strong>
                        </div>
                        <div>
                            <small style='color: #6B7280;'>Restante:</small><br>
                            <strong>{money_br(giant['Restante'])}</strong>
                        </div>
                        <div>
                            <small style='color: #6B7280;'>Meta Semanal:</small><br>
                            <strong>{giant['Meta Semanal']}</strong>
                        </div>
                    </div>
                    <div style='margin-top: 0.5rem;'>
                        <div class='stProgress' style='height: 0.5rem; background: #E5E7EB; border-radius: 0.25rem;'>
                            <div style='width: {giant["Progresso"]*100}%; height: 100%; background: #10B981; border-radius: 0.25rem;'></div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Modal de confirmação de exclusão
            if st.session_state.confirmar_exclusao_giant.get(giant['ID'], False):
                st.markdown(f"""
                    <div class='confirm-delete'>
                        <h4 class='confirm-delete__title'>⚠️ Confirmar Exclusão</h4>
                        <p style='margin: 0 0 1rem 0;'>Tem certeza que deseja excluir o gigante {giant['Nome']}? Esta ação não pode ser desfeita.</p>
                    </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Sim, excluir", key=f"confirm_del_{giant['ID']}"):
                        try:
                            giant_obj = db.query(Giant).get(giant['ID'])
                            if giant_obj:
                                # Primeiro excluir os pagamentos
                                db.query(GiantPayment).filter_by(giant_id=giant['ID']).delete()
                                # Depois excluir o gigante
                                db.delete(giant_obj)
                                db.commit()
                                st.success(f"Gigante {giant['Nome']} excluído com sucesso!")
                                del st.session_state.confirmar_exclusao_giant[giant['ID']]
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {str(e)}")
                            db.rollback()
                with col2:
                    if st.button("❌ Não, cancelar", key=f"cancel_del_{giant['ID']}"):
                        del st.session_state.confirmar_exclusao_giant[giant['ID']]
                        st.rerun()
            
            # Form de aporte
            with st.expander(f"💰 Adicionar Aporte para {giant['Nome']}", expanded=False):
                with st.form(f"aporte_giant_{giant['ID']}", clear_on_submit=True):
                    col1, col2, col3 = st.columns([2,2,1])
                    with col1:
                        valor_aporte = st.number_input("Valor", min_value=0.0, step=50.0, format="%.2f")
                    with col2:
                        obs_aporte = st.text_input("Observação", placeholder="Opcional")
                    with col3:
                        data_aporte = st.date_input("Data", value=date.today())
                    
                    if st.form_submit_button("💰 Registrar", use_container_width=True):
                        if valor_aporte > 0:
                            giant_obj = db.query(Giant).get(giant['ID'])
                            if giant_obj:
                                aporte = GiantPayment(
                                    user_id=user.id,
                                    giant_id=giant['ID'],
                                    amount=valor_aporte,
                                    date=data_aporte,
                                    note=obs_aporte
                                )
                                db.add(aporte)
                                
                                # Verificar se derrotou o gigante
                                total_pago_atual = giant['Pago'] + valor_aporte
                                if total_pago_atual >= giant['Total']:
                                    giant_obj.status = "defeated"
                                    st.balloons()
                                
                                db.commit()
                                st.success("✅ Aporte registrado com sucesso!")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.error("⚠️ Informe um valor maior que zero")
