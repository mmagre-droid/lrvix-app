import streamlit as st
from supabase import create_client
import time
import random
import string

def gerar_codigo_apr():
    letras = ''.join(random.choices(string.ascii_uppercase, k=4))
    numeros = ''.join(random.choices(string.digits, k=3))
    return f"{letras}{numeros}"

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
            "foto": foto_url,
            "responsavel": st.session_state.nome_tecnico  # Agora com "ns"
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
                        # Geração de nome único
                        timestamp = int(time.time())
                        caminho = f"fotos/{timestamp}_{foto_arquivo.name}"
                        supabase.storage.from_("fotos_atendimentos").upload(caminho, foto_arquivo.getvalue())
                        url_foto = caminho
                    except Exception as e:
                        st.error(f"Erro ao subir foto: {e}")
                
                if registrar_atendimento(data_execucao, cliente, endereco, protocolo, mercado, tipo_servico, observacao, url_foto):
                    st.success("Atendimento registrado com sucesso!")

    with aba2:
        st.subheader("📊 Meus Atendimentos (Internos e Externos)")
        
        try:
            atendimentos = supabase.table("ATENDIMENTO")\
                .select("*")\
                .eq("responsavel", st.session_state.nome_tecnico)\
                .in_("tipo_servico", ["INTERNO", "EXTERNO"])\
                .execute()
                
            if atendimentos.data:
                import pandas as pd
                df = pd.DataFrame(atendimentos.data)
                colunas_para_ocultar = ['id', 'created_at', 'responsavel']
                df_exibicao = df.drop(columns=[c for c in colunas_para_ocultar if c in df.columns])
                
                
                # Gera um CSV, que não precisa de bibliotecas extras

                csv = df_exibicao.to_csv(index=False).encode('utf-8')                
                st.download_button(
                    label="📥 Baixar tabela em CSV",
                    data=csv,
                    file_name="atendimentos.csv",
                    mime="text/csv"
                )

            else:
                st.info("Você ainda não possui atendimentos internos ou externos registrados.")
        except Exception as e:
            st.error(f"Erro ao buscar: {e}")

    with aba3:
            
            st.subheader("⚠️ ANÁLISE PRELIMINAR DE RISCO (APR)")
    
    # --- FORMULÁRIO DE PREENCHIMENTO ---
    # Certifique-se de que estas variáveis correspondam exatamente aos seus campos
    integridade_poste = st.selectbox("Integridade do Poste:", ["Bom", "Regular", "Ruim"])
    houve_paralisacao = st.radio("Houve paralisação?", ["Sim", "Não"])
    motivo_paralisacao = st.text_input("Motivo da paralisação (se houver):")
    # Nota: certifique-se de que 'url_foto' esteja sendo definida anteriormente no seu código
    
    if st.button("Salvar APR"):
        try:
            # 1. Geração do código único
            codigo_unico = gerar_codigo_apr()
            
            # 2. Inserção no Supabase
            supabase.table("APR").insert({
                "integridade_poste": integridade_poste,
                "houve_paralisacao": houve_paralisacao,
                "motivo_paralisacao": motivo_paralisacao,
                "responsavel": st.session_state.nome_tecnico,
                "foto_paralisacao": url_foto,
                "perfil": st.session_state.perfil,
                "codigo_apr": codigo_unico,
            }).execute()
            
            st.success(f"APR registrada com sucesso! Código: {codigo_unico}")
            
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

    # --- BUSCA E PDF ---
    st.divider()
    st.subheader("🔍 Buscar e Exportar APR")
    
    busca_codigo = st.text_input("Digite o código da APR para buscar:")
    
    if busca_codigo:
        resultado = supabase.table("APR").select("*").eq("codigo_apr", busca_codigo).execute()
        
        if resultado.data:
            apr_data = resultado.data[0]
            st.write("Dados encontrados:", apr_data)
            
            # Lógica para PDF (requer: pip install fpdf)
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Relatorio APR: {apr_data['codigo_apr']}", ln=True, align='C')
            pdf.cell(200, 10, txt=f"Tecnico: {apr_data['responsavel']}", ln=True)
            pdf.cell(200, 10, txt=f"Integridade Poste: {apr_data['integridade_poste']}", ln=True)
            
            # Transforma em bytes para o download
            pdf_output = pdf.output(dest='S').encode('latin-1')
            
            st.download_button(
                label="📥 Baixar PDF da APR",
                data=pdf_output,
                file_name=f"APR_{busca_codigo}.pdf",
                mime="application/pdf"
            )
        else:
            st.warning("Código não encontrado.")

                    
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
