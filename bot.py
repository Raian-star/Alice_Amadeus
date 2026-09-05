import os
import sys
import asyncio
import logging
import threading
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import (
    carregar_dados, registrar_transacao,
    salvar_fato, salvar_mensagem_memoria,
    carregar_memoria_chat, gerar_pdf_bytes
)
from ai import (
    processar_texto_com_ia, processar_imagem_com_ia,
    transcrever_audio, consultar_alice
)

# Configuração de Logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger("AliceBot")
LOGS_STREAMLIT = []

def registrar_log(mensagem):
    logger.info(mensagem)
    LOGS_STREAMLIT.append(mensagem)
    if len(LOGS_STREAMLIT) > 30:
        LOGS_STREAMLIT.pop(0)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registrar_log(f"📥 Recebido /start de: {update.effective_user.first_name}")
    if update.message:
        await update.message.reply_text(
            "👋 *Olá! Eu sou a Alice, sua assistente pessoal.*\n\n"
            "Posso te ajudar a:\n"
            "• Registrar seus gastos e ganhos diários (texto, áudio ou foto).\n"
            "• Responder dúvidas, fazer simulações e conversas gerais.\n"
            "• Memorizar regras e preferências sobre você.\n\n"
            "💬 *Como posso te ajudar agora?*",
            parse_mode="Markdown"
        )

async def comando_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registrar_log("📥 Recebido /relatorio")
    df = carregar_dados()
    if df.empty:
        await update.message.reply_text("Nenhuma transação encontrada.")
        return
        
    rec = df[df['tipo'] == 'receita']['valor'].sum()
    des = abs(df[df['tipo'] == 'despesa']['valor'].sum())
    saldo = rec - des
    
    msg = (
        f"📊 *Resumo Financeiro Atual*\n\n"
        f"🟢 *Entradas:* R$ {rec:,.2f}\n"
        f"🔴 *Saídas:* R$ {des:,.2f}\n"
        f"💵 *Saldo:* R$ {saldo:,.2f}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def comando_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registrar_log("📥 Recebido /pdf")
    df = carregar_dados()
    if df.empty:
        await update.message.reply_text("Nenhuma transação cadastrada.")
        return
        
    pdf_bytes = gerar_pdf_bytes(df, "Geral")
    await context.bot.send_document(
        chat_id=update.message.chat_id,
        document=pdf_bytes,
        filename="Relatorio_Alice.pdf",
        caption="📄 Seu relatório financeiro completo em PDF."
    )

async def responder_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    registrar_log(f"📥 Nova mensagem no Chat ID {chat_id}")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    texto_usuario = ""

    try:
        # Áudio (Transcrição silenciosa sem envio de mensagem intermediária)
        if update.message.voice or update.message.audio:
            registrar_log("🎙️ Processando áudio...")
            arquivo = await (update.message.voice or update.message.audio).get_file()
            audio_bytes = await arquivo.download_as_bytearray()
            texto_usuario = transcrever_audio(bytes(audio_bytes))

        # Imagem (Nota / Comprovante)
        elif update.message.photo:
            registrar_log("🖼️ Processando imagem...")
            foto = await update.message.photo[-1].get_file()
            img_bytes = await foto.download_as_bytearray()
            res_img = processar_imagem_com_ia(bytes(img_bytes))
            
            if res_img.get("tipo_acao") == "registro":
                registrar_transacao(
                    descricao=res_img["descricao"],
                    valor=res_img["valor"],
                    categoria=res_img.get("categoria", "Outros"),
                    tipo=res_img["tipo"]
                )
                sinal = "🟢 Entrada" if res_img["tipo"] == "receita" else "🔴 Saída"
                await update.message.reply_text(
                    f"✅ *Lançamento via Imagem Salvo!*\n\n"
                    f"📌 *Item:* {res_img['descricao']}\n"
                    f"💰 *Valor:* R$ {res_img['valor']:.2f}\n"
                    f"🏷️ *Categoria:* {res_img.get('categoria', 'Outros')}\n"
                    f"📊 *Tipo:* {sinal}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"⚠️ {res_img.get('mensagem', 'Erro ao ler imagem.')}")
            return

        # Texto
        elif update.message.text:
            texto_usuario = update.message.text

        if not texto_usuario:
            return

        # Classificação do texto recebido
        analise = processar_texto_com_ia(texto_usuario)
        tipo_acao = analise.get("tipo_acao")

        # ROTA 1: Registrar movimentação
        if tipo_acao == "registro":
            registrar_transacao(
                descricao=analise["descricao"],
                valor=analise["valor"],
                categoria=analise.get("categoria", "Outros"),
                tipo=analise["tipo"]
            )
            sinal = "🟢 Entrada" if analise["tipo"] == "receita" else "🔴 Saída"
            await update.message.reply_text(
                f"✅ *Lançamento Registrado!*\n\n"
                f"📌 *Descrição:* {analise['descricao']}\n"
                f"💰 *Valor:* R$ {analise['valor']:.2f}\n"
                f"🏷️ *Categoria:* {analise.get('categoria', 'Outros')}\n"
                f"📊 *Tipo:* {sinal}",
                parse_mode="Markdown"
            )

        # ROTA 2: Memorizar fato/repreensa
        elif tipo_acao == "memorizar":
            salvar_fato(analise["fato"])
            await update.message.reply_text(f"🧠 *Aprendi novo fato:* \"{analise['fato']}\"", parse_mode="Markdown")

        # ROTA 3: Bate-papo / Dúvida / Pergunta / Piada / Consulta
        else:
            df_trans = carregar_dados()
            
            # Carrega o histórico recente do banco
            historico_raw = carregar_memoria_chat(limite=3)
            historico_formatado = []
            for item in historico_raw:
                papel = "user" if item.get("papel") == "user" else "assistant"
                historico_formatado.append({"role": papel, "content": item.get("conteudo", "")})

            # Chama a IA passando o texto atual diretamente
            resposta = consultar_alice(df_trans, historico_formatado, texto_usuario)
            
            # Salva o par da conversa na memória após a resposta
            salvar_mensagem_memoria("user", texto_usuario)
            salvar_mensagem_memoria("assistant", resposta)
            
            await update.message.reply_text(resposta, parse_mode="Markdown")

    except Exception as e:
        registrar_log(f"❌ ERRO: {str(e)}")
        await update.message.reply_text(f"⚠️ Ocorreu um erro interno: {str(e)}")

def _rodar_polling():
    registrar_log("🚀 Iniciando Polling do Telegram...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler("start", comando_start))
        app.add_handler(CommandHandler("relatorio", comando_relatorio))
        app.add_handler(CommandHandler("pdf", comando_pdf))
        app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, responder_mensagem))

        # Derruba conexões pendentes para prevenir erro de conflito
        loop.run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))
        app.run_polling(drop_pending_updates=True, stop_signals=None, close_loop=False)
    except Exception as e:
        registrar_log(f"❌ ERRO CRÍTICO NO BOT: {str(e)}")

def iniciar_telegram_bot():
    if not TELEGRAM_TOKEN:
        return False, "Token ausente"

    if not hasattr(iniciar_telegram_bot, "thread_bot") or not iniciar_telegram_bot.thread_bot.is_alive():
        t = threading.Thread(target=_rodar_polling, daemon=True)
        iniciar_telegram_bot.thread_bot = t
        t.start()

    return True, "Rodando"

def obter_logs():
    return "\n".join(LOGS_STREAMLIT) if LOGS_STREAMLIT else "Nenhum log gravado."