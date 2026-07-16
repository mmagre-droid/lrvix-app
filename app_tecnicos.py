import streamlit as st
from supabase import create_client

# Configurações do seu banco de dados
URL = "https://ozcgilhxomoyqaejwyrs.supabase.co"
KEY = "sb_publishable_lrV26hcUDDuUpG0_pXSmFQ_S2T35_ZK" # Cole sua chave sb_publishable... aqui

supabase = create_client(URL, KEY)

st.title("👨‍🔧 Cadastro de Técnicos - LRVIX")

# Formulário de entrada
with st.form("form_tecnico"):
    nome = st.text_input("Nome do Técnico")
    cpf = st.text_input("CPF")
    email = st.text_input("E-mail")
    telefone = st.text_input("Telefone")
    
    btn_cadastrar = st.form_submit_button("Cadastrar Técnico")

    if btn_cadastrar:
        dados = {"nome": nome, "cpf": cpf, "email": email, "telefone": telefone}
        try:
            supabase.table("TECNICOS").insert(dados).execute()
            st.success(f"Técnico {nome} cadastrado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao cadastrar: {e}")

# Exibir técnicos já cadastrados
st.divider()
st.subheader("Técnicos Cadastrados")
if st.button("Atualizar lista"):
    response = supabase.table("TECNICOS").select("*").execute()
    st.table(response.data)