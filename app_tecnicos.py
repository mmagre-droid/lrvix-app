import streamlit as st
from supabase import create_client

# --- CONFIGURAÇÃO ---
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
    existe = supabase.table("TECNICOS").select("cpf").eq("cpf", cpf).execute()
    if existe.data:
        st.error("⚠️ Este CPF já está cadastrado!")
        return False
    try:
        supabase.table("TECNICOS").insert({"nome": nome, "cpf": cpf, "email": email, "telefone": telefone, "senha": senha, "perfil": "Técnico"}).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao cadastrar: {e}")
        return False

def registrar_atendimento(data_execucao, cliente, endereco, protocolo, mercado, tipo_servico, observacao, foto_url):
    try:
        supabase.table("ATENDIMENTO").insert({
            "data_execucao": str(data_execucao),
            "cliente": cliente,
            "endereco": endereco,
            "protocolo": protocolo,
            "mercado": mercado,
            "tipo_servico": tipo_servico,
            "observacao": observacao,
            "foto": foto_url
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
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
            if senha == confirma_senha and cadastrar_tecnico(nome, cpf, email, telefone, senha):
                st.success("Cadastro realizado!")

else:
    # --- ÁREA LOGADA COM ABAS ---
    st.success(f"Logado como: {st.session_state.nome_tecnico} ({st.session_state.perfil})")
    
    aba1, aba2, aba3, aba4 = st.tabs(["📝 Formulário", "📊 Produtividade", "⚠️ APR", "⚙️ Admin"])

    with aba1:
        with st.form("form_atendimento", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                data_execucao = st.date_input("Data")
                cliente = st.text_input("Cliente")
                endereco = st.text_input("Endereço")
            with c2:
                protocolo = st.text_input("Protocolo")
                mercado = st.selectbox("Mercado", ["Residencial", "Empresarial"])
                tipo_servico = st.selectbox("Serviço", ["Instalação", "Manutenção", "Reparo"])
            observacao = st.text_area("Observação")
            foto_arquivo = st.file_uploader("Foto", type=['jpg', 'png'])
            if st.form_submit_button("Registrar"):
                url_foto = ""
                if foto_arquivo:
                    caminho = f"fotos/{foto_arquivo.name}"
                    supabase.storage.from_("fotos_atendimentos").upload(caminho, foto_arquivo.getvalue())
                    url_foto = caminho
                if registrar_atendimento(data_execucao, cliente, endereco, protocolo, mercado, tipo_servico, observacao, url_foto):
                    st.success("Salvo!")

    with aba2:
        st.subheader("Atendimentos")
        dados = supabase.table("ATENDIMENTO").select("*").execute()
        st.dataframe(dados.data)

    with aba3:
        st.subheader("Análise de Risco (APR)")
        st.checkbox("EPIs Conferidos")
        st.checkbox("Área Segura")
        st.button("Finalizar APR")

    with aba4:
        if st.button("Sair do Sistema"):
            st.session_state.logado = False
            st.rerun()
        # Lógica de admin aqui...
