import streamlit as st
import pandas as pd
import time
from supabase import create_client
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="LRVIX - Sistema de Gestão Técnica",
    page_icon="⚡",
    layout="wide"
)

# --- ESTILIZAÇÃO CSS (OCULTA CABEÇALHO, MENU E ÍCONE DO GITHUB) ---
st.markdown("""
    <style>
        /* Oculta completamente o cabeçalho superior padrão do Streamlit */
        header {visibility: hidden !important;}
        #MainMenu {visibility: hidden !important;}
        footer {visibility: hidden !important;}
        
        /* Ajuste de espaçamento geral */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }
        
        /* Estilo para cartões e blocos */
        div.stButton > button {
            border-radius: 6px;
            font-weight: 500;
        }
        
        /* Ajuste de abas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            white-space: pre-wrap;
            border-radius: 4px 4px 0px 0px;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONFIGURAÇÃO ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

supabase = create_client(url, key)

if "logado" not in st.session_state:
    st.session_state.logado = False
if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False

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

def calcular_valor_lpu(tipo_servico, metragem_cabo, mercado, observacao):
    """
    Calcula o valor do atendimento baseando-se nas faixas de metragem e tipo de serviço da LPU,
    incluindo o cálculo proporcional de adicionais para metragens acima do teto cadastrado.
    """
    try:
        res_lpu = supabase.table("LPU").select("*").execute()
        if not res_lpu.data:
            return 0.0
            
        obs = str(observacao).strip().upper()
        if "não autorizado" in obs or "nao autorizado" in obs:
            return 0.0
            
        servico_lower = str(tipo_servico).strip().lower()
        
        try:
            metragem = float(metragem_cabo) if metragem_cabo else 0.0
        except ValueError:
            metragem = 0.0
            
        # 1. Procura se existe faixa de metragem compatível exata na LPU
        for item in res_lpu.data:
            min_m = item.get("min_metragem")
            max_m = item.get("max_metragem")
            
            if min_m is not None and max_m is not None:
                if float(min_m) <= metragem <= float(max_m):
                    return float(item.get("valor", 0.0))
        
        # 2. Se a metragem for maior que a maior faixa cadastrada, calcula o adicional por bloco (ex: a cada 100m)
        faixas_com_metragem = [item for item in res_lpu.data if item.get("min_metragem") is not None and item.get("max_metragem") is not None]
        if faixas_com_metragem and metragem > 0:
            # Ordena pela maior metragem máxima para encontrar o teto
            maior_faixa = max(faixas_com_metragem, key=lambda x: float(x.get("max_metragem", 0)))
            teto_max = float(maior_faixa.get("max_metragem", 0))
            
            if metragem > teto_max:
                valor_base = float(maior_faixa.get("valor", 0.0))
                excedente = metragem - teto_max
                
                # Busca na LPU se existe um item específico de adicional por bloco (ex: ADCIONAL_100 ou similar)
                valor_adicional_bloco = 0.0
                for item in res_lpu.data:
                    serv_nome = str(item.get("servico", "")).strip().upper()
                    if "ADICIONAL" in serv_nome or "100" in serv_nome:
                        valor_adicional_bloco = float(item.get("valor", 0.0))
                        break
                
                # Se não achar um item específico de adicional, estima proporcionalmente com base na última faixa
                if valor_adicional_bloco == 0.0 and teto_max > 0:
                    # Assume proporcional ao bloco de 100m baseado na faixa limite
                    valor_adicional_bloco = valor_base * (100.0 / teto_max)
                
                blocos_extras = (excedente // 100.0) + (1 if excedente % 100.0 > 0 else 0)
                return valor_base + (blocos_extras * valor_adicional_bloco)
                    
        # 3. Se não caiu em faixa de metragem, busca pelo nome do serviço fixo
        for item in res_lpu.data:
            nome_servico = str(item.get("servico", "")).strip().lower()
            if nome_servico == servico_lower:
                return float(item.get("valor", 0.0))
                
        return 0.0
    except Exception as e:
        print(f"Erro ao calcular LPU por faixa: {e}")
        return 0.0

def registrar_atendimento(data_execucao, cliente, endereco, protocolo, mercado, tipo_servico, observacao, foto_url, nome_tecnico, cpf_tecnico, metragem_cabo, valor_total):
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
            "metragem_cabo": metragem_cabo,
            "valor_total": float(valor_total)
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def gerar_pdf_apr(apr_id):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        import os
        
        pasta_destino = "aprs_geradas"
        os.makedirs(pasta_destino, exist_ok=True)
        
        dados_apr = supabase.table("APR").select("*").eq("id", apr_id).execute()
        nome_arquivo = os.path.join(pasta_destino, f"apr_{apr_id}.pdf")
        
        doc = SimpleDocTemplate(
            nome_arquivo, 
            pagesize=letter,
            rightMargin=30, leftMargin=30,
            topMargin=30, bottomMargin=30
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        estilo_titulo = ParagraphStyle(
            'TituloPrincipal',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=colors.HexColor('#1f2937'),
            alignment=1,
            spaceAfter=10
        )
        
        estilo_secao = ParagraphStyle(
            'TituloSecao',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.white,
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

        def traduzir_bool(valor):
            if isinstance(valor, bool):
                return "Sim" if valor else "Não"
            if str(valor).lower() in ["true", "t", "1", "sim"]:
                return "Sim"
            if str(valor).lower() in ["false", "f", "0", "não", "nao"]:
                return "Não"
            return str(valor)

        if dados_apr.data:
            item = dados_apr.data[0]
            num_controle = item.get('numero_controle') or item.get('id') or 'N/A'
            cpf_tec = item.get('cpf_tecnico', '')
            
            nome_tecnico = "Não informado"
            if cpf_tec:
                try:
                    res_tec = supabase.table("tecnicos").select("nome").eq("cpf", cpf_tec).execute()
                    if res_tec.data and len(res_tec.data) > 0:
                        nome_tecnico = res_tec.data[0].get("nome", cpf_tec)
                    else:
                        nome_tecnico = cpf_tec
                except Exception:
                    nome_tecnico = cpf_tec
            
            story.append(Paragraph("<b>LRVIX - SISTEMA DE GESTÃO TÉCNICA</b>", estilo_titulo))
            story.append(Paragraph(f"<b>ANÁLISE PRELIMINAR DE RISCO (APR) - Nº {num_controle}</b>", estilo_titulo))
            story.append(Spacer(1, 10))
            
            dados_gerais = [
                [Paragraph("<b>DADOS DA ATIVIDADE</b>", estilo_secao), ""],
                [Paragraph(f"<b>Data da Atividade:</b> {item.get('data_atividade', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Placa do Veículo:</b> {item.get('placa_veiculo', 'N/A')}", estilo_texto)],
                [Paragraph(f"<b>Local da Atividade:</b> {item.get('local_atividade', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Técnico Responsável:</b> {nome_tecnico}", estilo_texto)]
            ]
            
            tabela_geral = Table(dados_gerais, colWidths=[270, 270])
            tabela_geral.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_geral)
            story.append(Spacer(1, 15))
            
            dados_checklist = [
                [Paragraph("<b>CHECKLIST DE SEGURANÇA E CONDIÇÕES</b>", estilo_secao), ""],
                [Paragraph("<b>Item de Verificação</b>", estilo_texto_bold), Paragraph("<b>Status / Resposta</b>", estilo_texto_bold)],
                [Paragraph("Cinto de Segurança", estilo_texto), Paragraph(traduzir_bool(item.get('uso_cinto', 'N/A')), estilo_texto)],
                [Paragraph("Capacete Classe B", estilo_texto), Paragraph(traduzir_bool(item.get('uso_capacete', 'N/A')), estilo_texto)],
                [Paragraph("Amarração da Escada", estilo_texto), Paragraph(traduzir_bool(item.get('amarracao_escada', 'N/A')), estilo_texto)],
                [Paragraph("Sinalização da Área", estilo_texto), Paragraph(traduzir_bool(item.get('area_sinalizada', 'N/A')), estilo_texto)],
                [Paragraph("Verificação Geral", estilo_texto), Paragraph(traduzir_bool(item.get('verificacao_geral', 'N/A')), estilo_texto)],
                [Paragraph("Chuva", estilo_texto), Paragraph(traduzir_bool(item.get('chuva', 'N/A')), estilo_texto)],
                [Paragraph("Animais Peçonhentos", estilo_texto), Paragraph(traduzir_bool(item.get('animais_peconhetos', 'N/A')), estilo_texto)],
                [Paragraph("Poste Energizado", estilo_texto), Paragraph(traduzir_bool(item.get('poste_energizado', 'N/A')), estilo_texto)],
                [Paragraph("Integridade do Poste", estilo_texto), Paragraph(traduzir_bool(item.get('integridade_poste', 'N/A')), estilo_texto)],
            ]
            
            tabela_check = Table(dados_checklist, colWidths=[350, 190])
            tabela_check.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#f9fafb')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_check)
            story.append(Spacer(1, 15))
            
            dados_paralisacao = [
                [Paragraph("<b>STATUS DE INTERRUPÇÃO / PARALISAÇÃO</b>", estilo_secao), ""],
                [Paragraph(f"<b>Houve Interrupção das Atividades:</b> {traduzir_bool(item.get('houve_paralisacao', 'N/A'))}", estilo_texto), ""],
                [Paragraph(f"<b>Motivo da Paralisação:</b><br/>{item.get('motivo_paralisacao') or 'Nenhum motivo informado.'}", estilo_texto), ""]
            ]
            
            tabela_paralisa = Table(dados_paralisacao, colWidths=[540, 0])
            tabela_paralisa.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('SPAN', (0, 1), (1, 1)),
                ('SPAN', (0, 2), (1, 2)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_paralisa)
            
            caminhos_fotos = item.get('foto_paralisacao')
            
            if caminhos_fotos and isinstance(caminhos_fotos, list) and len(caminhos_fotos) > 0:
                story.append(Spacer(1, 15))
                dados_foto_cabecalho = [[Paragraph("<b>REGISTRO FOTOGRÁFICO DA OCORRÊNCIA</b>", estilo_secao)]]
                tabela_foto_cab = Table(dados_foto_cabecalho, colWidths=[540])
                tabela_foto_cab.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#2563eb')),
                    ('BOTTOMPADDING', (0, 0), (0, 0), 6),
                    ('TOPPADDING', (0, 0), (0, 0), 6),
                    ('LEFTPADDING', (0, 0), (0, 0), 8),
                    ('GRID', (0, 0), (0, 0), 0.5, colors.HexColor('#e5e7eb')),
                ]))
                story.append(tabela_foto_cab)
                story.append(Spacer(1, 10))
                
                fotos_limitadas = caminhos_fotos[:5]
                nome_bucket = "fotos_atendimentos"
                
                for idx, caminho_foto_storage in enumerate(fotos_limitadas):
                    if caminho_foto_storage and caminho_foto_storage.strip() != "":
                        try:
                            res_bytes = supabase.storage.from_(nome_bucket).download(caminho_foto_storage)
                            
                            if res_bytes:
                                temp_img_path = os.path.join(pasta_destino, f"temp_{apr_id}_{idx}.jpg")
                                with open(temp_img_path, "wb") as f:
                                    f.write(res_bytes)
                                
                                img = Image(temp_img_path, width=280, height=210)
                                img.hAlign = 'CENTER'
                                story.append(img)
                                story.append(Spacer(1, 10))
                        except Exception as img_err:
                            story.append(Paragraph(f"Não foi possível carregar a imagem {idx+1}: {str(img_err)}", estilo_texto))
            
        else:
            story.append(Paragraph("Detalhes da APR não encontrados no banco.", estilo_texto))
            
        doc.build(story)
        return nome_arquivo
        
    except Exception as e:
        pasta_destino = "aprs_geradas"
        os.makedirs(pasta_destino, exist_ok=True)
        nome_arquivo = os.path.join(pasta_destino, "erro_apr.pdf")
        c = canvas.Canvas(nome_arquivo, pagesize=letter)
        c.drawString(50, 750, f"Erro ao gerar PDF: {str(e)}")
        c.save()
        return nome_arquivo
    
if not st.session_state.logado:
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        st.markdown("<h2 style='text-align: center;'>⚡ LRVIX Acesso</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Sistema de Gestão Técnica</p>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Login", "Cadastrar Técnico"])
        with tab1:
            cpf_input = st.text_input("CPF")
            senha_input = st.text_input("Senha", type="password", key="login_senha")
            st.write("")
            if st.button("Entrar", use_container_width=True):
                try:
                    user_query = supabase.table("TECNICOS").select("*").eq("cpf", str(cpf_input).strip()).execute()
                    
                    if user_query.data:
                        dados_user = user_query.data[0]
                        senha_banco = str(dados_user.get("senha", "")).strip()
                        senha_digitada = str(senha_input).strip()
                        
                        if senha_banco == senha_digitada:
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
                    else:
                        st.error("❌ CPF ou Senha incorretos.")
                except Exception as e:
                    st.error(f"Erro na conexão com o banco: {e}")
with aba2: 
        st.subheader("Lista de Atendimentos")
        
        query = supabase.table("ATENDIMENTO").select("*")
        
        if st.session_state.perfil != "Administrador":
            query = query.eq("cpf_tecnico", st.session_state.cpf_tecnico)
        
        atendimentos = query.execute()
            
        if atendimentos.data:
            df = pd.DataFrame(atendimentos.data)
            
            if 'data_execucao' in df.columns:
                df['data_execucao'] = pd.to_datetime(df['data_execucao'], errors='coerce').dt.strftime('%d/%m/%Y')
            
            # --- DEFINIÇÃO DAS COLUNAS OCULTAS POR PERFIL ---
            colunas_para_ocultar = ['id', 'created_at', 'cpf_tecnico']
            
            # Se não for Administrador (perfil Técnico), oculta foto, responsavel e valor_total
            if st.session_state.perfil != "Administrador":
                colunas_para_ocultar.extend(['foto', 'responsavel', 'valor_total'])
            
            df_exibicao = df[[col for col in df.columns if col not in colunas_para_ocultar]]
            st.dataframe(df_exibicao, use_container_width=True)
            
            # --- TABELA DE PROJEÇÃO E INDICADORES ---
            st.write("")
            st.markdown("### 📊 Indicadores e Projeção")
            
            try:
                # Tratamento de dados para os cálculos
                df_calc = pd.DataFrame(atendimentos.data)
                
                # Dias trabalhados (datas distintas)
                dias_trabalhados = df_calc['data_execucao'].nunique() if 'data_execucao' in df_calc.columns else 0
                
                # Padronizar coluna tipo_servico para maiúsculo para contagem correta
                df_calc['tipo_servico_upper'] = df_calc['tipo_servico'].astype(str).str.strip().str.upper()
                
                # Contagem de serviços
                qtd_interno = len(df_calc[df_calc['tipo_servico_upper'] == 'INTERNO'])
                qtd_externo = len(df_calc[df_calc['tipo_servico_upper'] == 'EXTERNO'])
                qtd_improdutivo = len(df_calc[df_calc['tipo_servico_upper'] == 'IMPRODUTIVO'])
                
                # Total de serviços produtivos (Interno + Externo)
                total_servicos_produtivos = qtd_interno + qtd_externo
                
                # Média de serviço (desconsiderando improdutivos: total produtivo / dias trabalhados)
                media_servico = (total_servicos_produtivos / dias_trabalhados) if dias_trabalhados > 0 else 0.0
                
                # Ticket médio e Soma Geral (desconsiderando improdutivos para o ticket médio)
                df_calc['valor_total'] = pd.to_numeric(df_calc['valor_total'], errors='coerce').fillna(0.0)
                
                # Filtra apenas os produtivos para o ticket médio
                df_produtivos = df_calc[df_calc['tipo_servico_upper'].isin(['INTERNO', 'EXTERNO'])]
                soma_valor_produtivos = df_produtivos['valor_total'].sum()
                
                ticket_medio = (soma_valor_produtivos / total_servicos_produtivos) if total_servicos_produtivos > 0 else 0.0
                total_geral = df_calc['valor_total'].sum()
                
                # Montagem visual da tabela em HTML semelhante ao layout solicitado
                tabela_html = f"""
                <div style="overflow-x:auto;">
                    <table style="width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif; font-size: 14px;">
                        <thead>
                            <tr style="background-color: #4a90e2; color: white;">
                                <th style="border: 1px solid #ddd; padding: 10px;" colspan="5">PROJEÇÃO E INDICADORES</th>
                            </tr>
                            <tr style="background-color: #5ba4e6; color: white;">
                                <th style="border: 1px solid #ddd; padding: 8px;">DIAS TRABALHADOS</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">SERV. INTERNO / EXTERNO</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">MED. SERVIÇO</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">TICKET MÉDIO</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">T. GERAL</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background-color: #f9f9f9; color: #333; font-weight: bold;">
                                <td style="border: 1px solid #ddd; padding: 10px;">{dias_trabalhados}</td>
                                <td style="border: 1px solid #ddd; padding: 10px;">{qtd_interno} Int / {qtd_externo} Ext (Tot: {total_servicos_produtivos})</td>
                                <td style="border: 1px solid #ddd; padding: 10px;">{media_servico:.2f}</td>
                                <td style="border: 1px solid #ddd; padding: 10px;">R$ {ticket_medio:,.2f}</td>
                                <td style="border: 1px solid #ddd; padding: 10px;">R$ {total_geral:,.2f}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                """
                st.markdown(tabela_html, unsafe_allow_html=True)
                
            except Exception as calc_err:
                st.error(f"Erro ao calcular os indicadores: {calc_err}")
            
            if st.session_state.get("perfil") == "Administrador":
                st.divider()
                st.subheader("🖼️ Visualizador de Fotos")
                
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
                    "Selecione um atendimento para visualizar as fotos:", 
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
            
            
    with aba3:
        st.subheader("⚠️ ANÁLISE PRELIMINAR DE RISCO (APR)")
        
        if st.session_state.get("sucesso_apr"):
            st.success(st.session_state.sucesso_apr)
            st.balloons()
            del st.session_state["sucesso_apr"]

        with st.expander("📂 APRs Cadastradas", expanded=False):
            try:
                query_aprs = supabase.table("APR").select("id, numero_controle, cpf_tecnico").order("id", desc=True)
                
                if st.session_state.get("perfil") != "Administrador":
                    cpf_logado = str(st.session_state.get("cpf_tecnico", "")).strip()
                    cpf_limpo = cpf_logado.replace(".", "").replace("-", "")
                    
                    resposta_todas = query_aprs.execute()
                    
                    if resposta_todas.data:
                        lista_filtrada = []
                        for item in resposta_todas.data:
                            cpf_banco = str(item.get("cpf_tecnico", "")).strip()
                            cpf_banco_limpo = cpf_banco.replace(".", "").replace("-", "")
                            
                            if cpf_banco_limpo == cpf_limpo and cpf_limpo != "":
                                lista_filtrada.append(item)
                        lista_aprs_data = lista_filtrada
                    else:
                        lista_aprs_data = []
                else:
                    resposta_todas = query_aprs.execute()
                    lista_aprs_data = resposta_todas.data
                
                if lista_aprs_data:
                    cols = st.columns(4)
                    for i, item in enumerate(lista_aprs_data):
                        with cols[i % 4]:
                            num_exibicao = item.get('numero_controle') or str(item['id'])
                            if st.button(f"📄 APR {num_exibicao}", key=f"btn_apr_{item['id']}"):
                                arquivo = gerar_pdf_apr(item['id'])
                                with open(arquivo, "rb") as f:
                                    st.download_button(
                                        label="📥 BAIXAR PDF",
                                        data=f,
                                        file_name=arquivo,
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                else:
                    st.info("Nenhuma APR cadastrada para o seu usuário.")
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
            
            fotos_paralisacao = st.file_uploader("📸 Fotos da ocorrência (Até 5)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
            motivo_paralisacao = st.text_area("MOTIVO DA PARALISAÇÃO")
            
            st.write("")
            botao_enviar = st.form_submit_button("REGISTRAR APR", use_container_width=True)
            
            if botao_enviar:
                caminhos_fotos_salvas = []
                if fotos_paralisacao:
                    for foto in fotos_paralisacao[:5]:
                        try:
                            timestamp = int(time.time())
                            caminho = f"fotos/{timestamp}_{foto.name}"
                            supabase.storage.from_("fotos_atendimentos").upload(caminho, foto.getvalue())
                            caminhos_fotos_salvas.append(caminho)
                        except Exception as e:
                            st.error(f"Erro ao subir foto {foto.name}: {e}")
                
                try:
                    cpf_logado = st.session_state.get("cpf_tecnico", "")
                    perfil_usuario = st.session_state.get("perfil", "Técnico")
                    numero_gerado = str(int(time.time()))[-6:] 

                    resposta = supabase.table("APR").insert({
                        "numero_controle": numero_gerado,
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
                        "foto_paralisacao": caminhos_fotos_salvas,
                        "cpf_tecnico": cpf_logado,
                        "perfil": perfil_usuario
                    }).execute()
                    
                    st.session_state["sucesso_apr"] = f"APR {numero_gerado} registrada com sucesso!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar APR no banco: {e}")

    if aba4 is not None: 
        with aba4:
            st.subheader("⚙️ PAINEL ADMINISTRATIVO")
            
            opcao_admin = st.radio("O que deseja gerenciar?", ["Perfis de Usuários", "💰 Tabela LPU"], horizontal=True)
            senha_admin = st.text_input("DIGITE A SENHA MESTRA:", type="password", key="admin_senha")

            if senha_admin == "123456":
                if opcao_admin == "Perfis de Usuários":
                    st.write("### 👤 Gerenciamento de Perfis")
                    try:
                        dados_tecnicos = supabase.table("TECNICOS").select("*").execute()
                        df_tecnicos = pd.DataFrame(dados_tecnicos.data)
                        edited_df = st.data_editor(df_tecnicos, use_container_width=True)

                        if st.button("SALVAR PERFIS", use_container_width=True):
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
                            df_lpu = pd.DataFrame(columns=["id", "created_at", "servico", "valor", "descricao", "min_metragem", "max_metragem"])
                        else:
                            df_lpu = pd.DataFrame(dados_lpu.data)
                        
                        configuracao_colunas = {
                            "id": None,
                            "created_at": None,
                            "servico": st.column_config.TextColumn("Serviço", required=True),
                            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0),
                            "descricao": st.column_config.TextColumn("Descrição"),
                            "min_metragem": st.column_config.NumberColumn("Mín Metragem", min_value=0.0),
                            "max_metragem": st.column_config.NumberColumn("Máx Metragem", min_value=0.0)
                        }
                        
                        df_editada_lpu = st.data_editor(
                            df_lpu, 
                            use_container_width=True, 
                            num_rows="dynamic",
                            column_config=configuracao_colunas,
                            disabled=["id", "created_at"]
                        )

                        if st.button("SALVAR LPU", use_container_width=True):
                            with st.spinner("Salvando..."):
                                for index, row in df_editada_lpu.iterrows():
                                    servico_val = row.get("servico")
                                    valor_val = row.get("valor")
                                    
                                    if not servico_val or pd.isna(servico_val):
                                        continue
                                        
                                    id_val = row.get("id")
                                    descricao_val = row.get("descricao")
                                    min_m_val = row.get("min_metragem")
                                    max_m_val = row.get("max_metragem")
                                    
                                    dados_para_salvar = {
                                        "servico": str(servico_val),
                                        "valor": float(valor_val) if pd.notnull(valor_val) else 0.0,
                                        "descricao": str(descricao_val) if pd.notnull(descricao_val) and descricao_val is not None else None,
                                        "min_metragem": float(min_m_val) if pd.notnull(min_m_val) and min_m_val is not None else None,
                                        "max_metragem": float(max_m_val) if pd.notnull(max_m_val) and max_m_val is not None else None
                                    }
                                    
                                    if id_val is not None and pd.notnull(id_val) and str(id_val).strip() != "":
                                        supabase.table("LPU").update(dados_para_salvar).eq("id", id_val).execute()
                                    else:
                                        supabase.table("LPU").insert(dados_para_salvar).execute()
                                        
                                st.success("Tabela LPU atualizada com sucesso!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao acessar tabela LPU: {e}")
