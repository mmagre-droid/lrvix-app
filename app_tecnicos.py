import streamlit as st
from supabase import create_client

st.set_page_config(page_title="LRVIX - Acesso", layout="centered")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🔐 Acesso LRVIX")

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    tab1, tab2 = st.tabs(["Login", "Cadastrar Técnico"])
    
    with tab1:
        cpf_log = st.text_input("CPF", key="login_cpf")
        senha_log = st.text_input("Senha", type="password", key="login_senha")
        if st.button("Entrar"):
            user = supabase.table("TECNICOS").select("*").eq("cpf", cpf_log).eq("senha", senha_log).execute()
            if user.data:
                st.session_state.logado = True
                st.session_state.nome_tecnico = user.data[0]['nome']
                st.rerun()
            else:
                st.error("CPF ou Senha inválidos!")

    with tab2:
        with st.form("form_cadastro", clear_on_submit=True):
            nome = st.text_input("Nome Completo")
            cpf_cad = st.text_input("CPF (Será seu login)")
            senha_cad = st.text_input("Senha", type="password")
            
            if st.form_submit_button("Finalizar Cadastro"):
                # 1. Verifica se CPF já existe
                check = supabase.table("TECNICOS").select("cpf").eq("cpf", cpf_cad).execute()
                
                if check.data:
                    st.error("❌ Este CPF já está cadastrado!")
                elif not nome or not cpf_cad or not senha_cad:
                    st.warning("⚠️ Preencha todos os campos!")
                else:
                    # 2. Insere se não existir
                    supabase.table("TECNICOS").insert({
                        "nome": nome, "cpf": cpf_cad, "senha": senha_cad
                    }).execute()
                    st.success("Cadastro realizado com sucesso! Vá para a aba Login.")
else:
    st.success(f"Logado como: {st.session_state.nome_tecnico}")
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
