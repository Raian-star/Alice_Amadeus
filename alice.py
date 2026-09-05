import os
import streamlit as st

# 1. CONFIGURAÇÃO DA PÁGINA (Sempre no topo antes de renderizar)
st.set_page_config(
    page_title="Alice - Painel ADM",
    page_icon="alice.png" if os.path.exists("alice.png") else "👩‍💼",
    layout="wide"
)

# 2. IMPORTS PRINCIPAIS TRATADOS
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from ui import aplicar_estilo_css, autenticar_usuario, ALICE_IMG_PATH, ALICE_B64
from database import (
    carregar_dados, registrar_transacao, 
    carregar_fatos, salvar_fato, carregar_despesas_fixas, 
    salvar_despesa_fixa, deletar_despesa_fixa, processar_despesas_fixas_mes_atual,
    carregar_fatos_detalhados, deletar_fato, gerar_excel_bytes, gerar_pdf_bytes
)

# 3. APLICA ESTILOS E VALIDA AUTENTICAÇÃO
aplicar_estilo_css()

if not autenticar_usuario():
    st.stop()

# Tenta rodar a rotina de despesas fixas do mês sem travar o painel
try:
    processar_despesas_fixas_mes_atual()
except Exception as e:
    st.sidebar.warning(f"Aviso de sincronização: {e}")

# 4. SIDEBAR
with st.sidebar:
    avatar_sidebar = f'<img src="{ALICE_B64}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;">' if ALICE_B64 else '👩‍💼'
    st.markdown(f"<div style='display:flex; align-items:center; gap:12px; margin-bottom:20px;'>{avatar_sidebar} <div><h4 style='margin:0;'>Alice AI</h4><span style='color:#22c55e; font-size:12px;'>● Online</span></div></div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**🧠 Memória Resumida**")
    try:
        st.caption(carregar_fatos())
    except Exception:
        st.caption("Sem memórias gravadas.")
    st.divider()
    if st.button("🚪 Sair do Painel"):
        st.session_state.autenticado = False
        st.rerun()

# 5. CABEÇALHO
avatar_header = f'<img src="{ALICE_B64}" class="alice-avatar-img">' if ALICE_B64 else '<div style="font-size: 36px;">👩‍💼</div>'

st.markdown(f"""
    <style>
        .alice-header-container {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
        }}
        .alice-avatar-img {{
            width: 60px;
            height: 60px;
            min-width: 60px;
            min-height: 60px;
            border-radius: 50%;
            object-fit: cover;
            flex-shrink: 0 !important;
            border: 3px solid #6366f1;
            box-shadow: 0 4px 8px rgba(99,102,241,0.2);
        }}
        .alice-header-title {{
            margin: 0;
            padding: 0;
            color: #0f172a;
            font-size: 26px;
            font-weight: 800;
            line-height: 1.25;
        }}
        .alice-header-sub {{
            margin: 3px 0 0 0;
            color: #64748b;
            font-size: 14px;
        }}
        
        @media (max-width: 640px) {{
            .alice-header-container {{ gap: 12px; margin-bottom: 12px; }}
            .alice-avatar-img {{ width: 46px !important; height: 46px !important; min-width: 46px !important; min-height: 46px !important; }}
            .alice-header-title {{ font-size: 18px !important; }}
            .alice-header-sub {{ font-size: 11px !important; }}
            button[data-baseweb="tab"] {{ padding: 6px 10px !important; font-size: 13px !important; }}
        }}
    </style>
    <div class="alice-header-container">
        <div>{avatar_header}</div>
        <div>
            <h1 class="alice-header-title">Alice - Painel Administrativo</h1>
            <p class="alice-header-sub">Gestão Financeira e Controle de Conhecimento</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# 6. ABAS PRINCIPAIS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "➕ Lançamento Direto", "📌 Lançamentos Recorrentes", "🧠 Cérebro", "📱 Status Bot"])

# ABA 1: DASHBOARD FINANCEIRO PREDITIVO
with tab1:
    df_trans = carregar_dados()
    df_fixas = carregar_despesas_fixas()
    
    hoje = date.today()
    mes_atual_str = hoje.strftime("%Y-%m")
    
    v_real, v_proj, v_futuro = st.tabs(["💵 Realizado (Hoje)", "📈 Projetado (Mês Atual)", "🔮 Projeção Futura"])
    
    # VISÃO 1: REALIZADO ATÉ HOJE
    with v_real:
        st.subheader("💵 Saldo Realizado (Até Hoje)")
        st.caption("Apenas movimentações financeiras efetivadas no banco até o momento.")
        
        if not df_trans.empty:
            df_trans['data_dt'] = pd.to_datetime(df_trans['data']).dt.date
            df_real = df_trans[df_trans['data_dt'] <= hoje].copy()
            
            rec_real = df_real[df_real['tipo'] == 'receita']['valor'].sum() if not df_real.empty else 0.0
            des_real = abs(df_real[df_real['tipo'] == 'despesa']['valor'].sum()) if not df_real.empty else 0.0
            saldo_real = rec_real - des_real
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Entradas Reais", f"R$ {rec_real:,.2f}")
            c2.metric("Saídas Reais", f"R$ {des_real:,.2f}")
            c3.metric("Saldo Disponível Hoje", f"R$ {saldo_real:,.2f}")
            
            st.divider()
            c_graf, c_tab = st.columns([1.2, 1.8])
            with c_graf:
                df_desp_real = df_real[df_real['tipo'] == 'despesa'].copy()
                if not df_desp_real.empty:
                    df_desp_real['valor_abs'] = df_desp_real['valor'].abs()
                    fig = px.pie(df_desp_real, values='valor_abs', names='categoria', title="Gastos Efetivados por Categoria")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Nenhuma despesa efetuada até o momento.")
            with c_tab:
                st.markdown("**Histórico de Lançamentos Efetivados**")
                st.dataframe(df_real[['data', 'descricao', 'categoria', 'tipo', 'valor']], hide_index=True, use_container_width=True)
        else:
            st.info("Nenhuma transação cadastrada até o momento.")

    # VISÃO 2: PROJETADO DO MÊS ATUAL
    with v_proj:
        st.subheader(f"📈 Projeção Consolidada ({hoje.strftime('%m/%Y')})")
        st.caption("Soma do que já aconteceu + lançamentos fixos/recorrentes previstos para o restante do mês.")
        
        df_mes = pd.DataFrame()
        if not df_trans.empty:
            df_trans['mes_ano'] = pd.to_datetime(df_trans['data']).dt.strftime('%Y-%m')
            df_mes = df_trans[df_trans['mes_ano'] == mes_atual_str].copy()
            
        rec_mes_real = df_mes[df_mes['tipo'] == 'receita']['valor'].sum() if not df_mes.empty else 0.0
        des_mes_real = abs(df_mes[df_mes['tipo'] == 'despesa']['valor'].sum()) if not df_mes.empty else 0.0
        
        rec_pendente = 0.0
        des_pendente = 0.0
        if not df_fixas.empty:
            if "tipo" not in df_fixas.columns:
                df_fixas["tipo"] = "despesa"
            
            lancados_este_mes = set(df_mes['descricao'].unique()) if not df_mes.empty else set()
            
            for _, fixo in df_fixas.iterrows():
                marcador = f"[FIXO] {fixo['descricao']}"
                if marcador not in lancados_este_mes:
                    val = float(fixo['valor'])
                    if fixo['tipo'] == 'receita':
                        rec_pendente += val
                    else:
                        des_pendente += val
                        
        rec_total_proj = rec_mes_real + rec_pendente
        des_total_proj = des_mes_real + des_pendente
        saldo_proj = rec_total_proj - des_total_proj
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Receita Total Prevista", f"R$ {rec_total_proj:,.2f}", delta=f"+ R$ {rec_pendente:,.2f} pendente" if rec_pendente > 0 else None)
        c2.metric("Despesa Total Prevista", f"R$ {des_total_proj:,.2f}", delta=f"- R$ {des_pendente:,.2f} pendente" if des_pendente > 0 else None, delta_color="inverse")
        c3.metric("Saldo Previsto no Fim do Mês", f"R$ {saldo_proj:,.2f}")
        
        st.divider()
        st.markdown("##### 🔮 Resumo da Projeção Mensal")
        st.write(f"- **Realizado até hoje:** Entradas R$ {rec_mes_real:,.2f} | Saídas R$ {des_mes_real:,.2f}")
        st.write(f"- **Pendente de vencimento/recebimento:** Entradas R$ {rec_pendente:,.2f} | Saídas R$ {des_pendente:,.2f}")

    # VISÃO 3: PROJEÇÃO FUTURA (FÓRMULA DIRETA DE CAIXA CONSIDERANDO DATA_FIM)
    with v_futuro:
        st.subheader("🔮 Projeção para Meses Futuros")
        st.caption("Acompanhe o fluxo financeiro estimado para os próximos meses de forma direta.")
        
        col_m, col_a = st.columns(2)
        with col_m:
            mes_sel = st.selectbox("Selecione o Mês:", list(range(1, 13)), index=(hoje.month % 12))
        with col_a:
            ano_sel = st.selectbox("Selecione o Ano:", [hoje.year, hoje.year + 1], index=0)
            
        data_alvo = date(ano_sel, mes_sel, 1)
        
        # 1. SALDO ACUMULADO ATÉ O MÊS ANTERIOR (Realizado)
        saldo_acumulado_inicial = 0.0
        if not df_trans.empty:
            df_trans['data_dt'] = pd.to_datetime(df_trans['data']).dt.date
            trans_passadas = df_trans[df_trans['data_dt'] < date(hoje.year, hoje.month, 1)]
            rec_hist = trans_passadas[trans_passadas['tipo'] == 'receita']['valor'].sum()
            des_hist = abs(trans_passadas[trans_passadas['tipo'] == 'despesa']['valor'].sum())
            saldo_acumulado_inicial = rec_hist - des_hist

        # 2. CÁLCULO ITERATIVO DA FOLGA ATÉ O MÊS ALVO
        inicio_mes_atual = date(hoje.year, hoje.month, 1)
        saldo_final_previsto = saldo_acumulado_inicial
        
        if not df_fixas.empty and 'data_fim' not in df_fixas.columns:
            df_fixas['data_fim'] = None
            
        curr = inicio_mes_atual
        folga_mensal_alvo = 0.0
        rec_futura = 0.0
        des_futura = 0.0
        
        while curr <= data_alvo:
            folga_deste_mes = 0.0
            rec_este_mes = 0.0
            des_este_mes = 0.0
            
            if not df_fixas.empty:
                for _, row in df_fixas.iterrows():
                    valido = True
                    data_fim_str = row.get('data_fim')
                    
                    if pd.notna(data_fim_str) and data_fim_str:
                        try:
                            data_fim_obj = datetime.strptime(str(data_fim_str), "%Y-%m-%d").date()
                            if curr.year > data_fim_obj.year or (curr.year == data_fim_obj.year and curr.month > data_fim_obj.month):
                                valido = False
                        except ValueError:
                            pass
                            
                    if valido:
                        valor = float(row['valor'])
                        tipo = row.get('tipo', 'despesa')
                        if tipo == 'receita':
                            folga_deste_mes += valor
                            rec_este_mes += valor
                        else:
                            folga_deste_mes -= abs(valor)
                            des_este_mes += abs(valor)
            
            saldo_final_previsto += folga_deste_mes
            
            if curr == data_alvo:
                folga_mensal_alvo = folga_deste_mes
                rec_futura = rec_este_mes
                des_futura = des_este_mes
                
            curr += relativedelta(months=1)

        # 3. FÓRMULA DIRETA (2 CARTÕES DE DESTAQUE)
        c1, c2 = st.columns(2)
        c1.metric(f"Folga Financeira do Mês ({mes_sel:02d}/{ano_sel})", f"R$ {folga_mensal_alvo:,.2f}")
        c2.metric(f"Caixa Total Previsto em Conta", f"R$ {saldo_final_previsto:,.2f}", delta=f"R$ {saldo_acumulado_inicial:,.2f} acumulado real inicial")

        # 4. DETALHAMENTO EXPANDÍVEL (Apenas itens válidos no mês alvo)
        with st.expander("🔍 Ver Detalhamento dos Lançamentos Fixos Válidos no Mês"):
            col_rec, col_des = st.columns(2)
            
            df_exibicao = pd.DataFrame()
            if not df_fixas.empty:
                validos_idx = []
                for idx, row in df_fixas.iterrows():
                    v = True
                    dfim = row.get('data_fim')
                    if pd.notna(dfim) and dfim:
                        try:
                            dobj = datetime.strptime(str(dfim), "%Y-%m-%d").date()
                            if data_alvo.year > dobj.year or (data_alvo.year == dobj.year and data_alvo.month > dobj.month):
                                v = False
                        except ValueError:
                            pass
                    if v:
                        validos_idx.append(idx)
                df_exibicao = df_fixas.loc[validos_idx]

            with col_rec:
                st.markdown(f"**Entradas Fixas Previstas:** R$ {rec_futura:,.2f}")
                if not df_exibicao.empty:
                    df_rec = df_exibicao[df_exibicao['tipo'] == 'receita']
                    if not df_rec.empty:
                        st.dataframe(df_rec[['descricao', 'valor', 'dia_vencimento']], hide_index=True, use_container_width=True)
            with col_des:
                st.markdown(f"**Saídas Fixas Previstas:** R$ {des_futura:,.2f}")
                if not df_exibicao.empty:
                    df_desp = df_exibicao[df_exibicao['tipo'] == 'despesa']
                    if not df_desp.empty:
                        st.dataframe(df_desp[['descricao', 'valor', 'dia_vencimento']], hide_index=True, use_container_width=True)

        st.divider()
        col_exp_pdf, col_exp_excel = st.columns(2)
        with col_exp_pdf:
            pdf_data = gerar_pdf_bytes(df_trans, f"{mes_sel:02d}/{ano_sel}")
            st.download_button("📄 Baixar Relatório PDF", data=pdf_data, file_name=f"relatorio_{mes_sel:02d}_{ano_sel}.pdf", mime="application/pdf", use_container_width=True)
        with col_exp_excel:
            excel_data = gerar_excel_bytes(df_trans)
            st.download_button("📊 Baixar Relatório Excel", data=excel_data, file_name=f"relatorio_{mes_sel:02d}_{ano_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# ABA 2: LANÇAMENTO RÁPIDO
with tab2:
    st.subheader("➕ Lançamento Financeiro Manual")
    st.caption("Insira uma despesa ou receita rapidamente caso não queira usar o Telegram.")
    
    with st.form("form_manual_adm", clear_on_submit=True):
        col_desc, col_val = st.columns([2, 1])
        with col_desc:
            desc_input = st.text_input("Descrição:", placeholder="Ex: Mercado mensal ou Pagamento Projeto X")
        with col_val:
            val_input = st.number_input("Valor (R$):", min_value=0.01, step=10.0)
            
        col_cat, col_tipo, col_data = st.columns(3)
        with col_cat:
            cat_input = st.selectbox("Categoria:", ["Alimentação", "Moradia", "Transporte", "Saúde", "Lazer", "Assinaturas", "Educação", "Investimentos", "Outros"])
        with col_tipo:
            tipo_input = st.selectbox("Tipo:", ["despesa", "receita"])
        with col_data:
            data_input = st.date_input("Data:", datetime.now().date())
            
        btn_salvar = st.form_submit_button("Lançar Transação", type="primary", use_container_width=True)
        if btn_salvar and desc_input:
            registrar_transacao(desc_input, val_input, cat_input, tipo_input, str(data_input))
            st.success(f"✅ Transação '{desc_input}' lançada com sucesso!")
            st.rerun()

# ABA 3: FINANÇAS RECORRENTES (RECEITAS E DESPESAS)
with tab3:
    st.subheader("📌 Gerenciador de Lançamentos Recorrentes")
    st.caption("Cadastre seus salários, rendas fixas e despesas mensais recorrentes.")
    
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("**Cadastrar Novo Lançamento Fixo**")
        with st.form("form_fixos", clear_on_submit=True):
            desc = st.text_input("Descrição:", placeholder="Ex: Salário, Aluguel, Netflix")
            val = st.number_input("Valor mensal (R$):", min_value=0.01, step=50.0)
            
            tipo_fixo = st.selectbox("Tipo de Lançamento:", ["despesa", "receita"], format_func=lambda x: "🔴 Despesa (Saída)" if x == "despesa" else "🟢 Receita (Entrada/Salário)")
            cat = st.selectbox("Categoria:", ["Salário", "Investimentos", "Moradia", "Assinaturas", "Saúde", "Educação", "Transporte", "Outros"])
            dia = st.number_input("Dia do Vencimento / Recebimento:", 1, 31, 5)
            
            if st.form_submit_button("Salvar Recorrência", type="primary", use_container_width=True):
                if desc:
                    salvar_despesa_fixa(desc, val, cat, int(dia), tipo_fixo)
                    st.success(f"✅ Lançamento fixo '{desc}' cadastrado com sucesso!")
                    st.rerun()
    with c2:
        st.markdown("**Lançamentos Programados**")
        df_fixas = carregar_despesas_fixas()
        
        if not df_fixas.empty:
            if "tipo" not in df_fixas.columns:
                df_fixas["tipo"] = "despesa"
                
            rec_df = df_fixas[df_fixas["tipo"] == "receita"]
            desp_df = df_fixas[df_fixas["tipo"] == "despesa"]
            
            st.markdown("##### 🟢 Entradas Fixas (Salários/Rendas)")
            if not rec_df.empty:
                for _, item in rec_df.iterrows():
                    c_info, c_btn = st.columns([4, 1])
                    with c_info:
                        st.success(f"💰 **{item['descricao']}** — R$ {item['valor']:.2f} (Dia {item['dia_vencimento']}) [{item['categoria']}]")
                    with c_btn:
                        if st.button("🗑️", key=f"del_rec_{item['id']}"):
                            deletar_despesa_fixa(item['id'])
                            st.rerun()
            else:
                st.caption("Nenhuma receita fixa cadastrada.")
                
            st.markdown("##### 🔴 Saídas Fixas (Despesas Recorrentes)")
            if not desp_df.empty:
                for _, item in desp_df.iterrows():
                    c_info, c_btn = st.columns([4, 1])
                    with c_info:
                        data_fim_txt = f" | 🏁 Término: {item['data_fim']}" if pd.notna(item.get('data_fim')) and item.get('data_fim') else ""
                        st.info(f"📌 **{item['descricao']}** — R$ {item['valor']:.2f} (Dia {item['dia_vencimento']}) [{item['categoria']}]{data_fim_txt}")
                    with c_btn:
                        if st.button("🗑️", key=f"del_desp_{item['id']}"):
                            deletar_despesa_fixa(item['id'])
                            st.rerun()
            else:
                st.caption("Nenhuma despesa fixa cadastrada.")
        else:
            st.write("Nenhum lançamento recorrente programado.")

# ABA 4: CÉREBRO DA ALICE
with tab4:
    st.subheader("🧠 Base de Conhecimento da Alice")
    st.caption("Gerencie os fatos, preferências e regras que a Alice memorizou sobre você.")
    
    col_novo_fato, col_lista_fatos = st.columns([1, 1.5])
    
    with col_novo_fato:
        st.markdown("**Ensinar Novo Fato Manualmente**")
        novo_fato_txt = st.text_area("O que a Alice deve aprender?", placeholder="Ex: Meu limite de gastos no cartão de crédito é R$ 3.000,00", height=120)
        if st.button("💡 Adicionar ao Cérebro", type="primary", use_container_width=True):
            if novo_fato_txt.strip():
                salvar_fato(novo_fato_txt.strip())
                st.success("Conhecimento gravado!")
                st.rerun()
            else:
                st.warning("Escreva o texto do fato antes de salvar.")
                
    with col_lista_fatos:
        st.markdown("**Conhecimentos Atuais**")
        df_fatos = carregar_fatos_detalhados()
        
        if not df_fatos.empty:
            for _, row in df_fatos.iterrows():
                col_txt, col_del = st.columns([4, 1])
                with col_txt:
                    st.info(f"📌 {row['fato']}")
                with col_del:
                    if st.button("🗑️", key=f"fato_del_{row['id']}"):
                        deletar_fato(row['id'])
                        st.rerun()
        else:
            st.write("Nenhum aprendizado registrado.")

# ABA 5: STATUS DO BOT
with tab5:
    st.subheader("📱 Status e Diagnóstico do Bot do Telegram")
    
    try:
        from bot import iniciar_telegram_bot, obter_logs
        status_ok, msg_status = iniciar_telegram_bot()
        
        col_st, col_btn = st.columns([3, 1])
        with col_st:
            if status_ok:
                st.success(f"🟢 Serviço Ativo: {msg_status}")
            else:
                st.error(f"🔴 Falha no Serviço: {msg_status}")
                
        with col_btn:
            if st.button("🔄 Atualizar Logs", use_container_width=True):
                st.rerun()

        st.markdown("##### 📋 Console de Logs em Tempo Real")
        st.code(obter_logs(), language="text")
    except Exception as e_bot:
        st.error(f"⚠️ Erro ao carregar o módulo do Telegram: {str(e_bot)}")