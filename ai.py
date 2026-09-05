import os
import io
import json
import base64
import re
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
        Analise a imagem financeiro/nota/comprovante e retorne ESTRITAMENTE em JSON:
        
        Se for nota/comprovante/extrato legível:
        {
            "tipo_acao": "registro",
            "descricao": "Item ou Estabelecimento",
            "valor": 45.50,
            "tipo": "despesa", // Ou "receita" (ex: PIX recebido, comprovante de transferência recebida)
            "categoria": "Alimentação" // Categorias: Alimentação, Moradia, Transporte, Saúde, Lazer, Assinaturas, Educação, Investimentos, Salário, Outros
        }
        Caso contrário:
        {"tipo_acao": "erro", "mensagem": "Comprovante não identificado."}
        """
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extraia os dados financeiros:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ]
        )
        res = json.loads(response.choices[0].message.content)
        if res.get("tipo_acao") == "registro":
            tipo_orig = str(res.get("tipo", "")).strip().lower()
            res["tipo"] = "receita" if tipo_orig in ["receita", "ganho", "entrada", "lucro"] else "despesa"
        return res
    except Exception as e:
        return {"tipo_acao": "erro", "mensagem": f"Erro visual: {str(e)}"}

def processar_pdf_com_ia(pdf_bytes: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto_extraido = ""
        for page in reader.pages:
            texto_extraido += page.extract_text() or ""

        if not texto_extraido.strip():
            return {"tipo_acao": "erro", "mensagem": "Não foi possível extrair o texto deste PDF (pode ser uma imagem digitalizada)."}

        prompt_sistema = """
        Você é um assistente financeiro especialista em análise de documentos.
        Analise o texto do PDF e retorne ESTRITAMENTE em JSON:
        
        {
            "tipo_acao": "registro",
            "descricao": "Nome do estabelecimento, pagador ou emissor",
            "valor": 150.00,
            "tipo": "despesa",  
            "categoria": "Outros"
        }
        
        REGRAS DE CLASSIFICAÇÃO PARA 'tipo':
        • 'despesa': Faturas de cartão, boletos bancários a pagar, notas fiscais, recibos de compras, comprovantes de envio de PIX/transferência enviada.
        • 'receita': Comprovantes de PIX recebido, comprovantes de depósito, holerites/contracheques, extratos de rendimentos, reembolsos.
        
        CATEGORIAS VÁLIDAS:
        Alimentação, Moradia, Transporte, Saúde, Lazer, Assinaturas, Educação, Investimentos, Salário, Outros.
        """

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Texto do documento PDF:\n{texto_extraido[:3500]}"}
            ]
        )
        res = json.loads(response.choices[0].message.content)
        if res.get("tipo_acao") == "registro":
            tipo_orig = str(res.get("tipo", "")).strip().lower()
            res["tipo"] = "receita" if tipo_orig in ["receita", "ganho", "entrada", "lucro"] else "despesa"
        return res
    except Exception as e:
        return {"tipo_acao": "erro", "mensagem": f"Erro ao ler PDF: {str(e)}"}

def analisar_simulacao_compra(df_trans: pd.DataFrame, item: str, valor_compra: float, texto_usuario: str) -> str:
    fatos_longo_prazo = carregar_fatos()
    
    rec_real = df_trans[df_trans['tipo'] == 'receita']['valor'].sum() if not df_trans.empty else 0.0
    des_real = abs(df_trans[df_trans['tipo'] == 'despesa']['valor'].sum()) if not df_trans.empty else 0.0
    saldo_atual = rec_real - des_real

    try:
        df_fixas = carregar_despesas_fixas()
    except Exception:
        df_fixas = pd.DataFrame()

    hoje = datetime.now()
    mes_atual = hoje.month
    ano_atual = hoje.year

    meses_map = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, 
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8, 
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
    }
    
    dia_alvo = 31
    match_dia = re.search(r'\bdia\s+(\d{1,2})\b', texto_usuario.lower())
    if match_dia:
        dia_alvo = int(match_dia.group(1))

    meses_restantes = 0
    texto_lower = texto_usuario.lower()
    for nome_mes, num_mes in meses_map.items():
        if re.search(rf"\b{nome_mes}\b", texto_lower):
            if num_mes > mes_atual:
                meses_restantes = num_mes - mes_atual
            elif num_mes < mes_atual:
                meses_restantes = (12 - mes_atual) + num_mes
            break
            
    caixa_total_previsto = saldo_atual
    
    for i in range(1, meses_restantes + 1):
        mes_futuro = mes_atual + i
        ano_futuro = ano_atual
        if mes_futuro > 12:
            ano_futuro += (mes_futuro - 1) // 12
            mes_futuro = ((mes_futuro - 1) % 12) + 1
            
        folga_deste_mes = 0.0
        is_mes_final = (i == meses_restantes)
        
        if not df_fixas.empty:
            for _, row in df_fixas.iterrows():
                valido = True
                data_fim_str = row.get('data_fim')
                dia_vencimento = int(row.get('dia_vencimento', 31))
                
                if is_mes_final and dia_vencimento > dia_alvo:
                    valido = False

                if valido and pd.notna(data_fim_str) and data_fim_str:
                    try:
                        data_fim_obj = datetime.strptime(str(data_fim_str), "%Y-%m-%d")
                        if ano_futuro > data_fim_obj.year or (ano_futuro == data_fim_obj.year and mes_futuro > data_fim_obj.month):
                            valido = False
                    except ValueError:
                        pass
                
                if valido:
                    valor = float(row['valor'])
                    tipo = row.get('tipo', 'despesa')
                    if tipo == 'receita':
                        folga_deste_mes += valor
                    else:
                        folga_deste_mes -= abs(valor)
                        
        caixa_total_previsto += folga_deste_mes

    valor_faltante = valor_compra - caixa_total_previsto

    prompt_sistema = f"""
    Você é a Alice, uma assistente e conselheira financeira acolhedora, parceira e amigável. NUNCA FAÇA CÁLCULOS MATEMÁTICOS, use apenas os valores fornecidos abaixo.
    
    [DADOS JÁ CALCULADOS EXATOS]
    • Item Desejado: {item}
    • Valor da Compra: R$ {valor_compra:,.2f}
    • Caixa Total Previsto no Dia Solicitado: R$ {caixa_total_previsto:,.2f}
    
    REGRAS DE RESPOSTA:
    1. Baseie-se ESTRITAMENTE no 'Caixa Total Previsto no Dia Solicitado'.
    2. Se o Caixa Previsto for MENOR que o Valor da Compra, informe de forma gentil e clara que faltarão R$ {valor_faltante:,.2f}.
    3. Se for MAIOR, informe com entusiasmo que a compra é segura.
    4. Mantenha um tom natural, humano e de parceira no seu planejamento.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt_sistema}],
            temperature=0.1
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
    Você é a Alice, uma assistente pessoal e parceira financeira inteligente, empática e amigável.
    
    [DADOS FINANCEIROS REAIS DE HOJE]
    • Saldo Efetivado Atual no Banco: R$ {saldo_disponivel:,.2f}
    • Conhecimento Prévio: {fatos_longo_prazo}

    REGRAS DE RESPOSTA E TOM DE VOZ:
    1. Quando o usuário perguntar seu saldo atual ou quanto tem na conta HOJE, informe SEMPRE o 'Saldo Efetivado Atual no Banco' (R$ {saldo_disponivel:,.2f}).
    2. NUNCA confunda o saldo de hoje com projeções ou folgas do final do mês a menos que o usuário peça explicitamente uma estimativa futura.
    3. Seja amigável, acolhedora e use um tom de parceira no dia a dia. Evite parecer um robô ou responder de forma seca.
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