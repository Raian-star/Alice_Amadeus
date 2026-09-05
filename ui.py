import os
import base64
import streamlit as st

ALICE_IMG_PATH = "alice.png"

def carregar_imagem_base64(caminho: str) -> str:
    if os.path.exists(caminho):
        with open(caminho, "rb") as f:
            data = f.read()
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    return ""

ALICE_B64 = carregar_imagem_base64(ALICE_IMG_PATH)

def aplicar_estilo_css():
    if os.path.exists("style.css"):
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def autenticar_usuario() -> bool:
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        avatar_html = f'<img src="{ALICE_B64}" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; margin-bottom: 10px; border: 3px solid #6366f1; box-shadow: 0 4px 12px rgba(99,102,241,0.25);">' if ALICE_B64 else '<div style="font-size: 45px; margin-bottom: 10px;">👩‍💼</div>'

        st.markdown("""
            <style>
            [data-testid="collapsedControl"] { display: none; }
            header { visibility: hidden; }
            [data-testid="stAppViewContainer"] { background-color: #f8fafc; }
            
            div[data-testid="stForm"] {
                max-width: 380px !important;
                width: 100% !important;
                margin: 8vh auto 0 auto !important;
                background-color: #ffffff;
                border-radius: 20px;
                padding: 30px 24px 24px 24px;
                box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.08);
                border: 1px solid #e2e8f0;
            }
            
            div[data-baseweb="input"] {
                border-radius: 12px !important;
            }
            button[kind="primary"] {
                border-radius: 12px !important;
                height: 45px !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        _, col_center, _ = st.columns([1, 1.2, 1])
        
        with col_center:
            with st.form("login_form", clear_on_submit=False):
                st.markdown(f"""
                    <div style="text-align: center; margin-bottom: 20px;">
                        {avatar_html}
                        <h2 style="margin: 0; color: #0f172a; font-weight: 800; font-size: 22px;">Olá, seja bem-vindo</h2>
                        <p style="color: #64748b; font-size: 13px; margin-top: 4px;">Insira sua senha mestre para acessar</p>
                    </div>
                """, unsafe_allow_html=True)
                
                senha_digitada = st.text_input("Senha", type="password", placeholder="Digite sua senha...", label_visibility="collapsed")
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                btn_login = st.form_submit_button("Acessar Painel", type="primary", use_container_width=True)
                
                if btn_login:
                    if senha_digitada == st.secrets.get("APP_PASSWORD", "1234"):
                        st.session_state.autenticado = True
                        st.rerun()
                    else:
                        st.error("🔑 Senha incorreta.")
        return False
    return True