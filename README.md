# 👩‍💼 Alice — Assistente Pessoal & Gestão Financeira Inteligente

> Assistente autônoma 24/7 integrada ao Telegram e Streamlit, alimentada por IA (GPT-4o-mini, Whisper e Visão Computacional) com persistência em PostgreSQL (Supabase).

---

## 🚀 Funcionalidades Principais

* 🎙️ **Compreensão de Áudio (Telegram):** Transcrição de mensagens de voz em tempo real usando **OpenAI Whisper-1**.
* 🧾 **Leitura de Comprovantes por Foto:** Reconhecimento e extração automática de notas fiscais via **GPT-4o Vision**.
* 💰 **Gestão Financeira Inteligente:** Categorização automática de receitas e despesas com dashboard interativo e filtros por mês/ano.
* 📌 **Lançamento Automático de Gastos Fixos:** Processamento recorrente de assinaturas e contas mensais sem duplicidade.
* 🧠 **Memória de Longo Prazo:** Armazenamento contextual de fatos e preferências do usuário no Supabase.
* 📱 **Bot Telegram 24/7:** Execução contínua em segundo plano hospedada no Streamlit Cloud com monitoramento do UptimeRobot.

---

## 🛠️ Tecnologias Utilizadas

| Camada | Tecnologia |
| :--- | :--- |
| **Frontend / Dashboard** | Streamlit, Plotly Express |
| **Backend / Bot** | Python 3.11+, PyTelegramBotAPI (`telebot`) |
| **Inteligência Artificial** | OpenAI (GPT-4o-mini, Whisper-1) |
| **Banco de Dados** | Supabase (PostgreSQL) |
| **Hospedagem & CI/CD** | Streamlit Community Cloud, GitHub Actions |
| **Disponibilidade** | UptimeRobot (Prevenção de Hibernação) |

---

## 📁 Estrutura do Projeto

```text
.
├── alice.py          # Ponto de entrada, rotas e interface Streamlit
├── ai.py             # Módulo de inteligência (GPT-4o, Whisper e Vision)
├── bot.py            # Event loop do bot do Telegram (Texto, Áudio e Foto)
├── database.py       # Conexão, queries e automações do Supabase
├── ui.py             # Componentes visuais e autenticação responsiva
├── style.css         # Customização visual do dashboard
├── requirements.txt  # Dependências do ecossistema Python
└── .gitignore        # Bloqueio de arquivos sensíveis e segredos