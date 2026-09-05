import os
import io
import json
import base64
import pandas as pd
import streamlit as st
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

    1. Se for REGISTRO financeiro (ex: gastei 50 reais, paguei conta, recebi 5000):
       {"tipo_acao": "registro", "descricao": "nome", "valor": 50.0, "tipo": "despesa", "categoria": "Alimentação"}

    2. Se for para MEMORIZAR um fato permanente:
       {"tipo_acao": "memorizar", "fato": "Descrição do fato"}

    3. Se for BATE-PAPO, DÚVIDA, PERGUNTA, PIADA OU SIMULAÇÃO:
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
    
    # Monta as mensagens garantindo a presença do texto atual no final
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