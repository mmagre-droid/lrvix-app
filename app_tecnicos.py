import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="LRVIX - Controle Operacional",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILIZAÇÃO CSS (PADRÃO BRANCO E AZUL) ---
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        .stApp {
            background-color: #ffffff;
            color: #1e293b;
        }
        
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        .stButton>button {
            width: 100%;
            border-radius: 6px;
            font-weight: bold;
            height: 42px;
            background-color: #0284c7;
            color: white;
            border: none;
        }
        .stButton>button:hover {
            background-color: #0369a1;
            color: white;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #f0f9ff;
            border-radius: 6px 6px 0px 0px;
            color: #0369a1;
            font-weight: bold;
        }
        .stTabs [aria-selected="true"] {
            background-color: #0284c7 !important;
            color: white !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM O SUPABASE ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- CONTROLE DE SESSÃO DE LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "cpf_tecnico" not in st.session_state:
    st.session_state.cpf_tecnico = None
if "nome_tecnico" not in st.session_state:
    st.session_state.nome_tecnico = None

# --- TELA DE LOGIN ---
if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #0284c7;'>⚡ LRVIX Telecom</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Controle Operacional e APR</p>", unsafe_allow_html=True)
        
        with st.container():
            st.markdown("---")
            cpf_input = st.text_input("CPF do Técnico ou Administrador", placeholder="Digite seu CPF...")
            senha_input = st.text_input("Senha", type="password", placeholder="Digite sua senha...")
            
            if st.button("Acessar Sistema", use_container_width=True):
                if cpf_input and senha_input:
                    try:
                        res = supabase.table("tecnicos").select("*").eq("cpf", cpf_input).eq("senha", senha_input).execute()
                        if res.data:
                            user = res.data[0]
                            st.session_state.autenticado = True
                            st.session_state.perfil = user.get("perfil")
                            st.session_state.cpf_tecnico = user.get("cpf")
                            st.session_state.nome_tecnico = user.get("nome")
                            st.rerun()
                        else:
                            st.error("CPF ou senha incorretos.")
                    except Exception as e:
                        st.error(f"Erro ao conectar com o banco: {e}")
                else:
                    st.warning("Preencha todos os campos.")
        st.markdown("---")
        
else:
    # --- CABEÇALHO DO SISTEMA LOGADO ---
    col_topo1, col_topo2 = st.columns([3, 1])
    with col_topo1:
        st.markdown(f"### ⚡ Olá, **{st.session_state.get('nome_tecnico', 'Usuário')}**")
        st.caption(f"Perfil: **{st.session_state.perfil}**")
    with col_topo2:
        if st.button("🚪 Sair do Sistema"):
            st.session_state.autenticado = False
            st.session_state.perfil = None
            st.session_state.cpf_tecnico = None
            st.session_state.nome_tecnico = None
            st.rerun()

    st.markdown("---")

    # --- ABAS DO APLICATIVO ---
    aba1, aba2 = st.tabs(["📝 Registrar Atendimento / APR", "📊 Relatórios de Produtividade"])

    # ==========================================
    # ABA 1: FORMULÁRIO (ATENDIMENTO / APR)
    # ==========================================
    with aba1:
        st.subheader("Novo Lançamento Operacional")
        
        with st.form("form_atendimento", clear_on_submit=True):
            st.markdown("#### Informações do Atendimento")
            c1, c2 = st.columns(2)
            with c1:
                data_execucao = st.date_input("Data de Execução", value=datetime.today())
                cliente = st.text_input("Nome do Cliente")
                protocolo = st.text_input("Número do Protocolo")
            with c2:
                endereco = st.text_input("Endereço")
                tipo_servico = st.selectbox("Tipo de Serviço", ["REPARO", "INSTALAÇÃO", "MANUTENÇÃO"])
                mercado = st.selectbox("Mercado", ["INTERNO", "EXTERNO", "IMPRODUTIVO"])

            st.markdown("#### Detalhes e Observações")
            observacao = st.text_area("Observação / Relato do Serviço")
            metragem_cabo = st.text_input("Metragem de Cabo Utilizada (se aplicável)")
            
            fotos_atendimento = st.file_uploader("Anexar Fotos do Atendimento (Pode selecionar várias)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

            st.markdown("---")
            st.markdown("#### APR - Análise Preliminar de Risco")
            risco_identificado = st.text_input("Riscos Identificados na Activity / Atividade")
            medida_controle = st.text_input("Medidas de Controle Aplicadas")
            paralisacao = st.selectbox("Houve paralisação da atividade?", ["NÃO", "SIM"])
            
            fotos_paralisacao = []
            if paralisacao == "SIM":
                fotos_paralisacao = st.file_uploader("Fotos da Paralisação", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button("Salvar Registro Completo", use_container_width=True)

            if submit_button:
                if not cliente or not protocolo:
                    st.error("Preencha ao menos o Cliente e o Protocolo.")
                else:
                    try:
                        lista_caminhos_fotos = []
                        if fotos_atendimento:
                            for foto_arq in fotos_atendimento:
                                nome_arquivo_storage = f"fotos/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{foto_arq.name}"
                                supabase.storage.from_("fotos_atendimentos").upload(nome_arquivo_storage, foto_arq.getvalue())
                                lista_caminhos_fotos.append(nome_arquivo_storage)

                        lista_caminhos_apr = []
                        if fotos_paralisacao:
                            for foto_apr in fotos_paralisacao:
                                nome_apr_storage = f"fotos_apr/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{foto_apr.name}"
                                supabase.storage.from_("fotos_atendimentos").upload(nome_apr_storage, foto_apr.getvalue())
                                lista_caminhos_apr.append(nome_apr_storage)

                        dados_atendimento = {
                            "data_execucao": str(data_execucao),
                            "cliente": cliente,
                            "protocolo": protocolo,
                            "endereco": endereco,
                            "tipo_servico": tipo_servico,
                            "mercado": mercado,
                            "observacao": observacao,
                            "metragem_cabo": metragem_cabo,
                            "foto": lista_caminhos_fotos,
                            "responsavel": st.session_state.get("nome_tecnico"),
                            "cpf_tecnico": st.session_state.get("cpf_tecnico")
                        }
                        supabase.table("ATENDIMENTO").insert(dados_atendimento).execute()

                        dados_apr = {
                            "data_execucao": str(data_execucao),
                            "protocolo": protocolo,
                            "risco": risco_identificado,
                            "medida_controle": medida_controle,
                            "paralisacao": paralisacao,
                            "foto_paralisacao": lista_caminhos_apr,
                            "cpf_tecnico": st.session_state.get("cpf_tecnico")
                        }
                        supabase.table("APR").insert(dados_apr).execute()

                        st.success("Atendimento e APR salvos com sucesso no sistema!")
                    except Exception as e:
                        st.error(f"Erro ao salvar dados: {e}")

    # ==========================================
    # ABA 2: RELATÓRIOS E VISUALIZADOR DE FOTOS
    # ==========================================
    with aba2: 
        st.subheader("Lista de Atendimentos Realizados")
        
        query = supabase.table("ATENDIMENTO").select("*")
        
        if st.session_state.perfil != "Administrador":
            query = query.eq("cpf_tecnico", st.session_state.cpf_tecnico)
        
        atendimentos = query.execute()
            
        if atendimentos.data:
            df = pd.DataFrame(atendimentos.data)
            
            if 'data_execucao' in df.columns:
                df['data_execucao'] = pd.to_datetime(df['data_execucao'], errors='coerce').dt.strftime('%d/%m/%Y')
            
            colunas_para_ocultar = ['id', 'created_at', 'cpf_tecnico']
            df_exibicao = df[[col for col in df.columns if col not in colunas_para_ocultar]]
            st.dataframe(df_exibicao, use_container_width=True)
            
            # --- VISUALIZADOR DE FOTOS (EXCLUSIVO PARA ADMINISTRADOR) ---
            if st.session_state.get("perfil") == "Administrador":
                st.divider()
                st.subheader("🖼️ Visualizador de Fotos do Atendimento")
                
                opcoes_atendimento = {}
                for item in atendimentos.data:
                    data_original = item.get('data_execucao', '')
                    try:
                        data_formatada = pd.to_datetime(data_original).strftime('%d/%m/%Y')
                    except Exception:
                        data_formatada = data_original
                    
                    label = f"Data: {data_formatada} | Prot: {item.get('protocolo', 'N/A')} | Cliente: {item.get('cliente', 'N/A')}"
                    opcoes_atendimento[label] = item
                    
                atendimento_selecionado = st.selectbox(
                    "Selecione um atendimento para visualizar as fotos anexadas:", 
                    ["Selecione..."] + list(opcoes_atendimento.keys())
                )
                
                if atendimento_selecionado != "Selecione...":
                    dados_selecionados = opcoes_atendimento[atendimento_selecionado]
                    fotos = dados_selecionados.get("foto")
                    
                    if not fotos or fotos == ['{}'] or fotos == []:
                        st.info("Nenhuma foto anexada a este atendimento.")
                    else:
                        if isinstance(fotos, str):
                            fotos = [fotos]
                            
                        fotos_validas = [f for f in fotos if f and f.strip() != "" and f != '{}']
                        
                        if len(fotos_validas) > 0:
                            st.write(f"**{len(fotos_validas)} foto(s) encontrada(s):**")
                            cols = st.columns(len(fotos_validas))
                            
                            for idx, caminho_foto in enumerate(fotos_validas):
                                with cols[idx]:
                                    try:
                                        res_bytes = supabase.storage.from_("fotos_atendimentos").download(caminho_foto)
                                        st.image(res_bytes, caption=f"Anexo {idx+1}", use_column_width=True)
                                    except Exception as e:
                                        st.error(f"Erro ao carregar a foto {idx+1}")
                        else:
                            st.info("Nenhuma foto válida anexada a este atendimento.")
                        
        else:
            st.info("Nenhum atendimento registrado.")
