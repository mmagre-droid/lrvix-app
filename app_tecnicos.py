import streamlit as st
from supabase import create_client

# --- CONFIGURAÇÃO ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🔐 ACESSO LRVIX")

# INICIALIZAÇÃO DO ESTADO
if "LOGADO" not in st.session_state:
    st.session_state.LOGADO = False
if "MODO_ADMIN" not in st.session_state:
    st.session_state.MODO_ADMIN = False

# --- FUNÇÕES ---
def CADASTRAR_TECNICO(NOME, CPF, EMAIL, TELEFONE, SENHA):
    EXISTE = supabase.table("TECNICOS").select("CPF").eq("CPF", CPF).execute()
    if EXISTE.data:
        st.error("⚠️ ESTE CPF JÁ ESTÁ CADASTRADO!")
        return False
    try:
        supabase.table("TECNICOS").insert({"NOME": NOME, "CPF": CPF, "EMAIL": EMAIL, "TELEFONE": TELEFONE, "SENHA": SENHA, "PERFIL": "TÉCNICO"}).execute()
        return True
    except Exception as E:
        st.error(f"ERRO AO CADASTRAR: {E}")
        return False

def REGISTRAR_ATENDIMENTO(DATA_EXECUCAO, CLIENTE, ENDERECO, PROTOCOLO, MERCADO, TIPO_SERVICO, OBSERVACAO, FOTO_URL):
    try:
        supabase.table("ATENDIMENTO").insert({
            "DATA_EXECUCAO": str(DATA_EXECUCAO),
            "CLIENTE": CLIENTE,
            "ENDERECO": ENDERECO,
            "PROTOCOLO": PROTOCOLO,
            "MERCADO": MERCADO,
            "TIPO_SERVICO": TIPO_SERVICO,
            "OBSERVACAO": OBSERVACAO,
            "FOTO": FOTO_URL
        }).execute()
        return True
    except Exception as E:
        st.error(f"ERRO AO SALVAR: {E}")
        return False

# --- INTERFACE ---
if not st.session_state.LOGADO:
    TAB1, TAB2 = st.tabs(["LOGIN", "CADASTRAR TÉCNICO"])
    with TAB1:
        CPF_INPUT = st.text_input("CPF")
        SENHA_INPUT = st.text_input("SENHA", type="password", key="LOGIN_SENHA")
        if st.button("ENTRAR"):
            USER = supabase.table("TECNICOS").select("*").eq("CPF", CPF_INPUT).eq("SENHA", SENHA_INPUT).execute()
            if USER.data:
                st.session_state.LOGADO = True
                st.session_state.NOME_TECNICO = USER.data[0]["NOME"]
                st.session_state.PERFIL = USER.data[0]["PERFIL"]
                st.rerun()
            else:
                st.error("CPF OU SENHA INCORRETOS.")
    with TAB2:
        NOME = st.text_input("NOME COMPLETO")
        CPF = st.text_input("CPF (SOMENTE NÚMEROS)")
        EMAIL = st.text_input("E-MAIL")
        TELEFONE = st.text_input("TELEFONE")
        SENHA = st.text_input("SENHA", type="password", key="CAD_SENHA")
        CONFIRMA_SENHA = st.text_input("CONFIRME SUA SENHA", type="password", key="CAD_CONFIRMA")
        if st.button("FINALIZAR CADASTRO"):
            if SENHA == CONFIRMA_SENHA and CADASTRAR_TECNICO(NOME, CPF, EMAIL, TELEFONE, SENHA):
                st.success("CADASTRO REALIZADO!")

else:
    # --- ÁREA LOGADA COM ABAS ---
    st.success(f"LOGADO COMO: {st.session_state.NOME_TECNICO} ({st.session_state.PERFIL})")
    
    ABA1, ABA2, ABA3, ABA4 = st.tabs(["📝 FORMULÁRIO", "📊 PRODUTIVIDADE", "⚠️ APR", "⚙️ ADMIN"])

    with ABA1:
        with st.form("FORM_ATENDIMENTO", clear_on_submit=True):
            C1, C2 = st.columns(2)
            with C1:
                DATA_EXECUCAO = st.date_input("DATA DA EXECUÇÃO")
                CLIENTE = st.text_input("NOME DO CLIENTE")
                ENDERECO = st.text_input("ENDEREÇO")
            with C2:
                PROTOCOLO = st.text_input("PROTOCOLO")
                MERCADO = st.selectbox("MERCADO", ["REPARO", "ATIVAÇÃO", "RETIRADA"])
                TIPO_SERVICO = st.selectbox("TIPO DE SERVIÇO", ["INTERNO", "EXTERNO", "IMPRODUTIVO"])
            
            OBSERVACAO = st.text_area("OBSERVAÇÃO")
            FOTO_ARQUIVO = st.file_uploader("FOTO DO SERVIÇO", type=['JPG', 'PNG', 'JPEG'])
            
            if st.form_submit_button("REGISTRAR ATENDIMENTO"):
                URL_FOTO = ""
                if FOTO_ARQUIVO:
                    try:
                        CAMINHO = f"FOTOS/{FOTO_ARQUIVO.name}"
                        supabase.storage.from_("FOTOS_ATENDIMENTOS").upload(CAMINHO, FOTO_ARQUIVO.getvalue())
                        URL_FOTO = CAMINHO
                    except Exception as E:
                        st.error(f"ERRO AO SUBIR FOTO: {E}")
                
                if REGISTRAR_ATENDIMENTO(DATA_EXECUCAO, CLIENTE, ENDERECO, PROTOCOLO, MERCADO, TIPO_SERVICO, OBSERVACAO, URL_FOTO):
                    st.success("ATENDIMENTO REGISTRADO COM SUCESSO!")

    with ABA2:
        st.subheader("LISTA DE ATENDIMENTOS")
        ATENDIMENTOS = supabase.table("ATENDIMENTO").select("*").execute()
        if ATENDIMENTOS.data:
            st.dataframe(ATENDIMENTOS.data, use_container_width=True)
        else:
            st.info("NENHUM ATENDIMENTO REGISTRADO.")

    with ABA3:
        st.subheader("ANÁLISE PRELIMINAR DE RISCO (APR)")
        st.checkbox("USO DE EPIS OBRIGATÓRIOS")
        st.checkbox("ÁREA ISOLADA E SINALIZADA")
        st.selectbox("NÍVEL DE RISCO", ["BAIXO", "MÉDIO", "ALTO"])
        if st.button("FINALIZAR APR"):
            st.success("APR REGISTRADA!")

    with ABA4:
        if st.button("SAIR DO SISTEMA"):
            st.session_state.LOGADO = False
            st.rerun()
        st.subheader("ADMINISTRAÇÃO")
