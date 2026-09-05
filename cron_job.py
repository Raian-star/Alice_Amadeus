import os
import io
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import telebot

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_MY_CHAT_ID = os.environ.get("TELEGRAM_MY_CHAT_ID")

def carregar_dados_supabase():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = supabase.table("transacoes").select("*").order("data", desc=True).execute()
    return pd.DataFrame(res.data)

def gerar_pdf_bytes(df: pd.DataFrame, periodo_nome: str = "Geral") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#0f172a'))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#64748b'))
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')

    elements.append(Paragraph("<b>Alice AI — Relatório Financeiro Automático</b>", title_style))
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

def executar():
    if not all([SUPABASE_URL, SUPABASE_KEY, TELEGRAM_TOKEN, TELEGRAM_MY_CHAT_ID]):
        print("❌ Variáveis de ambiente faltando.")
        return

    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    df = carregar_dados_supabase()
    
    if df.empty:
        bot.send_message(TELEGRAM_MY_CHAT_ID, "📊 Relatório Automático: Nenhuma transação cadastrada.")
        return

    hoje = datetime.now()
    pdf_bytes = gerar_pdf_bytes(df, f"Geral ({hoje.strftime('%m/%Y')})")
    
    bot.send_document(
        TELEGRAM_MY_CHAT_ID,
        document=io.BytesIO(pdf_bytes),
        visible_file_name=f"relatorio_alice_{hoje.strftime('%m_%Y')}.pdf",
        caption="📅 **Relatório Automático Programado da Alice**\nSeu balanço atualizado já está disponível acima!"
    )
    print("✅ Relatório enviado com sucesso via GitHub Actions!")

if __name__ == "__main__":
    executar()