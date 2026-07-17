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
# Estado específico para a APR reativa
if "chk_paralisacao" not in st.session_state:
    st.session_state.chk_paralisacao = False

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

def atualizar_estado_apr():
    st.session_state.chk_paralisacao = st.session_state.paralisacao_key

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
                        caminho = f"fotos/{foto_arquivo.name}"
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
        st.info("Trabalho em Altura com Risco Elétrico[cite: 1]")
        st.write(f"**Equipe (Técnico):** {st.session_state.nome_tecnico}")
        
        with st.form("form_apr", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                data_atividade = st.date_input("Data da Atividade")
                local_atividade = st.text_input("Local da Atividade")
            with col2:
                placa_veiculo = st.text_input("Placa do Veículo")
            
            st.divider()
            st.write("### ✅ CHECKLIST DE EPIs E EPCs[cite: 1]")
            c1, c2 = st.columns(2)
            with c1:
                uso_cinto = st.checkbox("Cinto de Segurança (Inspeção OK)[cite: 1]")
                talabarte = st.checkbox("Talabarte Duplo (Inspeção OK)[cite: 1]")
                luvas = st.checkbox("Luvas Isolantes (Teste de ar OK)[cite: 1]")
            with c2:
                uso_capacete = st.checkbox("Capacete Classe B (Validade OK)[cite: 1]")
                area_sinalizada = st.checkbox("Sinalização da área inferior (EPC)[cite: 1]")
                verificacao_geral = st.checkbox("Verificação Geral concluída[cite: 1]")
            
            st.divider()
            
            # Checkbox com callback para interface reativa
            houve_paralisacao = st.checkbox(
                "Houve interrupção das atividades por condições inseguras?[cite: 1]",
                key="paralisacao_key",
                on_change=atualizar_estado_apr
            )
            
            foto_paralisacao = None
            if st.session_state.chk_paralisacao:
                st.warning("⚠️ Devido à interrupção, o envio de uma foto do local é obrigatório.")
                foto_paralisacao = st.file_uploader("📸 Foto da ocorrência (Obrigatório)", type=['jpg', 'png', 'jpeg'])
            
            motivo_paralisacao = st.text_area("MOTIVO DA PARALISAÇÃO E AÇÕES ADOTADAS[cite: 1]")
            
            if st.form_submit_button("REGISTRAR APR"):
                if st.session_state.chk_paralisacao and not foto_paralisacao:
                    st.error("Erro: A foto é obrigatória quando o serviço é paralisado!")
                else:
                    caminho_foto = ""
                    if foto_paralisacao:
                        try:
                            caminho_foto = f"fotos_apr/{foto_paralisacao.name}"
                            supabase.storage.from_("fotos_atendimentos").upload(caminho_foto, foto_paralisacao.getvalue())
                        except Exception as e:
                            st.error(f"Erro ao subir foto: {e}")

                    try:
                        supabase.table("APR").insert({
                            "data_atividade": str(data_atividade),
                            "local_atividade": local_atividade,
                            "equipe": st.session_state.nome_tecnico,
                            "placa_veiculo": placa_veiculo,
                            "uso_cinto": uso_cinto,
                            "uso_capacete": uso_capacete,
                            "area_sinalizada": area_sinalizada,
                            "houve_paralisacao": st.session_state.chk_paralisacao,
                            "motivo_paralisacao": motivo_paralisacao,
                            "foto_paralisacao": caminho_foto, # <--- Nova coluna gravada
                            "perfil": st.session_state.perfil
                        }).execute()
                        st.success("APR registrada com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar APR: {e}")

    with aba4:
        st.subheader("ADMINISTRAÇÃO DE PERFIS")
        senha_admin = st.text_input("DIGITE A SENHA MESTRA:", type="password", key="admin_senha")
        if senha_admin == "123456":
            usuarios = supabase.table("TECNICOS").select("*").execute()
            edited_data = st.data_editor(usuarios.data, column_config={
                "perfil": st.column_config.SelectboxColumn("PERFIL", options=["Técnico", "Assistente", "Administrador"], required=True)
            })
            if st.button("SALVAR PERFIS"):
                for row in edited_data:
                    supabase.table("TECNICOS").update({"perfil": row["perfil"]}).eq("cpf", row["cpf"]).execute()
                st.success("PERFIS ATUALIZADOS!")
                st.rerun()
        elif senha_admin:
            st.error("SENHA INCORRETA!")
