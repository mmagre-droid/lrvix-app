import streamlit as st
from supabase import create_client
import time

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
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.write(f"👤 Usuário: {st.session_state.nome_tecnico}")
        if st.button("SAIR DO SISTEMA"):
            st.session_state.logado = False
            st.rerun()

    st.success(f"Logado como: {st.session_state.nome_tecnico} ({st.session_state.perfil})")
    
    aba1, aba2, aba3, aba4 = st.tabs(["📝 FORMULÁRIO", "📊 PRODUTIVIDADE", "⚠️ APR", "⚙️ ADMIN"])

    with aba1:
        with st.form("form_atendimento", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                data_execucao = st.date_input("DATA DA EXECUÇÃO")
                cliente = st.text_input("NOME DO CLIENTE")
                endereco = st.text_input("ENDEREÇO")
            with c2:
                protocolo = st.text_input("PROTOCOLO")
                mercado = st.selectbox("MERCADO", ["REPARO", "ATIVAÇÃO", "RETIRADA"])
                tipo_servico = st.selectbox("TIPO DE SERVIÇO", ["INTERNO", "EXTERNO", "IMPRODUTIVO"])
            
            observacao = st.text_area("OBSERVAÇÃO")
            foto_arquivo = st.file_uploader("FOTO DO SERVIÇO", type=['jpg', 'png', 'jpeg'])
            
            if st.form_submit_button("REGISTRAR ATENDIMENTO"):
                url_foto = ""
                if foto_arquivo:
                    try:
                        timestamp = int(time.time())
                        caminho = f"fotos/{timestamp}_{foto_arquivo.name}"
                        supabase.storage.from_("fotos_atendimentos").upload(caminho, foto_arquivo.getvalue())
                        url_foto = caminho
                    except Exception as e:
                        st.error(f"Erro ao subir foto: {e}")
                
                if registrar_atendimento(data_execucao, cliente, endereco, protocolo, mercado, tipo_servico, observacao, url_foto):
                    st.success("Atendimento registrado com sucesso!")

    with aba2:
        st.subheader("Lista de Atendimentos")
        atendimentos = supabase.table("ATENDIMENTO").select("*").execute()
        if atendimentos.data:
            st.dataframe(atendimentos.data, use_container_width=True)
        else:
            st.info("Nenhum atendimento registrado.")

    with aba3:
        st.subheader("⚠️ ANÁLISE PRELIMINAR DE RISCO (APR)")
        
        col1, col2 = st.columns(2)
        with col1:
            data_atividade = st.date_input("Data da Atividade")
            local_atividade = st.text_input("Local da Atividade")
        with col2:
            placa_veiculo = st.text_input("Placa do Veículo")
        
        st.write("### ✅ CHECKLIST DETALHADO")
        c1, c2 = st.columns(2)
        with c1:
            uso_cinto = st.checkbox("Cinto de Segurança")
            uso_capacete = st.checkbox("Capacete Classe B")
            amarracao_escada = st.checkbox("Amarração da Escada")
            chuva = st.checkbox("Chuva")
            animais_peconhetos = st.checkbox("Animais Peçonhentos")
        with c2:
            area_sinalizada = st.checkbox("Sinalização da área")
            verificacao_geral = st.checkbox("Verificação Geral")
            poste_energizado = st.selectbox("Poste Energizado?", ["Não", "Sim"])
            integridade_poste = st.selectbox("Integridade do Poste", ["Bom", "Ruim"])
        
        st.divider()
        houve_paralisacao = st.checkbox("Houve interrupção das atividades?")
        foto_paralisacao = st.file_uploader("📸 Foto da ocorrência", type=['jpg', 'png', 'jpeg'])
        motivo_paralisacao = st.text_area("MOTIVO DA PARALISAÇÃO")
        
        if st.button("REGISTRAR APR"):
            url_foto = ""
            if foto_paralisacao:
                try:
                    timestamp = int(time.time())
                    caminho = f"fotos/{timestamp}_{foto_paralisacao.name}"
                    supabase.storage.from_("fotos_atendimentos").upload(caminho, foto_paralisacao.getvalue())
                    url_foto = caminho
                except Exception as e:
                    st.error(f"Erro no upload: {e}")
            
            if houve_paralisacao and not url_foto:
                st.error("Atenção: A foto é obrigatória para serviços paralisados!")
            else:
                try:
                    supabase.table("APR").insert({
                        "data_atividade": str(data_atividade),
                        "local_atividade": local_atividade,
                        "equipe": st.session_state.nome_tecnico,
                        "placa_veiculo": placa_veiculo,
                        "uso_cinto": uso_cinto,
                        "uso_capacete": uso_capacete,
                        "amarracao_escada": amarracao_escada,
                        "area_sinalizada": area_sinalizada,
                        "verificacao_geral": verificacao_geral,
                        
                        # Conversão dos selects para booleano:
                        "animais_peconhetos": True if animais_peconhetos == "Sim" else False,
                        "chuva": True if chuva == "Sim" else False,
                        "poste_energizado": True if poste_energizado == "Sim" else False,
                        
                        # Para este, se a coluna for texto, mantenha como está. Se for boolean, converta:
                        "integridade_poste": integridade_poste, 
                        
                        "houve_paralisacao": houve_paralisacao,
                        "motivo_paralisacao": motivo_paralisacao,
                        "responsavel": st.session_state.nome_tecnico,
                        "foto_paralisacao": url_foto,
                        "perfil": st.session_state.perfil
                    }).execute()
                    st.success("APR registrada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    with aba4:
        st.subheader("ADMINISTRAÇÃO DE PERFIS")
        senha_admin = st.text_input("DIGITE A SENHA MESTRA:", type="password", key="admin_senha")
        
        if senha_admin == "123456":
            usuarios = supabase.table("TECNICOS").select("*").execute()
            
            edited_data = st.data_editor(usuarios.data, column_config={
                "perfil": st.column_config.SelectboxColumn(
                    "PERFIL",
                    options=["Técnico", "Assistente", "Administrador"],
                    required=True,
                )
            })
            
            if st.button("SALVAR PERFIS"):
                sucesso = True
                for row in edited_data:
                    try:
                        supabase.table("TECNICOS").update({"perfil": row["perfil"]}).eq("cpf", row["cpf"]).execute()
                    except:
                        sucesso = False
                if sucesso:
                    st.success("PERFIS ATUALIZADOS!")
                    st.rerun()
        elif senha_admin:
            st.error("SENHA INCORRETA!")
