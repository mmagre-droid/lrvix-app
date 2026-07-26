import streamlit as st
import pandas as pd
import time
import re
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

# --- CONFIGURAÇÃO DE PWA PARA TRANSFORMAR EM APLICATIVO ---
st.markdown("""
    <link rel="manifest" href="manifest.json">
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', function() {
                navigator.serviceWorker.register('sw.js').then(function(registration) {
                    console.log('ServiceWorker registrado com sucesso: ', registration.scope);
                }, function(err) {
                    console.log('Falha ao registrar o ServiceWorker: ', err);
                });
            });
        }
    </script>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO E RECUPERAÇÃO DA SESSÃO VIA URL (CORREÇÃO DO F5) ---
if "logado" not in st.session_state:
    query_params = st.query_params
    if "logado" in query_params and query_params["logado"] == "True":
        st.session_state.logado = True
        st.session_state.nome_tecnico = query_params.get("nome", "")
        st.session_state.perfil = query_params.get("perfil", "")
        st.session_state.cpf_tecnico = query_params.get("cpf", "")
        st.session_state.precisa_trocar_senha = False
    else:
        st.session_state.logado = False
        st.session_state.modo_admin = False
        st.session_state.nome_tecnico = ""
        st.session_state.perfil = ""
        st.session_state.cpf_tecnico = ""
        st.session_state.precisa_trocar_senha = False

if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False
if "nome_tecnico" not in st.session_state:
    st.session_state.nome_tecnico = ""
if "perfil" not in st.session_state:
    st.session_state.perfil = ""
if "cpf_tecnico" not in st.session_state:
    st.session_state.cpf_tecnico = ""
if "precisa_trocar_senha" not in st.session_state:
    st.session_state.precisa_trocar_senha = False

# --- ESTILIZAÇÃO CSS (OCULTA CABEÇALHO, MENU, ÍCONES FLUTUANTES E GITHUB) ---
st.markdown("""
    <style>

    /* ⬇️ BLOQUEIA O PULL-TO-REFRESH NO CELULAR ⬇️ */
        body, html {
            overscroll-behavior-y: none;
        }
        
        /* Oculta completamente o cabeçalho e rodapé padrão do Streamlit */
        header {visibility: hidden !important; display: none !important;}
        #MainMenu {visibility: hidden !important; display: none !important;}
        footer {visibility: hidden !important; display: none !important;}
        
        /* Oculta seletores antigos e novos de widgets flutuantes e ferramentas */
        [data-testid="stStatusWidget"] {
            visibility: hidden !important;
            display: none !important;
        }
        div[data-testid="stToolbar"] {
            visibility: hidden !important;
            display: none !important;
        }
        div[class*="stToolbar"] {
            visibility: hidden !important;
            display: none !important;
        }
        div[class*="viewerBadge"] {
            visibility: hidden !important;
            display: none !important;
        }
        button[kind="header"] {
            visibility: hidden !important;
            display: none !important;
        }
        
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

def calcular_valor_lpu(tipo_servico, metragem_cabo, mercado, observacao, cpf_tecnico):
    try:
        tabela_lpu_alvo = "LPU"
        try:
            res_tec = supabase.table("TECNICOS").select("lpu_atribuida").eq("cpf", cpf_tecnico).execute()
            if res_tec.data:
                lpu_atribuida = res_tec.data[0].get("lpu_atribuida", "LPU Padrão")
                if lpu_atribuida == "DELIVERY":
                    tabela_lpu_alvo = "LPU DELIVERY"
        except Exception:
            pass

        res_lpu = supabase.table(tabela_lpu_alvo).select("*").execute()
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
            
        for item in res_lpu.data:
            min_m = item.get("min_metragem")
            max_m = item.get("max_metragem")
            
            if min_m is not None and max_m is not None:
                if float(min_m) <= metragem <= float(max_m):
                    return round(float(item.get("valor", 0.0)), 2)
        
        faixas_com_metragem = [item for item in res_lpu.data if item.get("min_metragem") is not None and item.get("max_metragem") is not None]
        if faixas_com_metragem and metragem > 0:
            maior_faixa = max(faixas_com_metragem, key=lambda x: float(x.get("max_metragem", 0)))
            teto_max = float(maior_faixa.get("max_metragem", 0))
            
            if metragem > teto_max:
                valor_base = float(maior_faixa.get("valor", 0.0))
                excedente = metragem - teto_max
                
                valor_adicional_bloco = 0.0
                for item in res_lpu.data:
                    serv_nome = str(item.get("servico", "")).strip().upper()
                    if "ADICIONAL" in serv_nome or "100" in serv_nome:
                        valor_adicional_bloco = float(item.get("valor", 0.0))
                        break
                
                if valor_adicional_bloco == 0.0 and teto_max > 0:
                    valor_adicional_bloco = valor_base * (100.0 / teto_max)
                
                blocos_extras = (excedente // 100.0) + (1 if excedente % 100.0 > 0 else 0)
                return round(valor_base + (blocos_extras * valor_adicional_bloco), 2)
                    
        for item in res_lpu.data:
            nome_servico = str(item.get("servico", "")).strip().lower()
            if nome_servico == servico_lower:
                return round(float(item.get("valor", 0.0)), 2)
                
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
                    res_tec = supabase.table("TECNICOS").select("nome").eq("cpf", cpf_tec).execute()
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
    
# --- TELA DE LOGIN OU TROCA OBRIGATÓRIA DE SENHA ---
if not st.session_state.logado:
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        st.markdown("<h2 style='text-align: center;'>⚡ LRVIX Acesso</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Sistema de Gestão Técnica</p>", unsafe_allow_html=True)
        
        if st.session_state.get("precisa_trocar_senha"):
            st.warning("⚠️ **Primeiro Acesso Detectado!** Por segurança, você deve alterar sua senha padrão antes de continuar.")
            
            with st.form("form_nova_senha"):
                nova_senha_input = st.text_input("Nova Senha", type="password")
                confirma_senha_input = st.text_input("Confirme a Nova Senha", type="password")
                
                st.caption("Requisitos da senha: mínimo de 8 caracteres, contendo letras maiúsculas, minúsculas e números.")
                
                if st.form_submit_button("Atualizar Senha", use_container_width=True):
                    if nova_senha_input != confirma_senha_input:
                        st.error("❌ As senhas não coincidem.")
                    elif len(nova_senha_input) < 8:
                        st.error("❌ A senha deve ter pelo menos 8 caracteres.")
                    elif not re.search(r"[A-Z]", nova_senha_input):
                        st.error("❌ A senha deve conter pelo menos uma letra maiúscula.")
                    elif not re.search(r"[a-z]", nova_senha_input):
                        st.error("❌ A senha deve conter pelo menos uma letra minúscula.")
                    elif not re.search(r"\d", nova_senha_input):
                        st.error("❌ A senha deve conter pelo menos um número.")
                    else:
                        try:
                            supabase.table("TECNICOS").update({
                                "senha": nova_senha_input,
                                "primeiro_acesso": False
                            }).eq("cpf", st.session_state.cpf_tecnico).execute()
                            
                            st.session_state.precisa_trocar_senha = False
                            st.session_state.logado = True
                            
                            st.query_params["logado"] = "True"
                            st.query_params["nome"] = st.session_state.nome_tecnico
                            st.query_params["perfil"] = st.session_state.perfil
                            st.query_params["cpf"] = st.session_state.cpf_tecnico
                            
                            st.success("Senha alterada com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar senha: {e}")
        else:
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
                        
                        eh_primeiro_acesso = dados_user.get("primeiro_acesso", True) or senha_banco == "123456"
                        
                        if senha_banco == senha_digitada:
                            if dados_user.get("ativo") is True:
                                st.session_state.nome_tecnico = dados_user["nome"]
                                st.session_state.perfil = dados_user["perfil"]
                                st.session_state.cpf_tecnico = dados_user["cpf"]
                                
                                if eh_primeiro_acesso and senha_digitada == "123456":
                                    st.session_state.precisa_trocar_senha = True
                                    st.rerun()
                                else:
                                    st.session_state.logado = True
                                    st.session_state.precisa_trocar_senha = False
                                    
                                    st.query_params["logado"] = "True"
                                    st.query_params["nome"] = dados_user["nome"]
                                    st.query_params["perfil"] = dados_user["perfil"]
                                    st.query_params["cpf"] = dados_user["cpf"]
                                    
                                    st.rerun()
                            else:
                                st.error("⚠️ Este usuário está inativo.")
                        else:
                            st.error("❌ CPF ou Senha incorretos.")
                    else:
                        st.error("❌ CPF ou Senha incorretos.")
                except Exception as e:
                    st.error(f"Erro na conexão com o banco: {e}")

else:
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(f"### ⚡ Olá, **{st.session_state.nome_tecnico}**")
        st.caption(f"Perfil de Acesso: **{st.session_state.perfil}**")
    with col_h2:
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.logado = False
            st.session_state.precisa_trocar_senha = False
            st.query_params.clear()
            st.rerun()

    st.markdown("---")
    
    if st.session_state.perfil == "Administrador":
        aba1, aba2, aba3, aba4, aba5 = st.tabs(["📝 FORMULÁRIO", "📊 PRODUTIVIDADE", "⚠️ APR", "📦 ESTOQUE", "⚙️ ADMIN"])
    else:
        aba1, aba2, aba3, aba4 = st.tabs(["📝 FORMULÁRIO", "📊 PRODUTIVIDADE", "⚠️ APR", "📦 ESTOQUE"])
        aba5 = None

    Python
# --- Na aba 1 (Formulário), coloque o checkbox e as opções de troca FORA do formulário principal para que o Streamlit recarregue a tela ao marcar e exiba os campos ---

    with aba1:
        st.subheader("Novo Lançamento Operacional")
        
        tabela_lpu_alvo = "LPU"
        lista_opcoes_servicos = ["INTERNO", "EXTERNO", "IMPRODUTIVO"]
        
        try:
            res_tec = supabase.table("TECNICOS").select("lpu_atribuida").eq("cpf", st.session_state.cpf_tecnico).execute()
            if res_tec.data:
                lpu_atribuida = res_tec.data[0].get("lpu_atribuida", "LPU Padrão")
                
                if lpu_atribuida == "DELIVERY":
                    tabela_lpu_alvo = "LPU DELIVERY"
                    res_servicos = supabase.table("LPU DELIVERY").select("servico").execute()
                    if res_servicos.data:
                        servicos_delivery = [str(item.get("servico")).strip() for item in res_servicos.data if item.get("servico")]
                        if servicos_delivery:
                            lista_opcoes_servicos = servicos_delivery
        except Exception as e:
            print(f"Erro ao carregar serviços da LPU: {e}")

        # --- BUSCAR LISTA DE EQUIPAMENTOS CADASTRADOS ---
        opcoes_equipamentos_cadastrados = ["Selecione..."]
        try:
            res_cad = supabase.table("CADASTRO_EQUIPAMENTOS").select("codigo, descricao").execute()
            if res_cad.data:
                opcoes_equipamentos_cadastrados += [f"{item['codigo']} - {item['descricao']}" for item in res_cad.data]
        except Exception:
            pass

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
                tipo_servico = st.selectbox("TIPO DE SERVIÇO", lista_opcoes_servicos)
            
            observacao = st.text_area("OBSERVAÇÃO")
            fotos_arquivos = st.file_uploader("FOTOS DO SERVIÇO (Até 5)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
            
            botao_enviar = st.form_submit_button("REGISTRAR ATENDIMENTO", use_container_width=True)

        # --- CHECKBOX E OPÇÕES DE TROCA FORA DO FORMULÁRIO (Para atualizar a tela instantaneamente ao clicar) ---
        st.divider()
        habilita_troca = st.checkbox("🔄 Realizar Troca de Equipamento neste Atendimento", value=st.session_state.get("habilita_troca_state", False), key="habilita_troca_state")
        
        equipamento_velho = "Selecione..."
        equipamento_novo = "Selecione..."
        status_velho = "DEFEITO"
        
        if habilita_troca:
            st.info("O equipamento **novo** sai do estoque para o cliente, e o equipamento **velho** (defeituoso/retirado) entra no estoque.")
            tc_e1, tc_e2 = st.columns(2)
            with tc_e1:
                equipamento_velho = st.selectbox("Nome do Equipamento Velho / Retirado", opcoes_equipamentos_cadastrados, key="form_eq_velho")
            with tc_e2:
                equipamento_novo = st.selectbox("Nome do Equipamento Novo", opcoes_equipamentos_cadastrados, key="form_eq_novo")
            
            status_velho = st.selectbox("Condição do Equipamento Velho", ["DEFEITO", "FUNCIONAL", "ANALISE"], key="form_status_velho")

        # --- PROCESSAMENTO DO ENVIO ---
        if botao_enviar:
            if not cliente or not endereco or not protocolo or not metragem_cabo:
                st.error("⚠️ Por favor, preencha todos os campos obrigatórios (Cliente, Endereço, Protocolo e Cabo Utilizado).")
            elif habilita_troca and (equipamento_novo == "Selecione..." or equipamento_velho == "Selecione..."):
                st.error("⚠️ Selecione os equipamentos corretos para a troca.")
            else:
                valor_calculado = calcular_valor_lpu(tipo_servico, metragem_cabo, mercado, observacao, st.session_state.cpf_tecnico)
                
                caminhos_fotos_atendimento = []
                if fotos_arquivos:
                    for foto in fotos_arquivos[:5]:
                        try:
                            timestamp = int(time.time())
                            caminho = f"fotos/{timestamp}_{foto.name}"
                            supabase.storage.from_("fotos_atendimentos").upload(caminho, foto.getvalue())
                            caminhos_fotos_atendimento.append(caminho)
                        except Exception as e:
                            st.error(f"Erro ao subir foto {foto.name}: {e}")
                
                # Se habilitou a troca, executa as movimentações no estoque automaticamente
                if habilita_troca:
                    try:
                        supabase.table("ESTOQUE").insert({
                            "equipamento": equipamento_novo,
                            "serial": "N/A",
                            "status": f"INSTALADO - {cliente}",
                            "localizacao": f"CLIENTE: {cliente}",
                            "observacao": f"Saída por troca no atendimento (Prot: {protocolo})."
                        }).execute()
                        
                        supabase.table("ESTOQUE").insert({
                            "equipamento": equipamento_velho,
                            "serial": "N/A",
                            "status": status_velho,
                            "localizacao": "ESTOQUE CENTRAL",
                            "observacao": f"Retirado do cliente {cliente} (Prot: {protocolo})."
                        }).execute()
                        
                        supabase.table("HISTORICO_ESTOQUE").insert({
                            "tipo_movimentacao": "TROCA",
                            "equipamento": f"Novo: {equipamento_novo} | Velho: {equipamento_velho}",
                            "serial": "N/A",
                            "responsavel": st.session_state.nome_tecnico,
                            "detalhes": f"Atendimento/Cliente: {cliente} | Protocolo: {protocolo}"
                        }).execute()
                    except Exception as est_err:
                        st.error(f"Erro ao movimentar o estoque na troca: {est_err}")
                
                if registrar_atendimento(
                    data_execucao, 
                    cliente, 
                    endereco, 
                    protocolo, 
                    mercado, 
                    tipo_servico, 
                    observacao, 
                    caminhos_fotos_atendimento, 
                    st.session_state.nome_tecnico, 
                    st.session_state.cpf_tecnico, 
                    metragem_cabo,
                    valor_calculado
                ):
                    st.success("Atendimento e movimentações registrados com sucesso!")
            
    with aba2: 
        st.subheader("Lista de Atendimentos")
        
        if st.session_state.perfil == "Administrador":
            try:
                res_tecnicos = supabase.table("TECNICOS").select("nome, cpf").eq("ativo", True).execute()
                lista_tecnicos = res_tecnicos.data if res_tecnicos.data else []
                
                opcoes_tec = {"Todos os Técnicos": "TODOS"}
                for t in lista_tecnicos:
                    opcoes_tec[t["nome"]] = t["cpf"]
                
                col_f1, col_f2 = st.columns([2, 2])
                with col_f1:
                    tecnico_selecionado = st.selectbox("Filtrar por Técnico:", list(opcoes_tec.keys()))
                
                query = supabase.table("ATENDIMENTO").select("*")
                
                if tecnico_selecionado != "Todos os Técnicos":
                    cpf_filtro = opcoes_tec[tecnico_selecionado]
                    query = query.eq("cpf_tecnico", cpf_filtro)
                    
            except Exception as e:
                st.error(f"Erro ao carregar lista de técnicos para o filtro: {e}")
                query = supabase.table("ATENDIMENTO").select("*")
        else:
            query = supabase.table("ATENDIMENTO").select("*").eq("cpf_tecnico", st.session_state.cpf_tecnico)
        
        atendimentos = query.execute()
            
        if atendimentos.data:
            df = pd.DataFrame(atendimentos.data)
            
            if 'data_execucao' in df.columns:
                df['data_execucao'] = pd.to_datetime(df['data_execucao'], errors='coerce').dt.strftime('%d/%m/%Y')
            
            colunas_para_ocultar = ['id', 'created_at', 'cpf_tecnico']
            
            if st.session_state.perfil != "Administrador":
                colunas_para_ocultar.extend(['foto', 'responsavel', 'valor_total'])
            
            df_exibicao = df[[col for col in df.columns if col not in colunas_para_ocultar]]
            
            if 'valor_total' in df_exibicao.columns:
                df_exibicao['valor_total'] = pd.to_numeric(df_exibicao['valor_total'], errors='coerce').map(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "")

            st.dataframe(df_exibicao, use_container_width=True)
            
            st.write("")
            st.markdown("### 📊 Indicadores e Projeção")
            
            try:
                df_calc = pd.DataFrame(atendimentos.data)
                dias_trabalhados = df_calc['data_execucao'].nunique() if 'data_execucao' in df_calc.columns else 0
                df_calc['tipo_servico_upper'] = df_calc['tipo_servico'].astype(str).str.strip().str.upper()
                
                qtd_interno = len(df_calc[df_calc['tipo_servico_upper'] == 'INTERNO'])
                qtd_externo = len(df_calc[df_calc['tipo_servico_upper'] == 'EXTERNO'])
                qtd_improdutivo = len(df_calc[df_calc['tipo_servico_upper'] == 'IMPRODUTIVO'])
                
                total_servicos_produtivos = qtd_interno + qtd_externo
                media_servico = (total_servicos_produtivos / dias_trabalhados) if dias_trabalhados > 0 else 0.0
                
                df_calc['valor_total'] = pd.to_numeric(df_calc['valor_total'], errors='coerce').fillna(0.0)
                df_produtivos = df_calc[df_calc['tipo_servico_upper'].isin(['INTERNO', 'EXTERNO'])]
                soma_valor_produtivos = df_produtivos['valor_total'].sum()
                
                ticket_medio = (soma_valor_produtivos / total_servicos_produtivos) if total_servicos_produtivos > 0 else 0.0
                total_geral = df_calc['valor_total'].sum()
                
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
                                        st.image(res_bytes, caption=f"Anexo {idx+1}", use_container_width=True)
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

    with aba4:
        st.subheader("📦 GESTÃO DE ESTOQUE E MOVIMENTAÇÕES")
        
        # --- BUSCAR LISTA DE EQUIPAMENTOS CADASTRADOS ---
        opcoes_equipamentos_cadastrados = ["Selecione..."]
        try:
            res_cad = supabase.table("CADASTRO_EQUIPAMENTOS").select("codigo, descricao").execute()
            if res_cad.data:
                opcoes_equipamentos_cadastrados += [f"{item['codigo']} - {item['descricao']}" for item in res_cad.data]
        except Exception:
            pass

        sub_aba1, sub_aba2, sub_aba3 = st.tabs(["➕ Entrada de Mercadoria", "🔄 Troca de Equipamento", "📋 Saldo e Histórico"])
        
        with sub_aba1:
            st.markdown("### Registrar Entrada de Novos Itens / Equipamentos")
            with st.form("form_entrada_estoque", clear_on_submit=True):
                ec1, ec2 = st.columns(2)
                with ec1:
                    item_selecionado = st.selectbox("Nome do Equipamento / Material", opcoes_equipamentos_cadastrados)
                    quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
                with ec2:
                    origem_nota = st.text_input("Nota Fiscal / Fornecedor / Origem")
                
                obs_entrada = st.text_area("Observações da Entrada")
                
                if st.form_submit_button("REGISTRAR ENTRADA", use_container_width=True):
                    if item_selecionado == "Selecione..." or not quantidade or quantidade < 1:
                        st.error("⚠️ Selecione o equipamento e informe uma quantidade válida.")
                    else:
                        try:
                            supabase.table("ESTOQUE").insert({
                                "equipamento": item_selecionado,
                                "serial": "N/A",
                                "status": "DISPONIVEL",
                                "localizacao": "ESTOQUE CENTRAL",
                                "observacao": obs_entrada
                            }).execute()
                            
                            supabase.table("HISTORICO_ESTOQUE").insert({
                                "tipo_movimentacao": "ENTRADA",
                                "equipamento": item_selecionado,
                                "serial": "N/A",
                                "responsavel": st.session_state.nome_tecnico,
                                "detalhes": f"Entrada de {quantidade} un. Origem: {obs_entrada or 'N/A'}"
                            }).execute()
                            
                            st.success("Entrada registrada com sucesso no estoque!")
                        except Exception as e:
                            st.error(f"Erro ao registrar entrada: {e}")
        with sub_aba2:
            st.markdown("### Registrar Troca de Equipamento (Cliente)")
            st.info("O equipamento **novo** sai do estoque para o cliente, e o equipamento **velho** (defeituoso/retirado) entra no estoque.")
            
            with st.form("form_troca_equipamento", clear_on_submit=True):
                tc1, tc2 = st.columns(2)
                with tc1:
                    cliente_troca = st.text_input("Nome do Cliente / Protocolo")
                    equipamento_novo = st.selectbox("Nome do Equipamento Novo", opcoes_equipamentos_cadastrados, key="eq_novo")
                with tc2:
                    equipamento_velho = st.selectbox("Nome do Equipamento Velho / Retirado", opcoes_equipamentos_cadastrados, key="eq_velho")
                    status_velho = st.selectbox("Condição do Equipamento Velho", ["DEFEITO", "FUNCIONAL", "ANALISE"])
                
                motivo_troca = st.text_area("Motivo da Troca (ex: Queimado por raio, lentidão)")
                
                if st.form_submit_button("CONFIRMAR TROCA DE EQUIPAMENTOS", use_container_width=True):
                    if not cliente_troca or equipamento_novo == "Selecione..." or equipamento_velho == "Selecione...":
                        st.error("⚠️ Preencha os campos obrigatórios e selecione os equipamentos corretamente.")
                    else:
                        try:
                            supabase.table("ESTOQUE").insert({
                                "equipamento": equipamento_novo,
                                "serial": "N/A",
                                "status": f"INSTALADO - {cliente_troca}",
                                "localizacao": f"CLIENTE: {cliente_troca}",
                                "observacao": f"Saída por troca. Motivo: {motivo_troca}"
                            }).execute()
                            
                            supabase.table("ESTOQUE").insert({
                                "equipamento": equipamento_velho,
                                "serial": "N/A",
                                "status": status_velho,
                                "localizacao": "ESTOQUE CENTRAL",
                                "observacao": f"Retirado do cliente {cliente_troca}. Motivo: {motivo_troca}"
                            }).execute()
                            
                            supabase.table("HISTORICO_ESTOQUE").insert({
                                "tipo_movimentacao": "TROCA",
                                "equipamento": f"Novo: {equipamento_novo} | Velho: {equipamento_velho}",
                                "serial": "N/A",
                                "responsavel": st.session_state.nome_tecnico,
                                "detalhes": f"Cliente: {cliente_troca} | Motivo: {motivo_troca}"
                            }).execute()
                            
                            st.success("Troca registrada com sucesso! Equipamento novo baixado e velho adicionado ao estoque.")
                        except Exception as e:
                            st.error(f"Erro ao processar troca: {e}")
        with sub_aba3:
            st.markdown("### Saldo Atual do Estoque e Histórico")
            try:
                res_estoque = supabase.table("ESTOQUE").select("*").execute()
                if res_estoque.data:
                    st.write("#### 📊 Itens Cadastrados no Estoque")
                    df_est = pd.DataFrame(res_estoque.data)
                    
                    # Ocultar colunas indesejadas (id, created_at, etc.)
                    colunas_ocultar_est = ['id', 'created_at']
                    df_est_exibicao = df_est[[col for col in df_est.columns if col not in colunas_ocultar_est]]
                    
                    st.dataframe(df_est_exibicao, use_container_width=True)
                else:
                    st.info("Nenhum item registrado no estoque.")
                
                st.divider()
                res_hist = supabase.table("HISTORICO_ESTOQUE").select("*").order("created_at", desc=True).execute()
                if res_hist.data:
                    st.write("#### 📜 Histórico de Movimentações")
                    df_hist = pd.DataFrame(res_hist.data)
                    
                    # Tratativa para criar colunas separadas de Entrada e Saída no Histórico
                    if 'serial' in df_hist.columns:
                        df_hist['Entrada'] = df_hist['serial'].apply(lambda x: x.split('/')[1].strip() if isinstance(x, str) and '/' in x else ('1' if 'Entrada' in str(x) else '0'))
                        df_hist['Saída'] = df_hist['serial'].apply(lambda x: x.split('/')[0].strip() if isinstance(x, str) and '/' in x else '0')
                    else:
                        df_hist['Entrada'] = '0'
                        df_hist['Saída'] = '0'

                    # Reorganizar ou ocultar colunas técnicas do histórico se necessário
                    colunas_ocultar_hist = ['id', 'created_at', 'serial']
                    df_hist_exibicao = df_hist[[col for col in df_hist.columns if col not in colunas_ocultar_hist]]
                    
                    st.dataframe(df_hist_exibicao, use_container_width=True)
                else:
                    st.info("Nenhuma movimentação registrada.")
            except Exception as e:
                st.error(f"Erro ao carregar dados de estoque: {e}")

    if aba5 is not None: 
        with aba5:
            st.subheader("⚙️ PAINEL ADMINISTRATIVO")
            
            # Adicionado "📋 Cadastro de Equipamento" nas opções do admin
            opcao_admin = st.radio("O que deseja gerenciar?", ["Perfis de Usuários", "Cadastrar Novo Usuário", "💰 Tabela LPU", "📦 Tabela LPU DELIVERY", "📋 Cadastro de Equipamento"], horizontal=True)
            senha_admin = st.text_input("DIGITE A SENHA MESTRA:", type="password", key="admin_senha")

            if senha_admin == "@tl3t1c0":
                if opcao_admin == "Perfis de Usuários":
                    st.write("### 👤 Gerenciamento de Perfis e LPU por Técnico")
                    try:
                        dados_tecnicos = supabase.table("TECNICOS").select("*").execute()
                        df_tecnicos = pd.DataFrame(dados_tecnicos.data)
                        
                        if "lpu_atribuida" not in df_tecnicos.columns:
                            df_tecnicos["lpu_atribuida"] = "LPU Padrão"
                        else:
                            df_tecnicos["lpu_atribuida"] = df_tecnicos["lpu_atribuida"].fillna("LPU Padrão")
                            df_tecnicos["lpu_atribuida"] = df_tecnicos["lpu_atribuida"].replace("", "LPU Padrão")
                            
                        config_colunas_tec = {
                            "id": None,
                            "senha": None,
                            "created_at": None,
                            "primeiro_acesso": None,
                            "nome": st.column_config.TextColumn("Nome", required=True),
                            "cpf": st.column_config.TextColumn("CPF", required=True),
                            "email": st.column_config.TextColumn("E-mail"),
                            "telefone": st.column_config.TextColumn("Telefone"),
                            "ativo": st.column_config.CheckboxColumn("Ativo"),
                            "perfil": st.column_config.SelectboxColumn("Perfil", options=["Técnico", "Administrador"]),
                            "lpu_atribuida": st.column_config.SelectboxColumn("LPU Atribuída", options=["LPU Padrão", "DELIVERY"], required=True)
                        }

                        edited_df = st.data_editor(
                            df_tecnicos, 
                            use_container_width=True,
                            column_config=config_colunas_tec,
                            disabled=["id", "senha", "created_at", "primeiro_acesso"]
                        )

                        if st.button("SALVAR PERFIS", use_container_width=True):
                            for index, row in edited_df.iterrows():
                                lpu_val = row.get("lpu_atribuida")
                                if pd.isna(lpu_val) or not lpu_val:
                                    lpu_val = "LPU Padrão"
                                    
                                supabase.table("TECNICOS").update({
                                    "nome": row["nome"],
                                    "cpf": row["cpf"],
                                    "email": row["email"],
                                    "telefone": row["telefone"],
                                    "ativo": row["ativo"],
                                    "perfil": row["perfil"],
                                    "lpu_atribuida": lpu_val
                                }).eq("id", row["id"]).execute()
                            st.success("Perfis atualizados com sucesso!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao carregar perfis: {e}")

                elif opcao_admin == "Cadastrar Novo Usuário":
                    st.write("### ➕ Cadastro de Novo Técnico / Administrador")
                    with st.form("form_cad_admin", clear_on_submit=True):
                        c_nome = st.text_input("Nome Completo")
                        c_cpf = st.text_input("CPF (somente números)")
                        c_email = st.text_input("E-mail")
                        c_telefone = st.text_input("Telefone")
                        c_senha = st.text_input("Senha Inicial", value="123456", type="password")
                        c_perfil = st.selectbox("Perfil de Acesso", ["Técnico", "Administrador"])
                        c_lpu = st.selectbox("LPU Atribuída", ["LPU Padrão", "DELIVERY"])
                        
                        if st.form_submit_button("CADASTRAR NOVO USUÁRIO", use_container_width=True):
                            if not c_nome or not c_cpf or not c_senha:
                                st.error("⚠️ Preencha os campos obrigatórios (Nome, CPF e Senha).")
                            else:
                                try:
                                    existe = supabase.table("TECNICOS").select("cpf").eq("cpf", c_cpf).execute()
                                    if existe.data:
                                        st.error("⚠️ Este CPF já está cadastrado!")
                                    else:
                                        supabase.table("TECNICOS").insert({
                                            "nome": c_nome, 
                                            "cpf": c_cpf, 
                                            "email": c_email, 
                                            "telefone": c_telefone, 
                                            "senha": c_senha, 
                                            "perfil": c_perfil,
                                            "lpu_atribuida": c_lpu,
                                            "ativo": True,
                                            "primeiro_acesso": True if c_senha == "123456" else False
                                        }).execute()
                                        st.success(f"Usuário {c_nome} cadastrado com sucesso!")
                                except Exception as e:
                                    st.error(f"Erro ao cadastrar: {e}")

                elif opcao_admin == "💰 Tabela LPU":
                    st.write("### 💰 Gerenciamento da LPU - FIELD")
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

                elif opcao_admin == "📦 Tabela LPU DELIVERY":
                    st.write("### 📦 Gerenciamento da LPU - DELIVERY")
                    try:
                        dados_lpu_deliv = supabase.table("LPU DELIVERY").select("*").execute()
                        
                        if not dados_lpu_deliv.data:
                            df_lpu_deliv = pd.DataFrame(columns=["id", "created_at", "servico", "valor", "descricao", "min_metragem", "max_metragem"])
                        else:
                            df_lpu_deliv = pd.DataFrame(dados_lpu_deliv.data)
                        
                        configuracao_colunas_deliv = {
                            "id": None,
                            "created_at": None,
                            "servico": st.column_config.TextColumn("Serviço", required=True),
                            "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0),
                            "descricao": st.column_config.TextColumn("Descrição"),
                            "min_metragem": st.column_config.NumberColumn("Mín Metragem", min_value=0.0),
                            "max_metragem": st.column_config.NumberColumn("Máx Metragem", min_value=0.0)
                        }
                        
                        df_editada_lpu_deliv = st.data_editor(
                            df_lpu_deliv, 
                            use_container_width=True, 
                            num_rows="dynamic",
                            column_config=configuracao_colunas_deliv,
                            disabled=["id", "created_at"]
                        )

                        if st.button("SALVAR LPU DELIVERY", use_container_width=True):
                            with st.spinner("Salvando..."):
                                for index, row in df_editada_lpu_deliv.iterrows():
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
                                        supabase.table("LPU DELIVERY").update(dados_para_salvar).eq("id", id_val).execute()
                                    else:
                                        supabase.table("LPU DELIVERY").insert(dados_para_salvar).execute()
                                        
                                st.success("Tabela LPU DELIVERY atualizada com sucesso!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao acessar tabela LPU DELIVERY: {e}")

                elif opcao_admin == "📋 Cadastro de Equipamento":
                    st.write("### 📋 Gerenciamento de Cadastro de Equipamentos (Código e Descrição)")
                    try:
                        dados_cad_eq = supabase.table("CADASTRO_EQUIPAMENTOS").select("*").execute()
                        
                        if not dados_cad_eq.data:
                            df_cad_eq = pd.DataFrame(columns=["id", "created_at", "codigo", "descricao"])
                        else:
                            df_cad_eq = pd.DataFrame(dados_cad_eq.data)
                        
                        config_colunas_cad_eq = {
                            "id": None,
                            "created_at": None,
                            "codigo": st.column_config.TextColumn("Código", required=True),
                            "descricao": st.column_config.TextColumn("Descrição do Equipamento", required=True)
                        }
                        
                        df_editada_cad_eq = st.data_editor(
                            df_cad_eq, 
                            use_container_width=True, 
                            num_rows="dynamic",
                            column_config=config_colunas_cad_eq,
                            disabled=["id", "created_at"]
                        )

                        if st.button("SALVAR CADASTRO DE EQUIPAMENTOS", use_container_width=True):
                            with st.spinner("Salvando..."):
                                for index, row in df_editada_cad_eq.iterrows():
                                    codigo_val = row.get("codigo")
                                    desc_val = row.get("descricao")
                                    
                                    if not codigo_val or pd.isna(codigo_val):
                                        continue
                                        
                                    id_val = row.get("id")
                                    
                                    dados_para_salvar = {
                                        "codigo": str(codigo_val).strip(),
                                        "descricao": str(desc_val).strip() if pd.notnull(desc_val) else ""
                                    }
                                    
                                    if id_val is not None and pd.notnull(id_val) and str(id_val).strip() != "":
                                        supabase.table("CADASTRO_EQUIPAMENTOS").update(dados_para_salvar).eq("id", id_val).execute()
                                    else:
                                        supabase.table("CADASTRO_EQUIPAMENTOS").insert(dados_para_salvar).execute()
                                        
                                st.success("Cadastro de Equipamentos atualizado com sucesso!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao acessar tabela de cadastro de equipamentos: {e}")
