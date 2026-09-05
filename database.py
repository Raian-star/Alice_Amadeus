import os
import io
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

ID_MEMORIA_UNIFICADA = 1

def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Variáveis de ambiente SUPABASE_URL e SUPABASE_KEY são obrigatórias.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- TRANSAÇÕES ---
def carregar_dados():
    supabase = get_supabase_client()
    res = supabase.table("transacoes").select("*").order("data", desc=True).execute()
    return pd.DataFrame(res.data)

def registrar_transacao(descricao, valor, categoria, tipo, data=None):
    supabase = get_supabase_client()
    if not data:
        data = datetime.now().strftime("%Y-%m-%d")
    
    valor_float = float(valor)
    if tipo == "despesa" and valor_float > 0:
        valor_float = -valor_float

    nova_transacao = {
        "descricao": descricao,
        "valor": valor_float,
        "categoria": categoria,
        "tipo": tipo,
        "data": str(data)
    }
    supabase.table("transacoes").insert(nova_transacao).execute()

# --- HISTÓRICO DE MENSAGENS E MEMÓRIA (usando tabela mensagens_chat) ---
def salvar_mensagem_memoria(papel, conteudo):
    supabase = get_supabase_client()
    try:
        data = {
            "papel": papel,
            "conteudo": conteudo,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("mensagens_chat").insert(data).execute()
    except Exception as e:
        print(f"Aviso ao salvar mensagem: {e}")

def carregar_historico_mensagens(limite=10):
    supabase = get_supabase_client()
    try:
        res = supabase.table("mensagens_chat").select("*").order("created_at", desc=True).limit(limite).execute()
        if res.data:
            return list(reversed(res.data))
    except Exception as e:
        print(f"Aviso ao carregar historico: {e}")
    return []

def carregar_memoria_chat(limite=10):
    return carregar_historico_mensagens(limite)

def salvar_memoria_chat(papel, conteudo):
    salvar_mensagem_memoria(papel, conteudo)

def consultar_memoria_unificada():
    supabase = get_supabase_client()
    try:
        fatos = carregar_fatos()
        dados_fin = carregar_dados()
        resumo_fin = f"Total de transações: {len(dados_fin)}" if not dados_fin.empty else "Sem transações salvas."
        return f"--- FATOS DO CÉREBRO ---\n{fatos}\n\n--- FINANÇAS ---\n{resumo_fin}"
    except Exception as e:
        return f"Memória parcial carregada. Erro: {e}"

# --- CÉREBRO / FATOS (usando tabela fatos_usuario) ---
def carregar_fatos():
    supabase = get_supabase_client()
    try:
        res = supabase.table("fatos_usuario").select("fato").order("created_at", desc=True).execute()
        if res.data:
            return "\n".join([f"- {item['fato']}" for item in res.data])
    except Exception as e:
        print(f"Erro ao carregar fatos: {e}")
    return "Nenhum fato registrado ainda."

def carregar_fatos_detalhados():
    supabase = get_supabase_client()
    try:
        res = supabase.table("fatos_usuario").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        print(f"Erro ao carregar fatos detalhados: {e}")
        return pd.DataFrame()

def salvar_fato(fato_texto):
    supabase = get_supabase_client()
    supabase.table("fatos_usuario").insert({"fato": fato_texto}).execute()

def deletar_fato(fato_id):
    supabase = get_supabase_client()
    supabase.table("fatos_usuario").delete().eq("id", fato_id).execute()

# --- LANÇAMENTOS RECORRENTES (RECEITAS E DESPESAS) ---
def salvar_despesa_fixa(descricao, valor, categoria, dia_vencimento, tipo="despesa"):
    supabase = get_supabase_client()
    data = {
        "descricao": descricao,
        "valor": float(valor),
        "categoria": categoria,
        "dia_vencimento": int(dia_vencimento),
        "tipo": tipo
    }
    supabase.table("despesas_fixas").insert(data).execute()

def carregar_despesas_fixas():
    supabase = get_supabase_client()
    res = supabase.table("despesas_fixas").select("*").order("dia_vencimento").execute()
    return pd.DataFrame(res.data)

def deletar_despesa_fixa(fixo_id):
    supabase = get_supabase_client()
    supabase.table("despesas_fixas").delete().eq("id", fixo_id).execute()

def processar_despesas_fixas_mes_atual():
    supabase = get_supabase_client()
    hoje = datetime.now()
    mes_ano_atual = hoje.strftime("%Y-%m")
    
    res_fixas = supabase.table("despesas_fixas").select("*").execute()
    if not res_fixas.data:
        return

    res_trans = supabase.table("transacoes").select("descricao, data").execute()
    trans_existentes = set()
    if res_trans.data:
        for t in res_trans.data:
            if t['data'].startswith(mes_ano_atual):
                trans_existentes.add(t['descricao'])

    for item in res_fixas.data:
        nome_marcador = f"[FIXO] {item['descricao']}"
        tipo_item = item.get('tipo', 'despesa')
        
        if nome_marcador not in trans_existentes:
            dia = int(item['dia_vencimento'])
            try:
                data_lancamento = datetime(hoje.year, hoje.month, dia).strftime("%Y-%m-%d")
            except ValueError:
                data_lancamento = datetime(hoje.year, hoje.month, 28).strftime("%Y-%m-%d")

            valor_final = float(item['valor'])
            if tipo_item == "despesa" and valor_final > 0:
                valor_final = -valor_final

            nova_t = {
                "descricao": nome_marcador,
                "valor": valor_final,
                "categoria": item['categoria'],
                "tipo": tipo_item,
                "data": data_lancamento
            }
            supabase.table("transacoes").insert(nova_t).execute()

# --- RELATÓRIOS ---
def gerar_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transacoes')
    return output.getvalue()

def gerar_pdf_bytes(df: pd.DataFrame, periodo_nome: str = "Geral") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#0f172a'))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#64748b'))
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')

    elements.append(Paragraph("<b>Alice AI — Relatório Financeiro</b>", title_style))
    elements.append(Paragraph(f"Período: <b>{periodo_nome}</b> | Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", sub_style))
    elements.append(Spacer(1, 15))

    rec = df[df['tipo'] == 'receita']['valor'].sum() if not df.empty else 0.0
    des = abs(df[df['tipo'] == 'despesa']['valor'].sum()) if not df.empty else 0.0
    saldo = rec - des

    data_resumo = [
        [Paragraph("<b>Entradas</b>", cell_bold), Paragraph("<b>Saídas</b>", cell_bold), Paragraph("<b>Saldo Período</b>", cell_bold)],
        [f"R$ {rec:,.2f}", f"R$ {des:,.2f}", f"R$ {saldo:,.2f}"]
    ]
    t_resumo = Table(data_resumo, colWidths=[170, 170, 170])
    t_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0f172a')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_resumo)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Detalhamento das Transações</b>", styles['Heading2']))
    elements.append(Spacer(1, 8))

    headers = [Paragraph("<b>Data</b>", cell_bold), Paragraph("<b>Descrição</b>", cell_bold), Paragraph("<b>Categoria</b>", cell_bold), Paragraph("<b>Tipo</b>", cell_bold), Paragraph("<b>Valor (R$)</b>", cell_bold)]
    table_data = [headers]

    for _, row in df.iterrows():
        val_str = f"R$ {abs(row['valor']):,.2f}"
        sinal = "-" if row['tipo'] == 'despesa' else "+"
        table_data.append([
            Paragraph(str(row['data']), cell_style),
            Paragraph(str(row['descricao'])[:35], cell_style),
            Paragraph(str(row['categoria']), cell_style),
            Paragraph(str(row['tipo']).capitalize(), cell_style),
            Paragraph(f"{sinal}{val_str}", cell_style)
        ])

    t_detalhes = Table(table_data, colWidths=[70, 180, 100, 70, 90])
    t_detalhes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_detalhes)

    doc.build(elements)
    return buffer.getvalue()