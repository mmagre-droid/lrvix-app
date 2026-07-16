import streamlit as st
from supabase import create_client

# --- CONFIGURAÇÃO ---
# Certifique-se de que SUPABASE_URL e SUPABASE_KEY estão nos "Secrets" do Streamlit
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🔐 Acesso LRVIX")

# Inicialização do estado
if "logado" not in st.session_state:
    st.session_state.logado = False
if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

# --- FUNÇÕES ---
def cadastrar_tecnico(nome, cpf, email, telefone, senha):
    # Verifica se o CPF já existe antes de tentar cadastrar
    existe = supabase.table("TECNICOS").select("cpf").eq("cpf", cpf).execute()
    
    if existe.data:
        st.error("⚠️ Este CPF já está cadastrado!")
        return False
    
    try:
        supabase.table("TECNICOS").insert({
            "nome": nome, 
            "cpf": cpf, 
            "email": email, 
            "telefone": telefone, 
            "senha": senha,
            "perfil": "Técnico"
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao cadastrar: {e}")
        return False

# --- INTERFACE ---
if not st.session_state.logado:
    tab1, tab2 = st.tabs(["Login", "Cadastrar Técnico"])
    
    with tab1:
        cpf_input = st.text_input("CPF")
        senha_input = st.text_input("Senha", type="password", key="login_senha")
        if st.button("Entrar"):
            user = supabase.table("TECNICOS").select("*").eq("cpf", cpf_input).eq("senha", senha_input).execute()
            if user.data:
                st.session_state.logado = True
                st.session_state.nome_tecnico = user.data[0]["nome"]
                st.session_state.perfil = user.data[0]["perfil"]
                st.rerun()
            else:
                st.error("CPF ou Senha incorretos.")

    with tab2:
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF (somente números)")
        email = st.text_input("E-mail")
        telefone = st.text_input("Telefone")
        senha = st.text_input("Senha", type="password", key="cad_senha")
        confirma_senha = st.text_input("Confirme sua Senha", type="password", key="cad_confirma")
        
        if st.button("Finalizar Cadastro"):
            if senha != confirma_senha:
                st.error("As senhas não coincidem!")
            elif not nome or not cpf or not senha:
                st.error("Por favor, preencha todos os campos obrigatórios.")
            else:
                if cadastrar_tecnico(nome, cpf, email, telefone, senha):
                    st.success("Cadastro realizado com sucesso!")

else:
    # --- ÁREA LOGADA ---
    st.success(f"Logado como: {st.session_state.nome_tecnico} ({st.session_state.perfil})")
    
    if st.button("Painel de Administração"):
        st.session_state.modo_admin = True
        st.rerun()

    if st.session_state.modo_admin:
        st.subheader("🔐 Área de Gestão de Perfis")
        senha_admin = st.text_input("Digite a Senha Mestra:", type="password", key="admin_senha")
        
        if senha_admin == "123456":
            usuarios = supabase.table("TECNICOS").select("*").execute()
            
            edited_data = st.data_editor(usuarios.data, column_config={
                "perfil": st.column_config.SelectboxColumn(
                    "Perfil",
                    options=["Técnico", "Assistente", "Administrador"],
                    required=True,
                )
            })
            
            if st.button("Salvar Perfis"):
                sucesso = True
                for row in edited_data:
                    try:
                        supabase.table("TECNICOS").update({"perfil": row["perfil"]}).eq("cpf", row["cpf"]).execute()
                    except:
                        sucesso = False
                if sucesso:
                    st.success("Perfis atualizados com sucesso!")
                    st.rerun()
        elif senha_admin:
            st.error("Senha incorreta!")
            
    if st.button("Sair"):
        st.session_state.logado = False
        st.session_state.modo_admin = False
        st.rerun()
