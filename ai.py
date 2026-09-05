import os
import io
import json
import base64
import pandas as pd
import streamlit as st
from datetime import datetime
from openai import OpenAI
from pypdf import PdfReader
from database import carregar_fatos, carregar_despesas_fixas

@st.cache_resource
def get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("Chave OPENAI_API_KEY não encontrada.")
    return OpenAI(api_key=api_key)

openai_client = get_openai_client()

def transcrever_audio(audio_bytes: bytes) -> str:
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "voice.ogg"
        transcription = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcription.text
    except Exception as e:
        return f"Erro ao transcrever áudio: {str(e)}"

def processar_texto_com_ia(texto: str) -> dict:
    prompt_sistema = """
    Você é a Alice. Analise o texto do usuário e retorne ESTRITAMENTE em JSON:

    1. Se for REGISTRO financeiro efetuado (ex: gastei 50 reais, paguei conta, recebi 5000):
       {"tipo_acao": "registro", "descricao": "nome", "valor": 50.0, "tipo": "despesa", "categoria": "Alimentação"}

    2. Se for uma PERGUNTA/SIMULAÇÃO DE COMPRA ou DUVIDA SE PODE GASTAR (ex: posso comprar um fone de 200?, posso gastar 500 no shopping?, posso comprar um pc em dezembro?):
       {"tipo_acao": "simulacao_compra", "item": "nome do item ou motivo", "valor": 200.0}

    3. Se for para MEMORIZAR um fato permanente:
       {"tipo_acao": "memorizar", "fato": "Descrição do fato"}

    4. Se for BATE-PAPO, DÚVIDA GERAL, PERGUNTA OU PIADA:
       {"tipo_acao": "consulta"}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"}, 
            messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": texto}]
        )
        res = json.loads(response.choices[0].message.content)
        if res.get("tipo_acao") == "registro":
            tipo_orig = str(res.get("tipo", "")).strip().lower()
            res["tipo"] = "receita" if tipo_orig in ["receita", "ganho", "entrada", "lucro"] else "despesa"
        return res
    except Exception:
        return {"tipo_acao": "consulta"}

def processar_imagem_com_ia(image_bytes: bytes) -> dict:
    try:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        prompt_sistema = """
        Analise a imagem e retorne em JSON:
        Se for nota/comprovante legível:
        {"tipo_acao": "registro", "descricao": "Item/Local", "valor": 45.50, "tipo": "despesa", "categoria": "Alimentação"}
        Caso contrário:
        {"tipo_acao": "erro", "mensagem": "Comprovante não identificado."}
        """
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extraia os dados:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"tipo_acao": "erro", "mensagem": f"Erro visual: {str(e)}"}

def analisar_simulacao_compra(df_trans: pd.DataFrame, item: str, valor_compra: float, texto_usuario: str) -> str:
    fatos_longo_prazo = carregar_fatos()
    
    # Saldo atual efetivado
    rec_real = df_trans[df_trans['tipo'] == 'receita']['valor'].sum() if not df_trans.empty else 0.0
    des_real = abs(df_trans[df_trans['tipo'] == 'despesa']['valor'].sum()) if not df_trans.empty else 0.0
    saldo_atual = rec_real - des_real

    # Projeção de fluxo fixo mensal
    try:
        df_fixas = carregar_despesas_fixas()
        rec_fixa = df_fixas[df_fixas['tipo'] == 'receita']['valor'].sum() if not df_fixas.empty else 0.0
        des_fixa = abs(df_fixas[df_fixas['tipo'] == 'despesa']['valor'].sum()) if not df_fixas.empty else 0.0
        folga_mensal = rec_fixa - des_fixa
    except Exception:
        folga_mensal = 0.0

    mes_atual = datetime.now().month
    meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    data_atual_str = f"{meses_nomes[mes_atual - 1]} de {datetime.now().year}"

    prompt_sistema = f"""
    Você é a Alice, uma assistente pessoal financeira.
    
    [DADOS FINANCEIROS]
    • Data Atual: {data_atual_str}
    • Saldo Atual na Conta: R$ {saldo_atual:,.2f}
    • Folga Mensal (Receitas Fixas - Despesas Fixas): R$ {folga_mensal:,.2f}
    • Conhecimento Prévio: {fatos_longo_prazo}

    [MISSÃO]
    O usuário quer simular a compra abaixo.
    • Mensagem: "{texto_usuario}"
    • Item: {item}
    • Valor: R$ {valor_compra:,.2f}

    REGRAS DE RESPOSTA:
    1. Identifique o prazo pela mensagem (ex: "em dezembro").
    2. Importante: Você não deve inventar cálculos.
       - Mês atual: {mes_atual}
       - Calcule mentalmente a diferença de meses entre o mês atual e o mês citado.
       - Multiplique a diferença de meses pelo valor da Folga Mensal (R$ {folga_mensal:,.2f}).
       - Some esse resultado ao Saldo Atual (R$ {saldo_atual:,.2f}) para encontrar o Caixa Total Previsto.
    3. Compare o Caixa Total Previsto com o Valor da Compra (R$ {valor_compra:,.2f}).
    4. Informe explicitamente o Caixa Total Previsto que você encontrou e se o valor é suficiente ou quanto faltará.
    5. Seja direta, natural e não exiba passo a passo matemático chato.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt_sistema}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao analisar compra: {str(e)}"

def consultar_alice(df_trans: pd.DataFrame, historico_mensagens: list, texto_atual: str) -> str:
    fatos_longo_prazo = carregar_fatos()
    rec_real = df_trans[df_trans['tipo'] == 'receita']['valor'].sum() if not df_trans.empty else 0.0
    des_real = abs(df_trans[df_trans['tipo'] == 'despesa']['valor'].sum()) if not df_trans.empty else 0.0
    saldo_disponivel = rec_real - des_real

    prompt_sistema = f"""
    Você é a Alice, uma assistente pessoal e parceira inteligente, bem-humorada e direta.
    
    [CONTEXTO SILENCIOSO]
    • Saldo Efetivado Atual: R$ {saldo_disponivel:,.2f}
    • Conhecimento Prévio: {fatos_longo_prazo}

    REGRAS DE RESPOSTA:
    1. RESPONDA DIRETAMENTE AO TEXTO DO USUÁRIO. Se ele pedir uma piada, conte uma piada. Se perguntar o que você faz, explique de forma sucinta.
    2. NUNCA responda com saudações genéricas como "Oi, como posso te ajudar?".
    3. Mantenha o tom natural, conciso e amigável.
    """
    
    mensagens_api = [{"role": "system", "content": prompt_sistema}] + historico_mensagens
    mensagens_api.append({"role": "user", "content": texto_atual})
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=mensagens_api,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao gerar resposta da Alice: {str(e)}"