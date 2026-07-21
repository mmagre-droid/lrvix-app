import streamlit as st
import pandas as pd
import time
from supabase import create_client
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

# --- CONFIGURAÇÃO ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

# Inicialização do Cliente Supabase
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

# Função para incluir atendimento
def registrar_atendimento(data_execucao, cliente, endereco, protocolo, mercado, tipo_servico, observacao, foto_url, nome_tecnico, cpf_tecnico, metragem_cabo):
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
            "responsavel": nome_tecnico,
            "cpf_tecnico": cpf_tecnico,
            "metragem_cabo": metragem_cabo
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# Função para gerar o PDF da APR corretamente
def gerar_pdf_apr(apr_id):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        
        pasta_destino = "aprs_geradas"
        os.makedirs(pasta_destino, exist_ok=True)
        
        dados_apr = supabase.table("APR").select("*").eq("id", apr_id).execute()
        nome_arquivo = os.path.join(pasta_destino, f"apr_{apr_id}.pdf")
        
        # Configuração do documento (Margens otimizadas para ocupar melhor a folha)
        doc = SimpleDocTemplate(
            nome_arquivo, 
            pagesize=letter,
            rightMargin=30, leftMargin=30,
            topMargin=30, bottomMargin=30
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Estilos personalizados para padronizar o visual
        estilo_titulo = ParagraphStyle(
            'TituloPrincipal',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=colors.HexColor('#1f2937'),
            alignment=1, # Centralizado
            spaceAfter=10
        )
        
        estilo_secao = ParagraphStyle(
            'TituloSecao',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.HexColor('#ffffff'),
            spaceBefore=0,
            spaceAfter=0
        )
        
        estilo_texto = ParagraphStyle(
            'TextoNormal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.HexColor('#374151')
        )
        
        estilo_texto_bold = ParagraphStyle(
            'TextoBold',
            parent=estilo_texto,
            fontName='Helvetica-Bold'
        )

        if dados_apr.data:
            item = dados_apr.data[0]
            num_controle = item.get('numero_controle') or item.get('id') or 'N/A'
            
            # --- CABEÇALHO ---
            story.append(Paragraph("<b>LRVIX - SISTEMA DE GESTÃO TÉCNICA</b>", estilo_titulo))
            story.append(Paragraph(f"<b>ANÁLISE PRELIMINAR DE RISCO (APR) - Nº {num_controle}</b>", estilo_titulo))
            story.append(Spacer(1, 10))
            
            # --- BLOCO 1: DADOS GERAIS ---
            dados_gerais = [
                [Paragraph("<b>DADOS DA ATIVIDADE</b>", estilo_secao), ""],
                [Paragraph(f"<b>Data da Atividade:</b> {item.get('data_atividade', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Placa do Veículo:</b> {item.get('placa_veiculo', 'N/A')}", estilo_texto)],
                [Paragraph(f"<b>Local da Atividade:</b> {item.get('local_atividade', 'N/A')}", estilo_texto), ""]
            ]
            
            tabela_geral = Table(dados_gerais, colWidths=[270, 270])
            tabela_geral.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)), # Mescla o cabeçalho da seção
                ('SPAN', (0, 2), (1, 2)), # Mescla o local para ocupar a largura toda
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1f2937')), # Cor de fundo do cabeçalho
                ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ]))
            story.append(tabela_geral)
            story.append(Spacer(1, 15))
            
            # --- BLOCO 2: CHECKLIST DETALHADO ---
            dados_checklist = [
                [Paragraph("<b>CHECKLIST DE SEGURANÇA E CONDIÇÕES</b>", estilo_secao), ""],
                [Paragraph("<b>Item de Verificação</b>", estilo_texto_bold), Paragraph("<b>Status / Resposta</b>", estilo_texto_bold)],
                [Paragraph("Cinto de Segurança", estilo_texto), Paragraph(str(item.get('uso_cinto', 'N/A')), estilo_texto)],
                [Paragraph("Capacete Classe B", estilo_texto), Paragraph(str(item.get('uso_capacete', 'N/A')), estilo_texto)],
                [Paragraph("Amarração da Escada", estilo_texto), Paragraph(str(item.get('amarracao_escada', 'N/A')), estilo_texto)],
                [Paragraph("Sinalização da Área", estilo_texto), Paragraph(str(item.get('area_sinalizada', 'N/A')), estilo_texto)],
                [Paragraph("Verificação Geral", estilo_texto), Paragraph(str(item.get('verificacao_geral', 'N/A')), estilo_texto)],
                [Paragraph("Chuva", estilo_texto), Paragraph(str(item.get('chuva', 'N/A')), estilo_texto)],
                [Paragraph("Animais Peçonhentos", estilo_texto), Paragraph(str(item.get('animais_peconhetos', 'N/A')), estilo_texto)],
                [Paragraph("Poste Energizado", estilo_texto), Paragraph(str(item.get('poste_energizado', 'N/A')), estilo_texto)],
                [Paragraph("Integridade do Poste", estilo_texto), Paragraph(str(item.get('integridade_poste', 'N/A')), estilo_texto)],
            ]
            
            tabela_check = Table(dados_checklist, colWidths=[350, 190])
            tabela_check.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1f2937')),
                ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#e5e7eb')), # Fundo cinza claro para o cabeçalho da tabela
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ]))
            story.append(tabela_check)
            story.append(Spacer(1, 15))
            
            # --- BLOCO 3: PARALISAÇÃO ---
            dados_paralisacao = [
                [Paragraph("<b>STATUS DE INTERRUPÇÃO / PARALISAÇÃO</b>", estilo_secao), ""],
                [Paragraph(f"<b>Houve Interrupção das Atividades:</b> {item.get('houve_paralisacao', 'N/A')}", estilo_texto), ""],
                [Paragraph(f"<b>Motivo da Paralisação:</b><br/>{item.get('motivo_paralisacao') or 'Nenhum motivo informado.'}", estilo_texto), ""]
            ]
            
            tabela_paralisa = Table(dados_paralisacao, colWidths=[540, 0])
            tabela_paralisa.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('SPAN', (0, 1), (1, 1)),
                ('SPAN', (0, 2), (1, 2)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ]))
            story.append(tabela_paralisa)
            
        else:
            story.append(Paragraph("Detalhes da APR não encontrados no banco.", estilo_texto))
            
        doc.build(story)
        return nome_arquivo
        
    except Exception as e:
        # Fallback de segurança caso ocorra algum erro na estilização
        pasta_destino = "aprs_geradas"
        os.makedirs(pasta_destino, exist_ok=True)
        nome_arquivo = os.path.join(pasta_destino, "erro_apr.pdf")
        c = canvas.Canvas(nome_arquivo, pagesize=letter)
        c.drawString(50, 750, f"Erro ao gerar PDF: {str(e)}")
        c.save()
        return nome_arquivo
    
if not st.session_state.logado:
    tab1, tab2 = st.tabs(["Login", "Cadastrar Técnico"])
    with tab1:
        cpf_input = st.text_input("CPF")
        senha_input = st.text_input("Senha", type="password", key="login_senha")
            
        if st.button("Entrar"):
            try:
                user_query = supabase.table("TECNICOS").select("*").eq("cpf", str(cpf_input).strip()).execute()
                
                if user_query.data and str(user_query.data[0].get("senha")) == str(senha_input).strip():
                    dados_user = user_query.data[0]
                    if dados_user.get("ativo") is True:
                        st.session_state.logado = True
                        st.session_state.nome_tecnico = dados_user["nome"]
                        st.session_state.perfil = dados_user["perfil"]
                        st.session_state.cpf_tecnico = dados_user["cpf"]
                        st.rerun()
                    else:
                        st.error("⚠️ Este usuário está inativo.")
                else:
                    st.error("❌ CPF ou Senha incorretos.")
            except Exception as e:
                st.error(f"Erro na conexão com o banco: {e}")
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
    
    if st.session_state.perfil == "Administrador":
        aba1, aba2, aba3, aba4 = st.tabs(["📝 FORMULÁRIO", "📊 PRODUTIVIDADE", "⚠️ APR", "⚙️ ADMIN"])
    else:
        aba1, aba2, aba3 = st.tabs(["📝 FORMULÁRIO", "📊 PRODUTIVIDADE", "⚠️ APR"])
        aba4 = None

    with aba1:
        with st.form("form_atendimento", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                data_execucao = st.date_input("DATA DA EXECUÇÃO", format="DD/MM/YYYY")
                cliente = st.text_input("NOME DO CLIENTE")
                endereco = st.text_input("ENDEREÇO")
                metragem_cabo = st.text_input("CABO UTILIZADO")
            with c2:
                protocolo = st.text_input("PROTOCOLO")
                mercado = st.selectbox("MERCADO", ["REPARO", "ATIVAÇÃO", "RETIRADA"])
                tipo_servico = st.selectbox("TIPO DE SERVIÇO", ["INTERNO", "EXTERNO", "IMPRODUTIVO"])
            
            observacao = st.text_area("OBSERVAÇÃO")
            foto_arquivo = st.file_uploader("FOTO DO SERVIÇO", type=['jpg', 'png', 'jpeg'])
            
            if st.form_submit_button("REGISTRAR ATENDIMENTO"):
                if not cliente or not endereco or not protocolo or not metragem_cabo:
                    st.error("⚠️ Por favor, preencha todos os campos obrigatórios (Cliente, Endereço, Protocolo e Cabo Utilizado).")
                else:
                    url_foto = ""
                    if foto_arquivo:
                        try:
                            timestamp = int(time.time())
                            caminho = f"fotos/{timestamp}_{foto_arquivo.name}"
                            supabase.storage.from_("fotos_atendimentos").upload(caminho, foto_arquivo.getvalue())
                            url_foto = caminho
                        except Exception as e:
                            st.error(f"Erro ao subir foto: {e}")
                    
                    if registrar_atendimento(
                        data_execucao, 
                        cliente, 
                        endereco, 
                        protocolo, 
                        mercado, 
                        tipo_servico, 
                        observacao, 
                        url_foto, 
                        st.session_state.nome_tecnico, 
                        st.session_state.cpf_tecnico, 
                        metragem_cabo
                    ):
                        st.success("Atendimento registrado com sucesso!")
            
    with aba2: 
        st.subheader("Lista de Atendimentos")
        
        query = supabase.table("ATENDIMENTO").select("*")
        
        if st.session_state.perfil != "Administrador":
            query = query.eq("cpf_tecnico", st.session_state.cpf_tecnico)
        
        atendimentos = query.execute()
            
        if atendimentos.data:
            df = pd.DataFrame(atendimentos.data)
            colunas_para_ocultar = ['id', 'created_at', 'cpf_tecnico']
            df_exibicao = df[[col for col in df.columns if col not in colunas_para_ocultar]]
            st.dataframe(df_exibicao, use_container_width=True)
        else:
            st.info("Nenhum atendimento registrado.")

    with aba3:
        st.subheader("⚠️ ANÁLISE PRELIMINAR DE RISCO (APR)")
        
        with st.expander("📂 APRs Cadastradas", expanded=False):
            try:
                query_aprs = supabase.table("APR").select("id, numero_controle")
                
                if st.session_state.get("perfil") != "Administrador":
                    query_aprs = query_aprs.eq("cpf_tecnico", st.session_state.get("cpf_tecnico", ""))
                
                lista_aprs = query_aprs.order("numero_controle", desc=True).execute()
                
                if lista_aprs.data:
                    cols = st.columns(4)
                    for i, item in enumerate(lista_aprs.data):
                        with cols[i % 4]:
                            if st.button(f"📄 APR {item['numero_controle']}", key=f"apr_{item['id']}"):
                                arquivo = gerar_pdf_apr(item['id'])
                                with open(arquivo, "rb") as f:
                                    st.download_button(
                                        label="📥 BAIXAR PDF",
                                        data=f,
                                        file_name=arquivo,
                                        mime="application/pdf"
                                    )
                else:
                    st.info("Nenhuma APR cadastrada.")
            except Exception as e:
                st.error(f"Erro ao listar APRs: {e}")

        st.divider()
        
        with st.form("form_apr", clear_on_submit=True):
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
                area_sinalizada = st.checkbox("Sinalização da área")
                verificacao_geral = st.checkbox("Verificação Geral")
            with c2:
                chuva = st.selectbox("Chuva", ["Não", "Sim"])
                animais_peconhetos = st.selectbox("Animais Peçonhentos", ["Não", "Sim"])
                poste_energizado = st.selectbox("Poste Energizado?", ["Não", "Sim"])
                integridade_poste = st.selectbox("Integridade do Poste", ["Bom", "Ruim"])
            
            st.divider()
            houve_paralisacao = st.checkbox("Houve interrupção das atividades?")
            foto_paralisacao = st.file_uploader("📸 Foto da ocorrência", type=['jpg', 'png', 'jpeg'])
            motivo_paralisacao = st.text_area("MOTIVO DA PARALISAÇÃO")
            
            if st.form_submit_button("REGISTRAR APR"):
                url_foto = ""
                if foto_paralisacao:
                    try:
                        timestamp = int(time.time())
                        caminho = f"fotos/{timestamp}_{foto_paralisacao.name}"
                        supabase.storage.from_("fotos_atendimentos").upload(caminho, foto_paralisacao.getvalue())
                        url_foto = caminho
                    except Exception as e:
                        st.error(f"Erro ao subir foto: {e}")
                
                try:
                    cpf_logado = st.session_state.get("cpf_tecnico", "")

                    resposta = supabase.table("APR").insert({
                        "data_atividade": str(data_atividade),
                        "local_atividade": local_atividade,
                        "placa_veiculo": placa_veiculo,
                        "uso_cinto": bool(uso_cinto),
                        "uso_capacete": bool(uso_capacete),
                        "amarracao_escada": bool(amarracao_escada),
                        "area_sinalizada": bool(area_sinalizada),
                        "verificacao_geral": bool(verificacao_geral),
                        "chuva": True if chuva == "Sim" else False,
                        "animais_peconhetos": True if animais_peconhetos == "Sim" else False,
                        "poste_energizado": True if poste_energizado == "Sim" else False,
                        "integridade_poste": integridade_poste,
                        "houve_paralisacao": bool(houve_paralisacao),
                        "motivo_paralisacao": motivo_paralisacao,
                        "foto_paralisacao": url_foto,
                        "cpf_tecnico": cpf_logado
                    }).execute()
                    
                    st.success("APR registrada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar APR no banco: {e}")
                    
    if aba4 is not None: 
        with aba4:
            st.subheader("⚙️ PAINEL ADMINISTRATIVO")
            
            opcao_admin = st.radio("O que deseja gerenciar?", ["Perfis de Usuários", "💰 Tabela LPU"])
            senha_admin = st.text_input("DIGITE A SENHA MESTRA:", type="password", key="admin_senha")

            if senha_admin == "123456":
                if opcao_admin == "Perfis de Usuários":
                    st.write("### 👤 Gerenciamento de Perfis")
                    try:
                        dados_tecnicos = supabase.table("TECNICOS").select("*").execute()
                        df_tecnicos = pd.DataFrame(dados_tecnicos.data)
                        edited_df = st.data_editor(df_tecnicos, use_container_width=True)

                        if st.button("SALVAR PERFIS"):
                            for index, row in edited_df.iterrows():
                                supabase.table("TECNICOS").update({
                                    "nome": row["nome"],
                                    "cpf": row["cpf"],
                                    "email": row["email"],
                                    "telefone": row["telefone"],
                                    "ativo": row["ativo"],
                                    "perfil": row["perfil"]
                                }).eq("id", row["id"]).execute()
                            st.success("Perfis atualizados!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao carregar perfis: {e}")

                elif opcao_admin == "💰 Tabela LPU":
                    st.write("### 💰 Gerenciamento da LPU")
                    try:
                        dados_lpu = supabase.table("LPU").select("*").execute()
                        
                        if not dados_lpu.data:
                            df_lpu = pd.DataFrame(columns=["servico", "valor"])
                        else:
                            df_lpu = pd.DataFrame(dados_lpu.data)
                        
                        df_editada_lpu = st.data_editor(
                            df_lpu, 
                            use_container_width=True, 
                            num_rows="dynamic" 
                        )

                        if st.button("SALVAR LPU"):
                            with st.spinner("Salvando..."):
                                for index, row in df_editada_lpu.iterrows():
                                    if "id" in row and pd.notnull(row["id"]):
                                        supabase.table("LPU").update({
                                            "servico": row["servico"],
                                            "valor": row["valor"]
                                        }).eq("id", row["id"]).execute()
                                    elif row["servico"]:
                                        supabase.table("LPU").insert({
                                            "servico": row["servico"],
                                            "valor": row["valor"]
                                        }).execute()
                                st.success("Tabela LPU atualizada com sucesso!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao acessar tabela LPU: {e}")
