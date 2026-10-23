import streamlit as st
import pandas as pd
import time
import re
from supabase import create_client
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from streamlit_option_menu import option_menu
from datetime import date

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="LRVIX - Sistema de Gestão Técnica",
    page_icon="⚡",
    layout="wide"
)

# --- OCULTAR MENSAGEM DO CTRL+ENTER NO TEXT_AREA ---
st.markdown("""
    <style>
    div[data-testid="InputInstructions"] {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

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
        st.session_state.tipo_atuacao_sessao = query_params.get("tipo_atuacao", "")
        st.session_state.precisa_trocar_senha = False
    else:
        st.session_state.logado = False
        st.session_state.modo_admin = False
        st.session_state.nome_tecnico = ""
        st.session_state.perfil = ""
        st.session_state.cpf_tecnico = ""
        st.session_state.tipo_atuacao_sessao = ""
        st.session_state.precisa_trocar_senha = False

if "modo_admin" not in st.session_state:
    st.session_state.modo_admin = False
if "nome_tecnico" not in st.session_state:
    st.session_state.nome_tecnico = ""
if "perfil" not in st.session_state:
    st.session_state.perfil = ""
if "cpf_tecnico" not in st.session_state:
    st.session_state.cpf_tecnico = ""
if "tipo_atuacao_sessao" not in st.session_state:
    st.session_state.tipo_atuacao_sessao = ""
if "precisa_trocar_senha" not in st.session_state:
    st.session_state.precisa_trocar_senha = False

# --- ESTILIZAÇÃO CSS ---
st.markdown(
    """
    <style>
    /* ⬇️ BLOQUEIA O PULL-TO-REFRESH NO CELULAR ⬇️ */
    body, html {
        overscroll-behavior-y: none;
    }
    
    /* ⬇️ ALINHAR BOTÕES DA SIDEBAR À ESQUERDA ⬇️ */
    section[data-testid="stSidebar"] div.stButton > button {
        display: block !important;
        text-align: left !important;
        width: 100% !important;
        padding-left: 10px !important;
    }
    
    section[data-testid="stSidebar"] div.stButton > button * {
        text-align: left !important;
        justify-content: flex-start !important;
    }
    
    /* Oculta rodapé nativo */
    footer {visibility: hidden !important; display: none !important;}
    
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
""",
    unsafe_allow_html=True,
)

# --- CONFIGURAÇÃO ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

supabase = create_client(url, key)

def calcular_valor_lpu(tipo_servico, metragem_cabo, mercado, observacao, cpf_tecnico, tipo_atuacao_sessao):
    try:
        tabela_lpu_alvo = "LPU"
        eh_lpu_delivery = False
        
        modo = str(tipo_atuacao_sessao).strip().upper()
        if modo == "DELIVERY":
            tabela_lpu_alvo = "LPU DELIVERY"
            eh_lpu_delivery = True
        else:
            tabela_lpu_alvo = "LPU"

        try:
            res_tec = supabase.table("TECNICOS").select("lpu_atribuida").eq("cpf", cpf_tecnico).execute()
            if res_tec.data:
                lpu_atribuida = str(res_tec.data[0].get("lpu_atribuida", "")).strip().upper()
                if "MEI" in lpu_atribuida:
                    if modo == "DELIVERY":
                        tabela_lpu_alvo = "LPU_DELIVERY_MEI"
                        eh_lpu_delivery = True
                    else:
                        tabela_lpu_alvo = "LPU_MEI"
                else:
                    if modo == "DELIVERY":
                        tabela_lpu_alvo = "LPU DELIVERY"
                        eh_lpu_delivery = True
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
            
        servico_upper = str(tipo_servico).strip().upper()
        if servico_upper == "FDS":
            for item in res_lpu.data:
                if str(item.get("servico", "")).strip().upper() == "FDS":
                    return round(float(item.get("valor", 0.0)), 2)
        elif servico_upper == "IMPRODUTIVO":
            for item in res_lpu.data:
                if str(item.get("servico", "")).strip().upper() == "IMPRODUTIVO":
                    return round(float(item.get("valor", 0.0)), 2)
        elif servico_upper == "INTERNO":
            for item in res_lpu.data:
                if str(item.get("servico", "")).strip().upper() == "INTERNO":
                    return round(float(item.get("valor", 0.0)), 2)

        for item in res_lpu.data:
            min_m = item.get("min_metragem")
            max_m = item.get("max_metragem")
            
            if min_m is not None and max_m is not None:
                if float(min_m) <= metragem <= float(max_m):
                    nome_servico = str(item.get("servico", "")).strip().lower()
                    if servico_lower in nome_servico or nome_servico in servico_lower or servico_upper in ["EXTERNO"]:
                        valor_encontrado = float(item.get("valor", 0.0))
                        if eh_lpu_delivery and metragem > 500:
                            excedente = metragem - 500
                            valor_metro_adicional = 0.0
                            for it_adc in res_lpu.data:
                                s_nome = str(it_adc.get("servico", "")).strip().upper()
                                if "METRAGEM" in s_nome or "EXCEDENTE" in s_nome or "ADICIONAL" in s_nome:
                                    valor_metro_adicional = float(it_adc.get("valor", 0.0))
                                    break
                            valor_encontrado += (excedente * valor_metro_adicional)
                        return round(valor_encontrado, 2)

        for item in res_lpu.data:
            nome_servico = str(item.get("servico", "")).strip().lower()
            if nome_servico == servico_lower:
                min_m = item.get("min_metragem")
                max_m = item.get("max_metragem")
                
                if min_m is not None and max_m is not None:
                    if float(min_m) <= metragem <= float(max_m):
                        valor_encontrado = float(item.get("valor", 0.0))
                        if eh_lpu_delivery and metragem > 500:
                            excedente = metragem - 500
                            valor_metro_adicional = 0.0
                            for it_adc in res_lpu.data:
                                s_nome = str(it_adc.get("servico", "")).strip().upper()
                                if "METRAGEM" in s_nome or "EXCEDENTE" in s_nome or "ADICIONAL" in s_nome:
                                    valor_metro_adicional = float(it_adc.get("valor", 0.0))
                                    break
                            valor_encontrado += (excedente * valor_metro_adicional)
                        return round(valor_encontrado, 2)
                else:
                    valor_encontrado = float(item.get("valor", 0.0))
                    if eh_lpu_delivery and metragem > 500:
                        excedente = metragem - 500
                        valor_metro_adicional = 0.0
                        for it_adc in res_lpu.data:
                            s_nome = str(it_adc.get("servico", "")).strip().upper()
                            if "METRAGEM" in s_nome or "EXCEDENTE" in s_nome or "ADICIONAL" in s_nome:
                                valor_metro_adicional = float(it_adc.get("valor", 0.0))
                                break
                        valor_encontrado += (excedente * valor_metro_adicional)
                    return round(valor_encontrado, 2)

        faixas_com_metragem = [item for item in res_lpu.data if item.get("min_metragem") is not None and item.get("max_metragem") is not None]
        if faixas_com_metragem and metragem > 0:
            for item in faixas_com_metragem:
                min_m = float(item.get("min_metragem"))
                max_m = float(item.get("max_metragem"))
                nome_servico = str(item.get("servico", "")).strip().lower()
                
                if min_m <= metragem <= max_m and (servico_lower in nome_servico or nome_servico in servico_lower):
                    valor_encontrado = float(item.get("valor", 0.0))
                    if eh_lpu_delivery and metragem > 500:
                        excedente = metragem - 500
                        valor_metro_adicional = 0.0
                        for it_adc in res_lpu.data:
                            s_nome = str(it_adc.get("servico", "")).strip().upper()
                            if "METRAGEM" in s_nome or "EXCEDENTE" in s_nome or "ADICIONAL" in s_nome:
                                valor_metro_adicional = float(it_adc.get("valor", 0.0))
                                break
                        valor_encontrado += (excedente * valor_metro_adicional)
                    return round(valor_encontrado, 2)

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
                valor_total_calc = valor_base + (blocos_extras * valor_adicional_bloco)
                
                if eh_lpu_delivery and metragem > 500:
                    excedente_deliv = metragem - 500
                    valor_metro_adicional = 0.0
                    for it_adc in res_lpu.data:
                        s_nome = str(it_adc.get("servico", "")).strip().upper()
                        if "METRAGEM" in s_nome or "EXCEDENTE" in s_nome or "ADICIONAL" in s_nome:
                            valor_metro_adicional = float(it_adc.get("valor", 0.0))
                            break
                    valor_total_calc += (excedente_deliv * valor_metro_adicional)
                
                return round(valor_total_calc, 2)
                
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
        import io
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
                [Paragraph(f"<b>Equipe:</b> {item.get('equipe', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Responsável:</b> {item.get('responsavel_atividade', 'N/A')}", estilo_texto)],
                [Paragraph(f"<b>Nº O.S.:</b> {item.get('numero_os', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Cidade:</b> {item.get('cidade', 'N/A')}", estilo_texto)],
                [Paragraph(f"<b>Frota:</b> {item.get('frota', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Placa:</b> {item.get('placa_veiculo', item.get('placa', 'N/A'))}", estilo_texto)],
                [Paragraph(f"<b>Data:</b> {item.get('data_atividade', 'N/A')} | <b>Hora:</b> {item.get('hora', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Endereço:</b> {item.get('local_atividade', item.get('endereco', 'N/A'))}", estilo_texto)],
                [Paragraph(f"<b>Atividade a Realizar:</b> {item.get('atividade_realizar', 'N/A')}", estilo_texto), 
                 Paragraph(f"<b>Técnico Sistema:</b> {nome_tecnico}", estilo_texto)]
            ]
            
            tabela_geral = Table(dados_gerais, colWidths=[270, 270])
            tabela_geral.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_geral)
            story.append(Spacer(1, 15))
            
            dados_checklist = [
                [Paragraph("<b>2 - PLANEJAMENTO - AVALIAÇÃO INICIAL</b>", estilo_secao), ""],
                [Paragraph("<b>Item de Verificação</b>", estilo_texto_bold), Paragraph("<b>Status</b>", estilo_texto_bold)],
                [Paragraph("Circuito ou rede elétrica próxima do posto de trabalho?", estilo_texto), Paragraph(traduzir_bool(item.get('p_circuito_eletrico_proximo', 'N/A')), estilo_texto)],
                [Paragraph("Distância da rede elétrica é segura?", estilo_texto), Paragraph(traduzir_bool(item.get('p_distancia_segura_rede', 'N/A')), estilo_texto)],
                [Paragraph("Conservação do poste antes de subir?", estilo_texto), Paragraph(traduzir_bool(item.get('p_conservacao_poste', 'N/A')), estilo_texto)],
                [Paragraph("Acesso ao poste com segurança?", estilo_texto), Paragraph(traduzir_bool(item.get('p_acesso_seguro_poste', 'N/A')), estilo_texto)],
                [Paragraph("Possível realizar ponto de ancoragem para linha de vida?", estilo_texto), Paragraph(traduzir_bool(item.get('p_ancoragem_linha_vida', 'N/A')), estilo_texto)],
                [Paragraph("Condições de ancorar a escada extensível?", estilo_texto), Paragraph(traduzir_bool(item.get('p_ancorar_escada', 'N/A')), estilo_texto)],
                [Paragraph("Escada e linha de vida foram ancoradas?", estilo_texto), Paragraph(traduzir_bool(item.get('p_escada_linha_ancoradas', item.get('amarracao_escada', 'N/A'))), estilo_texto)],
                [Paragraph("Ancoragem da torre no mesmo ponto de ancoragem morto?", estilo_texto), Paragraph(traduzir_bool(item.get('p_ancoragem_torre_morto', 'N/A')), estilo_texto)],
                [Paragraph("Torre apresenta deformidades estruturais?", estilo_texto), Paragraph(traduzir_bool(item.get('p_torre_deformidades', 'N/A')), estilo_texto)],
                [Paragraph("Torre possui linha de vida em condição de uso?", estilo_texto), Paragraph(traduzir_bool(item.get('p_torre_linha_vida', 'N/A')), estilo_texto)],
                [Paragraph("Ferragens da torre deterioradas/quebradas/emendas mal feitas?", estilo_texto), Paragraph(traduzir_bool(item.get('p_ferragens_deterioradas', 'N/A')), estilo_texto)],
                [Paragraph("Concreto do morto ou base da torre deteriorado?", estilo_texto), Paragraph(traduzir_bool(item.get('p_concreto_deteriorado', 'N/A')), estilo_texto)],
                [Paragraph("Posse de todos os EPI's para atividade em altura?", estilo_texto), Paragraph(traduzir_bool(item.get('p_posse_epis', 'N/A')), estilo_texto)],
                [Paragraph("Funcionário(s) bem física e mentalmente?", estilo_texto), Paragraph(traduzir_bool(item.get('p_funcionario_bem', 'N/A')), estilo_texto)],
            ]
            
            tabela_check = Table(dados_checklist, colWidths=[380, 160])
            tabela_check.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#f9fafb')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_check)
            story.append(Spacer(1, 15))

            dados_riscos = [
                [Paragraph("<b>3 - IDENTIFICAÇÕES DOS RISCOS DA ATIVIDADE</b>", estilo_secao), ""],
                [Paragraph("Choque elétrico:", estilo_texto), Paragraph(traduzir_bool(item.get('r_choque_eletrico', 'N/A')), estilo_texto)],
                [Paragraph("Postura inadequada:", estilo_texto), Paragraph(traduzir_bool(item.get('r_postura_inadequada', 'N/A')), estilo_texto)],
                [Paragraph("Fuga de energia das partes metálicas no poste:", estilo_texto), Paragraph(traduzir_bool(item.get('r_fuga_energia', 'N/A')), estilo_texto)],
                [Paragraph("Poste ou torre com estrutura comprometida:", estilo_texto), Paragraph(traduzir_bool(item.get('r_estrutura_comprometida', item.get('integridade_poste', 'N/A'))), estilo_texto)],
                [Paragraph("Queda de altura:", estilo_texto), Paragraph(traduzir_bool(item.get('r_queda_altura', 'N/A')), estilo_texto)],
                [Paragraph("Queda de objetos:", estilo_texto), Paragraph(traduzir_bool(item.get('r_queda_objetos', 'N/A')), estilo_texto)],
                [Paragraph("Cortes e perfurações:", estilo_texto), Paragraph(traduzir_bool(item.get('r_cortes_perfuracoes', 'N/A')), estilo_texto)],
                [Paragraph("Escorregar/tropeçar:", estilo_texto), Paragraph(traduzir_bool(item.get('r_escorregar_tropecar', 'N/A')), estilo_texto)],
                [Paragraph("Atropelamento:", estilo_texto), Paragraph(traduzir_bool(item.get('r_atropelamento', 'N/A')), estilo_texto)],
                [Paragraph("Insetos ou animais peçonhentos:", estilo_texto), Paragraph(traduzir_bool(item.get('r_animais_peconhentos', item.get('animais_peconhetos', 'N/A'))), estilo_texto)],
            ]
            tabela_r = Table(dados_riscos, colWidths=[380, 160])
            tabela_r.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_r)
            story.append(Spacer(1, 15))

            dados_epcs = [
                [Paragraph("<b>4 - AÇÃO PREVENTIVA NECESSÁRIA - EPC'S E OUTRAS AÇÕES</b>", estilo_secao), ""],
                [Paragraph("Corda linha de vida 12mm²:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_corda_linha_vida', 'N/A')), estilo_texto)],
                [Paragraph("Cones de sinalização:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_cones_sinalizacao', item.get('area_sinalizada', 'N/A'))), estilo_texto)],
                [Paragraph("Bandeirola:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_bandeirola', 'N/A')), estilo_texto)],
                [Paragraph("Pisca alerta do veículo:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_pisca_alerta', 'N/A')), estilo_texto)],
                [Paragraph("Chave teste digital:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_chave_teste', 'N/A')), estilo_texto)],
                [Paragraph("Fita de sinalização:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_fita_sinalizacao', 'N/A')), estilo_texto)],
                [Paragraph("Outros:", estilo_texto), Paragraph(traduzir_bool(item.get('epc_outros', 'N/A')), estilo_texto)],
            ]
            tabela_epc = Table(dados_epcs, colWidths=[380, 160])
            tabela_epc.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_epc)
            story.append(Spacer(1, 15))

            dados_epis = [
                [Paragraph("<b>5 e 6 - DEMAIS CONTROLES E EPI'S NECESSÁRIOS</b>", estilo_secao), ""],
                [Paragraph("Luva isolante de borracha com classe de tensão e luva de cobertura:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_luva_isolante', 'N/A')), estilo_texto)],
                [Paragraph("Cinto paraquedista com talabarte:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_cinto_paraquedista', item.get('uso_cinto', 'N/A'))), estilo_texto)],
                [Paragraph("Luva de vaqueta/raspa:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_luva_vaqueta', 'N/A')), estilo_texto)],
                [Paragraph("Capacete classe B ou alpinista com jugular:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_capacete_b', item.get('uso_capacete', 'N/A'))), estilo_texto)],
                [Paragraph("Calçado de segurança:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_calcado_seguranca', 'N/A')), estilo_texto)],
                [Paragraph("Óculos de segurança:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_oculos_seguranca', 'N/A')), estilo_texto)],
                [Paragraph("Protetor auditivo:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_protetor_auditivo', 'N/A')), estilo_texto)],
                [Paragraph("Capacete de proteção facial:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_capacete_facial', 'N/A')), estilo_texto)],
                [Paragraph("Trava quedas:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_trava_quedas', 'N/A')), estilo_texto)],
                [Paragraph("Outros EPI's:", estilo_texto), Paragraph(traduzir_bool(item.get('epi_outros', 'N/A')), estilo_texto)],
                [Paragraph("<b>Seguro para realizar atividade em altura?</b>", estilo_texto_bold), Paragraph(traduzir_bool(item.get('seguro_altura', 'N/A')), estilo_texto_bold)],
            ]
            tabela_epi = Table(dados_epis, colWidths=[380, 160])
            tabela_epi.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#2563eb')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_epi)
            story.append(Spacer(1, 15))
            
            dados_paralisacao = [
                [Paragraph("<b>DIREITO DE RECUSA E EMERGÊNCIA</b>", estilo_secao), ""],
                [Paragraph(f"<b>Ciência orientações de emergência (SAMU 192 / Bombeiros 193):</b> {traduzir_bool(item.get('ciencia_emergencia', 'N/A'))}", estilo_texto), ""],
                [Paragraph(f"<b>Motivo do não atendimento / Direito de Recusa:</b><br/>{item.get('motivo_nao_atendimento') or item.get('motivo_paralisacao') or 'Nenhum motivo informado.'}", estilo_texto), ""]
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
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ]))
            story.append(tabela_paralisa)
            
            caminho_ass = item.get('assinatura_url')
            if caminho_ass and caminho_ass.strip() != "":
                try:
                    story.append(Spacer(1, 15))
                    dados_ass_cabecalho = [[Paragraph("<b>ASSINATURA DO TÉCNICO RESPONSÁVEL</b>", estilo_secao)]]
                    tabela_ass_cab = Table(dados_ass_cabecalho, colWidths=[540])
                    tabela_ass_cab.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#2563eb')),
                        ('BOTTOMPADDING', (0, 0), (0, 0), 6),
                        ('TOPPADDING', (0, 0), (0, 0), 6),
                        ('LEFTPADDING', (0, 0), (0, 0), 8),
                        ('GRID', (0, 0), (0, 0), 0.5, colors.HexColor('#e5e7eb')),
                    ]))
                    story.append(tabela_ass_cab)
                    story.append(Spacer(1, 8))
                    
                    res_bytes_ass = supabase.storage.from_("fotos_atendimentos").download(caminho_ass)
                    if res_bytes_ass:
                        temp_ass_path = os.path.join(pasta_destino, f"temp_ass_{apr_id}.jpg")
                        with open(temp_ass_path, "wb") as f:
                            f.write(res_bytes_ass)
                        
                        img_ass = Image(temp_ass_path, width=200, height=70)
                        img_ass.hAlign = 'CENTER'
                        
                        dados_bloco_assinatura = [
                            [img_ass],
                            [Paragraph(f"<b>Técnico:</b> {nome_tecnico.upper()} &nbsp;&nbsp;|&nbsp;&nbsp; <b>CPF:</b> {cpf_tec}", ParagraphStyle('TxtAss', parent=estilo_texto, alignment=1))]
                        ]
                        tabela_bloco_ass = Table(dados_bloco_assinatura, colWidths=[540])
                        tabela_bloco_ass.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('TOPPADDING', (0, 0), (-1, -1), 4),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                        ]))
                        story.append(tabela_bloco_ass)
                except Exception as e:
                    story.append(Paragraph(f"Não foi possível carregar a assinatura: {str(e)}", estilo_texto))
            
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

def obter_perfis_cadastrados():
    perfis_padrao = ["Técnico", "Administrador"]
    try:
        res_p = supabase.table("PERMISSOES").select("perfil").execute()
        if res_p.data:
            perfis_banco = [item.get("perfil") for item in res_p.data if item.get("perfil")]
            for p in perfis_banco:
                if p not in perfis_padrao:
                    perfis_padrao.append(p)
    except Exception:
        pass
    return perfis_padrao

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
                            st.query_params["tipo_atuacao"] = st.session_state.tipo_atuacao_sessao
                            
                            st.success("Senha alterada com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar senha: {e}")
        else:
            cpf_input = st.text_input("CPF")
            senha_input = st.text_input("Senha", type="password", key="login_senha")
            
            exibir_modalidade = False
            if cpf_input and str(cpf_input).strip() != "admin":
                try:
                    res_chk = supabase.table("TECNICOS").select("perfil, lpu_atribuida").eq("cpf", str(cpf_input).strip()).execute()
                    if res_chk.data:
                        d_chk = res_chk.data[0]
                        p_db = str(d_chk.get("perfil", "")).strip().lower()
                        l_db = str(d_chk.get("lpu_atribuida", "")).strip().upper()
                        if "tecnico" in p_db or "técnico" in p_db or "mei" in l_db or "delivery" in l_db or "lpu" in l_db:
                            exibir_modalidade = True
                except Exception:
                    pass

            tipo_atendimento_login = ""
            if exibir_modalidade:
                tipo_atendimento_login = st.radio(
                    "Selecione a modalidade de trabalho:",
                    options=["FIELD", "DELIVERY"],
                    index=None,
                    horizontal=True
                )
            
            st.write("")
            if st.button("Entrar", use_container_width=True):
                if exibir_modalidade and not tipo_atendimento_login:
                    st.warning("⚠️ Selecione obrigatoriamente se irá trabalhar em FIELD ou DELIVERY!")
                elif str(cpf_input).strip() == "admin" and str(senha_input).strip() == "tR294xmvYmyYhVB":
                    st.session_state.nome_tecnico = "Administrador Master"
                    st.session_state.perfil = "Administrador"
                    st.session_state.cpf_tecnico = "admin"
                    st.session_state.tipo_atuacao_sessao = "FIELD"
                    st.session_state.logado = True
                    st.session_state.precisa_trocar_senha = False
                    
                    st.query_params["logado"] = "True"
                    st.query_params["nome"] = "Administrador Master"
                    st.query_params["perfil"] = "Administrador"
                    st.query_params["cpf"] = "admin"
                    st.query_params["tipo_atuacao"] = "FIELD"
                    
                    st.rerun()
                else:
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
                                    st.session_state.tipo_atuacao_sessao = tipo_atendimento_login if exibir_modalidade else "FIELD"
                                    
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
                                        st.query_params["tipo_atuacao"] = tipo_atendimento_login if exibir_modalidade else "FIELD"
                                        
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
    perms_usuario = {
        "ve_formulario": True,
        "ve_produtividade": True,
        "ve_apr": True,
        "ve_estoque": True,
        "ve_admin": True if st.session_state.perfil == "Administrador" else False,
        "ve_colaborador": True
    }
    try:
        res_p = supabase.table("PERMISSOES").select("*").eq("perfil", st.session_state.perfil).execute()
        if res_p.data:
            perms_usuario = res_p.data[0]
    except Exception:
        pass

    with st.sidebar:
        st.markdown(f"### ⚡ Olá, **{st.session_state.nome_tecnico}**")
        st.caption(f"Perfil: **{st.session_state.perfil}** | Modo: **{st.session_state.get('tipo_atuacao_sessao', 'N/A')}**")
        
        st.markdown("---")
        
        if "menu_principal_ativo" not in st.session_state:
            st.session_state.menu_principal_ativo = "FORMULÁRIO"

        def mudar_menu(novo_menu):
            st.session_state.menu_principal_ativo = novo_menu
            st.rerun()

        if perms_usuario.get("ve_formulario", True):
            if st.button("📄 FORMULÁRIO", use_container_width=True): mudar_menu("FORMULÁRIO")
            
        if perms_usuario.get("ve_produtividade", True):
            if st.button("📊 PRODUTIVIDADE", use_container_width=True): mudar_menu("PRODUTIVIDADE")
            
        if perms_usuario.get("ve_apr", True):
            if st.button("⚠️ APR", use_container_width=True): mudar_menu("APR")

        if perms_usuario.get("ve_estoque", True):
            with st.expander("📦 ESTOQUE", expanded=(st.session_state.menu_principal_ativo == "ESTOQUE")):
                if st.button("📥 Entrada de Mercadoria", use_container_width=True):
                    st.session_state.submenu_estoque = "Entrada de Mercadoria"
                    mudar_menu("ESTOQUE")
                if st.button("🔄 Troca de Equipamento", use_container_width=True):
                    st.session_state.submenu_estoque = "Troca de Equipamento"
                    mudar_menu("ESTOQUE")
                if st.button("📋 Saldo e Histórico", use_container_width=True):
                    st.session_state.submenu_estoque = "Saldo e Histórico"
                    mudar_menu("ESTOQUE")

        if perms_usuario.get("ve_admin", False) or st.session_state.perfil == "Administrador":
            with st.expander("⚙️ ADMIN", expanded=(st.session_state.menu_principal_ativo == "ADMIN")):
                if st.button("👤 Perfis de Usuários", use_container_width=True):
                    st.session_state.submenu_admin = "Perfis de Usuários"
                    mudar_menu("ADMIN")
                if st.button("➕ Cadastrar Novo Usuário", use_container_width=True):
                    st.session_state.submenu_admin = "Cadastrar Novo Usuário"
                    mudar_menu("ADMIN")
                if st.button("🔒 Gerenciar Permissões", use_container_width=True):
                    st.session_state.submenu_admin = "Gerenciar Permissões"
                    mudar_menu("ADMIN")
                if st.button("📊 Tabela LPU", use_container_width=True):
                    st.session_state.submenu_admin = "Tabela LPU"
                    mudar_menu("ADMIN")
                if st.button("🚚 Tabela LPU Delivery", use_container_width=True):
                    st.session_state.submenu_admin = "Tabela LPU Delivery"
                    mudar_menu("ADMIN")
                if st.button("📊 Tabela LPU - MEI", use_container_width=True):
                    st.session_state.submenu_admin = "Tabela LPU - MEI"
                    mudar_menu("ADMIN")
                if st.button("🚚 Tabela LPU Delivery - MEI", use_container_width=True):
                    st.session_state.submenu_admin = "Tabela LPU Delivery - MEI"
                    mudar_menu("ADMIN")
                if st.button("🛠 Cadastro de Equipamento", use_container_width=True):
                    st.session_state.submenu_admin = "Cadastro de Equipamento"
                    mudar_menu("ADMIN")

        if perms_usuario.get("ve_colaborador", True):
            with st.expander("👥 COLABORADOR", expanded=(st.session_state.menu_principal_ativo == "COLABORADOR")):
                if st.button("📋 ATESTADO", use_container_width=True):
                    st.session_state.submenu_colaborador = "ATESTADO"
                    mudar_menu("COLABORADOR")
                if st.button("💵 CONTRA CHEQUE", use_container_width=True):
                    st.session_state.submenu_colaborador = "CONTRA CHEQUE"
                    mudar_menu("COLABORADOR")

        st.markdown("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.logado = False
            st.query_params.clear()
            st.rerun()

    if "submenu_estoque" not in st.session_state:
        st.session_state.submenu_estoque = "Entrada de Mercadoria"
    if "submenu_admin" not in st.session_state:
        st.session_state.submenu_admin = "Perfis de Usuários"
    if "submenu_colaborador" not in st.session_state:
        st.session_state.submenu_colaborador = "ATESTADO"
    
    sub_menu_estoque = st.session_state.submenu_estoque
    sub_menu_admin = st.session_state.submenu_admin
    sub_menu_colaborador = st.session_state.submenu_colaborador

    aba1 = (st.session_state.menu_principal_ativo == "FORMULÁRIO")
    aba2 = (st.session_state.menu_principal_ativo == "PRODUTIVIDADE")
    aba3 = (st.session_state.menu_principal_ativo == "APR")
    aba4 = (st.session_state.menu_principal_ativo == "ESTOQUE")
    aba5 = (st.session_state.menu_principal_ativo == "ADMIN")
    aba6 = (st.session_state.menu_principal_ativo == "COLABORADOR")

    if aba1 and perms_usuario.get("ve_formulario", True):
        st.subheader("NOVO LANÇAMENTO OPERACIONAL")
        
        if "form_version" not in st.session_state:
            st.session_state.form_version = 0

        v = st.session_state.form_version

        opcoes_equipamentos_cadastrados = ["SELECIONE..."]
        try:
            res_cad = supabase.table("CADASTRO_EQUIPAMENTOS").select("codigo, descricao").execute()
            if res_cad.data:
                opcoes_equipamentos_cadastrados += [f"{item['codigo']} - {item['descricao']}".upper() for item in res_cad.data]
        except Exception:
            pass

        tabela_lpu_alvo = "LPU"
        lista_opcoes_servicos = ["INTERNO", "EXTERNO", "IMPRODUTIVO"]
        
        modo_atual = str(st.session_state.get("tipo_atuacao_sessao", "FIELD")).strip().upper()
        if modo_atual == "DELIVERY":
            tabela_lpu_alvo = "LPU DELIVERY"
        else:
            tabela_lpu_alvo = "LPU"
        
        try:
            res_tec = supabase.table("TECNICOS").select("lpu_atribuida").eq("cpf", st.session_state.cpf_tecnico).execute()
            if res_tec.data:
                lpu_atribuida = str(res_tec.data[0].get("lpu_atribuida", "")).strip().upper()
                if "MEI" in lpu_atribuida:
                    if modo_atual == "DELIVERY":
                        tabela_lpu_alvo = "LPU_DELIVERY_MEI"
                    else:
                        tabela_lpu_alvo = "LPU_MEI"
                else:
                    if modo_atual == "DELIVERY":
                        tabela_lpu_alvo = "LPU DELIVERY"
                    else:
                        tabela_lpu_alvo = "LPU"
                
                res_servicos = supabase.table(tabela_lpu_alvo).select("servico").execute()
                if res_servicos.data:
                    servicos_db = [str(item.get("servico")).strip().upper() for item in res_servicos.data if item.get("servico")]
                    if servicos_db:
                        lista_opcoes_servicos = servicos_db
        except Exception as e:
            print(f"Erro ao carregar serviços da LPU: {e}")

        c1, c2 = st.columns(2)
        with c1:
            data_execucao = st.date_input("DATA DA EXECUÇÃO", format="DD/MM/YYYY", key=f"input_data_{v}")
            cliente = st.text_input("NOME DO CLIENTE", key=f"input_cliente_{v}")
            endereco = st.text_input("ENDEREÇO", key=f"input_endereco_{v}")
            metragem_cabo = st.text_input("CABO UTILIZADO", key=f"input_cabo_{v}")
        with c2:
            protocolo = st.text_input("PROTOCOLO", key=f"input_protocolo_{v}")
            mercado = st.selectbox("MERCADO", ["REPARO", "ATIVAÇÃO", "RETIRADA"], key=f"input_mercado_{v}")
            tipo_servico = st.selectbox("TIPO DE SERVIÇO", lista_opcoes_servicos, key=f"input_servico_{v}")
        
        observacao = st.text_area("OBSERVAÇÃO", key=f"input_obs_{v}")
        fotos_arquivos = st.file_uploader("FOTOS DO SERVIÇO (Até 5)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True, key=f"input_fotos_{v}")
        
        st.divider()
        
        habilita_troca = st.checkbox("TROCA DE EQUIPAMENTO", value=False, key=f"check_troca_{v}")
        
        quantidades_velhos = {}
        quantidades_novos = {}
        equipamentos_velhos_selecionados = []
        equipamentos_novos_selecionados = []
        status_velho = "DEFEITO"

        if habilita_troca:
            st.info("O equipamento novo sai do estoque e o velho entra.")
            tc_e1, tc_e2 = st.columns(2)
            with tc_e1:
                equipamentos_velhos_selecionados = st.multiselect("NOME DOS EQUIPAMENTOS VELHOS / RETIRADOS", [opt for opt in opcoes_equipamentos_cadastrados if opt != "SELECIONE..."], key=f"sel_velhos_{v}")
                if equipamentos_velhos_selecionados:
                    for eq in equipamentos_velhos_selecionados:
                        quantidades_velhos[eq] = st.number_input(f"Qtd Velho: {eq}", min_value=1, value=1, step=1, key=f"qtd_v_{eq}_{v}")
            with tc_e2:
                equipamentos_novos_selecionados = st.multiselect("NOME DOS EQUIPAMENTOS NOVOS", [opt for opt in opcoes_equipamentos_cadastrados if opt != "SELECIONE..."], key=f"sel_novos_{v}")
                if equipamentos_novos_selecionados:
                    for eq in equipamentos_novos_selecionados:
                        quantidades_novos[eq] = st.number_input(f"Qtd Novo: {eq}", min_value=1, value=1, step=1, key=f"qtd_n_{eq}_{v}")
            
            status_velho = st.selectbox("CONDIÇÃO DOS EQUIPAMENTOS VELHOS", ["DEFEITO", "FUNCIONAL", "ANALISE"], key=f"sel_status_velho_{v}")

        st.markdown("")
        botao_enviar = st.button("REGISTRAR ATENDIMENTO", use_container_width=True, type="primary", key=f"btn_enviar_{v}")

        if botao_enviar:
            if not cliente or not endereco or not protocolo or not metragem_cabo:
                st.error("⚠️ Por favor, preencha todos os campos obrigatórios.")
            elif habilita_troca and (not equipamentos_novos_selecionados or not equipamentos_velhos_selecionados):
                st.error("⚠️ Selecione os equipamentos para a troca.")
            else:
                valor_calculado = calcular_valor_lpu(tipo_servico, metragem_cabo, mercado, observacao, st.session_state.cpf_tecnico, st.session_state.get("tipo_atuacao_sessao", "FIELD"))
                
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
                
                sucesso_registro = registrar_atendimento(
                    data_execucao=data_execucao,
                    cliente=cliente,
                    endereco=endereco,
                    protocolo=protocolo,
                    mercado=mercado,
                    tipo_servico=tipo_servico,
                    observacao=observacao,
                    foto_url=caminhos_fotos_atendimento,
                    nome_tecnico=st.session_state.get("nome_tecnico", "Técnico"),
                    cpf_tecnico=st.session_state.cpf_tecnico,
                    metragem_cabo=metragem_cabo,
                    valor_total=valor_calculado
                )
                
                if sucesso_registro:
                    st.success("Atendimento e movimentações registrados com sucesso!")
                    st.session_state.form_version += 1
                    st.rerun()
            
    if aba2 and perms_usuario.get("ve_produtividade", True): 
        st.subheader("LISTA DE ATENDIMENTOS")
        st.caption("")
        
        if st.session_state.perfil == "Administrador":
            try:
                res_tecnicos = supabase.table("TECNICOS").select("nome, cpf, perfil").eq("ativo", True).execute()
                
                lista_tecnicos = []
                if res_tecnicos.data:
                    for t in res_tecnicos.data:
                        perfil_tec = str(t.get("perfil", "")).strip().lower()
                        if "técnico" in perfil_tec or "tecnico" in perfil_tec:
                            lista_tecnicos.append(t)
                
                opcoes_tec = {"TODOS OS TÉCNICOS": "TODOS"}
                for t in lista_tecnicos:
                    opcoes_tec[t["nome"].upper()] = t["cpf"]
                
                col_f1, col_f2 = st.columns([2, 2])
                with col_f1:
                    tecnico_selecionado = st.selectbox("FILTRAR POR TÉCNICO:", list(opcoes_tec.keys()))
                with col_f2:
                    periodo_datas = st.date_input("FILTRAR POR PERÍODO (DATA DE EXECUÇÃO):", value=[])
                
                query = supabase.table("ATENDIMENTO").select("*").order("data_execucao", desc=True)
                
                if tecnico_selecionado != "TODOS OS TÉCNICOS":
                    cpf_filtro = opcoes_tec[tecnico_selecionado]
                    query = query.eq("cpf_tecnico", cpf_filtro)
                    
            except Exception as e:
                st.error(f"Erro ao carregar lista de técnicos para o filtro: {e}")
                query = supabase.table("ATENDIMENTO").select("*").order("data_execucao", desc=True)
        else:
            col_f1, col_f2 = st.columns([2, 2])
            with col_f2:
                periodo_datas = st.date_input("FILTRAR POR PERÍODO (DATA DE EXECUÇÃO):", value=[])
            
            query = supabase.table("ATENDIMENTO").select("*").eq("cpf_tecnico", st.session_state.cpf_tecnico).in_("tipo_servico", ["INTERNO", "EXTERNO"]).order("data_execucao", desc=True)
        
        atendimentos = query.execute()
            
        if atendimentos.data:
            df = pd.DataFrame(atendimentos.data)
            
            if 'data_execucao' in df.columns:
                df['data_execucao_dt'] = pd.to_datetime(df['data_execucao'], errors='coerce')
                
                if 'periodo_datas' in locals() and isinstance(periodo_datas, tuple) and len(periodo_datas) == 2:
                    data_inicio, data_fim = periodo_datas
                    if data_inicio:
                        df = df[df['data_execucao_dt'].dt.date >= data_inicio]
                    if data_fim:
                        df = df[df['data_execucao_dt'].dt.date <= data_fim]
                elif 'periodo_datas' in locals() and isinstance(periodo_datas, tuple) and len(periodo_datas) == 1 and periodo_datas[0]:
                    data_unica = periodo_datas[0]
                    df = df[df['data_execucao_dt'].dt.date == data_unica]

                df['data_execucao'] = df['data_execucao_dt'].dt.strftime('%d/%m/%Y')
                if 'data_execucao_dt' in df.columns:
                    df = df.drop(columns=['data_execucao_dt'])
            
            st.markdown("---")
            
            ids_validos = df['id'].tolist() if 'id' in df.columns else []
            atendimentos_filtrados = [item for item in atendimentos.data if item.get('id') in ids_validos]

            with st.expander("ATENDIMENTOS CADASTRADOS", expanded=False):
                for idx, item in enumerate(atendimentos_filtrados):
                    data_original = item.get('data_execucao', '')
                    try:
                        data_formatada = pd.to_datetime(data_original).strftime('%d/%m/%Y')
                    except Exception:
                        data_formatada = data_original
                    
                    label_expander = f"📅 {data_formatada} | 🏷️ PROT: {str(item.get('protocolo', 'N/A')).upper()} | 👤 {str(item.get('cliente', 'N/A')).upper()} | 🔧 {str(item.get('tipo_servico', 'N/A')).upper()}"
                    
                    with st.expander(label_expander):
                        col_det1, col_det2 = st.columns(2)
                        with col_det1:
                            st.write(f"**CLIENTE:** {str(item.get('cliente', 'N/A')).upper()}")
                            st.write(f"**ENDEREÇO:** {str(item.get('endereco', 'N/A')).upper()}")
                            st.write(f"**PROTOCOLO:** {str(item.get('protocolo', 'N/A')).upper()}")
                            st.write(f"**MERCADO:** {str(item.get('mercado', 'N/A')).upper()}")
                        with col_det2:
                            st.write(f"**TIPO DE SERVIÇO:** {str(item.get('tipo_servico', 'N/A')).upper()}")
                            st.write(f"**CABO UTILIZADO:** {str(item.get('metragem_cabo', 'N/A')).upper()}")
                            if st.session_state.perfil == "Administrador":
                                st.write(f"**RESPONSÁVEL:** {str(item.get('responsavel', 'N/A')).upper()}")
                                val_tot = item.get('valor_total', 0)
                                st.write(f"**VALOR LPU:** R$ {float(val_tot):,.2f}" if pd.notnull(val_tot) else "R$ 0,00")
                        
                        st.markdown("---")
                        st.markdown(f"**OBSERVAÇÃO COMPLETA:**")
                        st.info(str(item.get('observacao', 'Nenhuma observação registrada.')).upper())
            
            st.write("")
            st.markdown("INDICADORES E PROJEÇÃO")
            
            try:
                df_calc = df.copy()
                dias_trabalhados = df_calc['data_execucao'].nunique() if 'data_execucao' in df_calc.columns else 0
                
                df_calc['valor_numerico'] = pd.to_numeric(df_calc['valor_total'], errors='coerce').fillna(0.0)
                df_calc['tipo_servico_upper'] = df_calc['tipo_servico'].astype(str).str.strip().str.upper()
                
                df_produtivos = df_calc[~df_calc['tipo_servico_upper'].isin(['IMPRODUTIVO', 'FDS'])]
                
                total_servicos_produtivos = len(df_produtivos)
                media_servico = (total_servicos_produtivos / dias_trabalhados) if dias_trabalhados > 0 else 0.0
                
                soma_valor_produtivos = df_produtivos['valor_numerico'].sum()
                ticket_medio = (soma_valor_produtivos / total_servicos_produtivos) if total_servicos_produtivos > 0 else 0.0
                total_geral = soma_valor_produtivos
                
                contagem_servicos = df_produtivos['tipo_servico'].astype(str).str.upper().value_counts().to_dict()
                resumo_servicos_str = " | ".join([f"{str(k).upper()}: {v}" for k, v in contagem_servicos.items()])
                if not resumo_servicos_str:
                    resumo_servicos_str = "NENHUM SERVIÇO PRODUTIVO"

                tabela_html = f"""
                <div style="overflow-x:auto;">
                    <table style="width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif; font-size: 14px;">
                        <thead>
                            <tr style="background-color: #4a90e2; color: white;">
                                <th style="border: 1px solid #ddd; padding: 10px;" colspan="5">PROJEÇÃO E INDICADORES (EXCLUINDO IMPRODUTIVOS)</th>
                            </tr>
                            <tr style="background-color: #5ba4e6; color: white;">
                                <th style="border: 1px solid #ddd; padding: 8px;">DIAS TRABALHADOS</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">SERV. PRODUTIVOS ({resumo_servicos_str})</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">MED. SERVIÇO</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">TICKET MÉDIO</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">T. GERAL</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background-color: #f9f9f9; color: #333; font-weight: bold;">
                                <td style="border: 1px solid #ddd; padding: 10px;">{dias_trabalhados}</td>
                                <td style="border: 1px solid #ddd; padding: 10px;">{total_servicos_produtivos}</td>
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
                st.subheader("VISUALIZADOR DE FOTOS")
                
                opcoes_atendimento = {}
                for item in atendimentos.data:
                    data_original = item.get('data_execucao', '')
                    try:
                        data_formatada = pd.to_datetime(data_original).strftime('%d/%m/%Y')
                    except Exception:
                        data_formatada = data_original
                    
                    label = f"DATA: {data_formatada} | PROT: {str(item.get('protocolo', 'N/A')).upper()} | CLIENTE: {str(item.get('cliente', 'N/A')).upper()}"
                    opcoes_atendimento[label] = item
                    
                atendimento_selecionado = st.selectbox(
                    "SELECIONE UM ATENDIMENTO PARA VISUALIZAR AS FOTOS:", 
                    ["SELECIONE..."] + list(opcoes_atendimento.keys())
                )
                
                if atendimento_selecionado != "SELECIONE...":
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
                                        st.image(res_bytes, caption=f"ANEXO {idx+1}", use_container_width=True)
                                    except Exception as e:
                                        st.error(f"Erro ao carregar a foto {idx+1}")
                        else:
                            st.info("Nenhuma foto válida anexada a este atendimento.")
                        
        else:
            st.info("Nenhum atendimento registrado.")

    if aba3 and perms_usuario.get("ve_apr", True):
        st.subheader("ANÁLISE PRELIMINAR DE RISCO (APR)")
        
        if st.session_state.get("sucesso_apr"):
            st.success(st.session_state.sucesso_apr)
            st.balloons()
            del st.session_state["sucesso_apr"]

        with st.expander("APRS CADASTRADAS", expanded=False):
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
                            if st.button(f"APR {num_exibicao}", key=f"btn_apr_{item['id']}"):
                                arquivo = gerar_pdf_apr(item['id'])
                                with open(arquivo, "rb") as f:
                                    st.download_button(
                                        label="BAIXAR PDF",
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
            st.markdown("### 1 - Identificação da Atividade")
            col_id1, col_id2 = st.columns(2)
            with col_id1:
                equipe = st.text_input("EQUIPE")
                responsavel_atividade = st.text_input("RESPONSÁVEL PELA ATIVIDADE")
                numero_os = st.text_input("NÚMERO DA O.S.")
                cidade = st.text_input("CIDADE")
                frota = st.text_input("FROTA")
            with col_id2:
                data_atividade = st.date_input("DATA")
                hora = st.text_input("HORA (ex: 08:00)")
                endereco = st.text_input("ENDEREÇO")
                atividade_realizar = st.text_input("1- Atividade a realizar:")
                placa = st.text_input("PLACA")
            
            st.markdown("---")
            st.markdown("### 2 - Planejamento - Avaliação Inicial")
            p1, p2 = st.columns(2)
            with p1:
                p_circuito_eletrico_proximo = st.selectbox("Há existência de circuito ou rede elétrica próxima do posto de trabalho?", ["NÃO", "SIM"])
                p_distancia_segura_rede = st.selectbox("Verificou se a distância da rede elétrica é segura ao seu posto de trabalho?", ["NÃO", "SIM"])
                p_conservacao_poste = st.selectbox("Verificou a conservação do poste antes de subir?", ["NÃO", "SIM"])
                p_acesso_seguro_poste = st.selectbox("O acesso ao poste pode ser feito com segurança?", ["NÃO", "SIM"])
                p_ancoragem_linha_vida = st.selectbox("É possível realizar ponto de ancoragem para a linha de vida?", ["NÃO", "SIM"])
                p_ancorar_escada = st.selectbox("Existem condições de ancorar a escada extensível?", ["NÃO", "SIM"])
                p_escada_linha_ancoradas = st.selectbox("A escada e linha de vida foram ancoradas?", ["NÃO", "SIM"])
            with p2:
                p_ancoragem_torre_morto = st.selectbox("Verificou se a ancoragem da torre está no mesmo ponto de ancoragem morto?", ["NÃO", "SIM"])
                p_torre_deformidades = st.selectbox("A torre apresenta deformidades que comprometam sua estrutura?", ["NÃO", "SIM"])
                p_torre_linha_vida = st.selectbox("A torre possui linha de vida e a mesma está em condição de uso?", ["NÃO", "SIM"])
                p_ferragens_deterioradas = st.selectbox("As ferragens da torre encontram-se deterioradas com partes quebradas ou emendas mal feitas?", ["NÃO", "SIM"])
                p_concreto_deteriorado = st.selectbox("O concreto do morto ou base da torre apresenta deterioração que comprometa sua estabilidade?", ["NÃO", "SIM"])
                p_posse_epis = st.selectbox("Estão de posse de todos os EPI's para a atividade em altura?", ["NÃO", "SIM"])
                p_funcionario_bem = st.selectbox("Funcionário(s) está (ão) bem fisicamente e mentalmente?", ["NÃO", "SIM"])

            st.markdown("---")
            st.markdown("### 3 - Identificações dos riscos da atividade")
            r1, r2 = st.columns(2)
            with r1:
                r_choque_eletrico = st.selectbox("Choque elétrico:", ["NÃO", "SIM"])
                r_postura_inadequada = st.selectbox("Postura inadequada:", ["NÃO", "SIM"])
                r_fuga_energia = st.selectbox("Fuga de energia das partes metálicas no poste:", ["NÃO", "SIM"])
                r_estrutura_comprometida = st.selectbox("Poste ou torre com estrutura comprometida:", ["NÃO", "SIM"])
                r_queda_altura = st.selectbox("Queda de altura:", ["NÃO", "SIM"])
            with r2:
                r_queda_objetos = st.selectbox("Queda de objetos:", ["NÃO", "SIM"])
                r_cortes_perfuracoes = st.selectbox("Cortes e perfurações:", ["NÃO", "SIM"])
                r_escorregar_tropecar = st.selectbox("Escorregar/tropeçar:", ["NÃO", "SIM"])
                r_atropelamento = st.selectbox("Atropelamento:", ["NÃO", "SIM"])
                r_animais_peconhentos = st.selectbox("Insetos ou animais peçonhentos:", ["NÃO", "SIM"])

            st.markdown("---")
            st.markdown("### 4 - Ação preventiva necessária - EPC's e outras ações")
            ep1, ep2 = st.columns(2)
            with ep1:
                epc_corda_linha_vida = st.selectbox("Corda linha de vida 12mm²", ["NÃO", "SIM"])
                epc_cones_sinalizacao = st.selectbox("Cones de sinalização:", ["NÃO", "SIM"])
                epc_bandeirola = st.selectbox("Bandeirola:", ["NÃO", "SIM"])
                epc_pisca_alerta = st.selectbox("Pisca alerta do veículo:", ["NÃO", "SIM"])
            with ep2:
                epc_chave_teste = st.selectbox("Chave teste digital:", ["NÃO", "SIM"])
                epc_fita_sinalizacao = st.selectbox("Fita de sinalização:", ["NÃO", "SIM"])
                epc_outros = st.selectbox("Outros (EPC's):", ["NÃO", "SIM"])

            st.markdown("---")
            st.markdown("### 5 e 6 - Ação preventiva necessária - EPI's e Demais Controles")
            ei1, ei2 = st.columns(2)
            with ei1:
                epi_luva_isolante = st.selectbox("Luva isolante de borracha com classe de tensão e luva de cobertura:", ["NÃO", "SIM"])
                epi_cinto_paraquedista = st.selectbox("Cinto paraquedista com talabarte:", ["NÃO", "SIM"])
                epi_luva_vaqueta = st.selectbox("Luva de vaqueta/raspa:", ["NÃO", "SIM"])
                epi_capacete_b = st.selectbox("Capacete classe B ou alpinista com jugular:", ["NÃO", "SIM"])
                epi_calcado_seguranca = st.selectbox("Calçado de segurança:", ["NÃO", "SIM"])
            with ei2:
                epi_oculos_seguranca = st.selectbox("Óculos de Segurança:", ["NÃO", "SIM"])
                epi_protetor_auditivo = st.selectbox("Protetor auditivo:", ["NÃO", "SIM"])
                epi_capacete_facial = st.selectbox("Capacete de proteção facial:", ["NÃO", "SIM"])
                epi_trava_quedas = st.selectbox("Trava quedas:", ["NÃO", "SIM"])
                epi_outros = st.selectbox("Outros (EPI's):", ["NÃO", "SIM"])

            st.markdown("---")
            seguro_altura = st.selectbox("Ao atender todos os requisitos de segurança para trabalho em altura, você está seguro para realizar essa atividade?", ["NÃO", "SIM"])

            st.markdown("---")
            st.markdown("**Orientações de emergência:** ligar para SAMU-192 ou Bombeiros 193; aplicar técnicas de resgate de acidentados; realizar primeiros socorros e comunicar o acidente à liderança.")
            ciencia_emergencia = st.selectbox("Sim, estou ciente sobre a orientação de emergência.", ["NÃO", "SIM"])
            
            st.markdown("**Em caso de Risco Iminente:** Interromper suas atividades exercendo o direito de recusa, sempre que constatarem evidências de riscos graves e iminentes...")
            motivo_nao_atendimento = st.text_area("Descreva abaixo o motivo do não atendimento:")

            st.write("### ✍️ ASSINATURA DO TÉCNICO (Obrigatório desenhar abaixo)")
            
            from streamlit_drawable_canvas import st_canvas
            
            canvas_result = st_canvas(
                fill_color="rgba(255, 255, 255, 0)",
                stroke_width=2,
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=150,
                width=500,
                drawing_mode="freedraw",
                return_image_data=True,
                key="canvas_assinatura",
            )
            
            st.write("")
            botao_enviar = st.form_submit_button("REGISTRAR APR", use_container_width=True)
            
            if botao_enviar:
                if canvas_result.image_data is None:
                    st.error("⚠️ Por favor, faça a assinatura no quadro antes de registrar a APR.")
                else:
                    caminho_assinatura_salva = ""
                    try:
                        import numpy as np
                        from PIL import Image as PILImage
                        import io
                        
                        img_data = canvas_result.image_data
                        
                        if img_data is not None:
                            img_array = img_data.astype(np.uint8)
                            pil_img = PILImage.fromarray(img_array)
                            
                            if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
                                fundo_branco = PILImage.new("RGB", pil_img.size, (255, 255, 255))
                                fundo_branco.paste(pil_img, mask=pil_img.split()[3])
                                pil_img_final = fundo_branco
                            else:
                                pil_img_final = pil_img.convert("RGB")
                            
                            buffered = io.BytesIO()
                            pil_img_final.save(buffered, format="JPEG", quality=95)
                            img_bytes = buffered.getvalue()
                            
                            timestamp = int(time.time())
                            caminho_assinatura_salva = f"assinaturas/assinatura_{timestamp}.jpg"
                            
                            supabase.storage.from_("fotos_atendimentos").upload(caminho_assinatura_salva, img_bytes)
                    except Exception as e:
                        st.error(f"Erro ao salvar a assinatura: {e}")
                    
                    try:
                        cpf_logado = st.session_state.get("cpf_tecnico", "")
                        perfil_usuario = st.session_state.get("perfil", "Técnico")
                        numero_gerado = str(int(time.time()))[-6:] 

                        dados_payload = {
                            "numero_controle": numero_gerado,
                            "data_atividade": str(data_atividade),
                            "local_atividade": endereco.upper() if endereco else "",
                            "placa_veiculo": placa.upper() if placa else "",
                            "cpf_tecnico": cpf_logado,
                            "perfil": perfil_usuario.upper(),
                            "assinatura_url": caminho_assinatura_salva,
                            "uso_cinto": (epi_cinto_paraquedista == "SIM"),
                            "uso_capacete": (epi_capacete_b == "SIM"),
                            "amarracao_escada": (p_escada_linha_ancoradas == "SIM"),
                            "area_sinalizada": (epc_cones_sinalizacao == "SIM"),
                            "verificacao_geral": True,
                            "chuva": False,
                            "animais_peconhentos": (r_animais_peconhentos == "SIM"),  # Corrigido corretamente com 'h'
                            "poste_energizado": "SIM" if r_choque_eletrico == "SIM" else "NÃO",
                            "integridade_poste": "RUIM" if r_estrutura_comprometida == "SIM" else "BOM",
                            "houve_paralisacao": "SIM" if motivo_nao_atendimento else "NÃO",
                            "motivo_paralisacao": motivo_nao_atendimento.upper() if motivo_nao_atendimento else ""
                        }

                        resposta = supabase.table("APR").insert(dados_payload).execute()
                        
                        st.session_state["sucesso_apr"] = f"APR {numero_gerado} registrada com sucesso!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar APR no banco: {e}")

    if aba4 and perms_usuario.get("ve_estoque", True):
        st.subheader("GESTÃO DE ESTOQUE E MOVIMENTAÇÕES")
        
        opcoes_equipamentos_cadastrados = ["SELECIONE..."]
        try:
            res_cad = supabase.table("CADASTRO_EQUIPAMENTOS").select("codigo, descricao").execute()
            if res_cad.data:
                opcoes_equipamentos_cadastrados += [f"{item['codigo']} - {item['descricao']}".upper() for item in res_cad.data]
        except Exception:
            pass

        def renderizar_saldo_e_historico():
            st.markdown("SALDO ATUAL DO ESTOQUE E HISTÓRICO")
            try:
                res_estoque = supabase.table("ESTOQUE").select("*").execute()
                if res_estoque.data:
                    st.write("ITENS CADASTRADOS NO ESTOQUE")
                    df_est = pd.DataFrame(res_estoque.data)
                    
                    if 'serial' in df_est.columns:
                        df_est = df_est.rename(columns={'serial': 'qtd'})
                    
                    colunas_ocultar_est = ['id', 'created_at']
                    df_est_exibicao = df_est[[col for col in df_est.columns if col not in colunas_ocultar_est]]
                    
                    st.dataframe(df_est_exibicao, use_container_width=True)
                else:
                    st.info("Nenhum item registrado no estoque.")
                
                st.divider()
                res_hist = supabase.table("HISTORICO_ESTOQUE").select("*").order("created_at", desc=True).execute()
                if res_hist.data:
                    st.write("HISTÓRICO DE MOVIMENTAÇÕES")
                    df_hist = pd.DataFrame(res_hist.data)
                    
                    colunas_ocultar_hist = ['id', 'created_at', 'serial']
                    df_hist_exibicao = df_hist[[col for col in df_hist.columns if col not in colunas_ocultar_hist]]
                    
                    st.dataframe(df_hist_exibicao, use_container_width=True)
                else:
                    st.info("Nenhuma movimentação registrada.")
            except Exception as e:
                st.error(f"Erro ao carregar dados de estoque: {e}")

        if st.session_state.perfil == "Administrador":
            opcao_estoque = sub_menu_estoque if sub_menu_estoque else "Entrada de Mercadoria"
            
            if opcao_estoque == "Entrada de Mercadoria":
                st.markdown("REGISTRAR ENTRADA DE NOVOS ITENS / EQUIPAMENTOS")
                with st.form("form_entrada_estoque", clear_on_submit=True):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        item_selecionado = st.selectbox("NOME DO EQUIPAMENTO / MATERIAL", opcoes_equipamentos_cadastrados)
                        quantidade = st.number_input("QUANTIDADE", min_value=1, value=1, step=1)
                    with ec2:
                        origem_nota = st.text_input("NOTA FISCAL / FORNECEDOR / ORIGEM")
                    
                    obs_entrada = st.text_area("OBSERVAÇÕES DA ENTRADA")
                    
                    if st.form_submit_button("REGISTRAR ENTRADA", use_container_width=True):
                        if item_selecionado == "SELECIONE..." or not quantidade or quantidade < 1:
                            st.error("⚠️ Selecione o equipamento e informe uma quantidade válida.")
                        else:
                            try:
                                supabase.table("ESTOQUE").insert({
                                    "equipamento": item_selecionado,
                                    "serial": str(quantidade),
                                    "status": "DISPONIVEL",
                                    "localizacao": "ESTOQUE CENTRAL",
                                    "observacao": obs_entrada.upper()
                                }).execute()
                                
                                supabase.table("HISTORICO_ESTOQUE").insert({
                                    "tipo_movimentacao": "ENTRADA",
                                    "equipamento": item_selecionado,
                                    "serial": str(quantidade),
                                    "responsavel": st.session_state.nome_tecnico.upper(),
                                    "detalhes": f"Entrada de {quantidade} un. Origem: {obs_entrada or 'N/A'}".upper()
                                }).execute()
                                
                                st.success("Entrada registrada com sucesso no estoque!")
                            except Exception as e:
                                st.error(f"Erro ao registrar entrada: {e}")

            elif opcao_estoque == "Troca de Equipamento":
                st.markdown("REGISTRAR TROCA DE EQUIPAMENTO (CLIENTE)")
                st.info("O equipamento **novo** sai do estoque para o cliente, e o equipamento **velho** (defeituoso/retirado) entra no estoque.")
                
                with st.form("form_troca_equipamento", clear_on_submit=True):
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        cliente_troca = st.text_input("NOME DO CLIENTE / PROTOCOLO")
                        equipamentos_novos_multi = st.multiselect("NOME DOS EQUIPAMENTOS NOVOS", [opt for opt in opcoes_equipamentos_cadastrados if opt != "SELECIONE..."], key="eq_novo_multi")
                    with tc2:
                        equipamentos_velhos_multi = st.multiselect("NOME DOS EQUIPAMENTOS VELHOS / RETIRADOS", [opt for opt in opcoes_equipamentos_cadastrados if opt != "SELECIONE..."], key="eq_velho_multi")
                        status_velho = st.selectbox("CONDIÇÃO DOS EQUIPAMENTOS VELHOS", ["DEFEITO", "FUNCIONAL", "ANALISE"])
                    
                    motivo_troca = st.text_area("MOTIVO DA TROCA (ex: Queimado por raio, lentidão)")
                    
                    if st.form_submit_button("CONFIRMAR TROCA DE EQUIPAMENTOS", use_container_width=True):
                        if not cliente_troca or not equipamentos_novos_multi or not equipamentos_velhos_multi:
                            st.error("⚠️ Preencha os campos obrigatórios e selecione os equipamentos corretamente.")
                        else:
                            try:
                                for eq_novo in equipamentos_novos_multi:
                                    supabase.table("ESTOQUE").insert({
                                        "equipamento": eq_novo,
                                        "serial": "1",
                                        "status": f"INSTALADO - {cliente_troca}".upper(),
                                        "localizacao": f"CLIENTE: {cliente_troca}".upper(),
                                        "observacao": f"Saída por troca. Motivo: {motivo_troca}".upper()
                                    }).execute()
                                
                                for eq_velho in equipamentos_velhos_multi:
                                    supabase.table("ESTOQUE").insert({
                                        "equipamento": eq_velho,
                                        "serial": "1",
                                        "status": status_velho,
                                        "localizacao": "ESTOQUE CENTRAL",
                                        "observacao": f"Retirado do cliente {cliente_troca}. Motivo: {motivo_troca}".upper()
                                    }).execute()
                                
                                str_novos = " | ".join(equipamentos_novos_multi)
                                str_velhos = " | ".join(equipamentos_velhos_multi)
                                supabase.table("HISTORICO_ESTOQUE").insert({
                                    "tipo_movimentacao": "TROCA",
                                    "equipamento": f"Novos: {str_novos} | Velhos: {str_velhos}".upper(),
                                    "serial": "1",
                                    "responsavel": st.session_state.nome_tecnico.upper(),
                                    "detalhes": f"Cliente: {cliente_troca} | Motivo: {motivo_troca}".upper()
                                }).execute()
                                
                                st.success("Troca registrada com sucesso! Equipamentos novos baixados e velhos adicionados ao estoque.")
                            except Exception as e:
                                st.error(f"Erro ao processar troca: {e}")

            elif opcao_estoque == "Saldo e Histórico":
                renderizar_saldo_e_historico()
        else:
            renderizar_saldo_e_historico()

    if aba5 and (perms_usuario.get("ve_admin", False) or st.session_state.perfil == "Administrador"): 
        st.subheader("PAINEL ADMINISTRATIVO")
        
        if st.session_state.perfil == "Administrador":
            senha_admin = "tR294xmvYmyYhVB"
        else:
            senha_admin = st.text_input("DIGITE LA SENHA MESTRA:", type="password", key="admin_senha")

        if senha_admin == "tR294xmvYmyYhVB":
            opcao_admin = sub_menu_admin if sub_menu_admin else "Perfis de Usuários"
            lista_perfis_cadastrados = obter_perfis_cadastrados()
            
            if opcao_admin == "Gerenciar Permissões":
                st.write("### 🔒 CONTROLE DE ACESSO POR PERFIL (RBAC)")
                st.info("Para criar um novo perfil, clique na última linha vazia abaixo e digite o nome do perfil. Depois marque as permissões e clique em **SALVAR PERMISSÕES**.")
                try:
                    dados_perms = supabase.table("PERMISSOES").select("*").execute()
                    
                    if not dados_perms.data:
                        df_perms = pd.DataFrame([
                            {"id": 1, "perfil": "Técnico", "ve_formulario": True, "ve_produtividade": True, "ve_apr": True, "ve_estoque": False, "ve_admin": False, "ve_colaborador": True},
                            {"id": 2, "perfil": "Administrador", "ve_formulario": True, "ve_produtividade": True, "ve_apr": True, "ve_estoque": True, "ve_admin": True, "ve_colaborador": True}
                        ])
                    else:
                        df_perms = pd.DataFrame(dados_perms.data)

                    colunas_exibicao = ["id", "perfil", "ve_formulario", "ve_produtividade", "ve_apr", "ve_estoque", "ve_admin", "ve_colaborador"]
                    for col in colunas_exibicao:
                        if col not in df_perms.columns:
                            df_perms[col] = False if col not in ["perfil", "id"] else ""

                    df_perms = df_perms[colunas_exibicao]

                    config_col_perms = {
                        "id": None,
                        "perfil": st.column_config.TextColumn("Perfil", required=True),
                        "ve_formulario": st.column_config.CheckboxColumn("Ver Formulário", default=True),
                        "ve_produtividade": st.column_config.CheckboxColumn("Ver Produtividade", default=True),
                        "ve_apr": st.column_config.CheckboxColumn("Ver APR", default=True),
                        "ve_estoque": st.column_config.CheckboxColumn("Ver Estoque", default=False),
                        "ve_admin": st.column_config.CheckboxColumn("Ver Admin", default=False),
                        "ve_colaborador": st.column_config.CheckboxColumn("Ver Colaborador", default=True)
                    }

                    df_edit_perms = st.data_editor(
                        df_perms, 
                        use_container_width=True, 
                        column_config=config_col_perms, 
                        disabled=["id"],
                        num_rows="dynamic",
                        key="editor_permissoes_perfis"
                    )

                    if st.button("SALVAR PERMISSÕES", use_container_width=True):
                        registros_salvos = 0
                        
                        for _, row in df_edit_perms.iterrows():
                            perfil_nome = str(row["perfil"]).strip() if pd.notnull(row["perfil"]) else ""
                            
                            if not perfil_nome or perfil_nome.lower() in ["nan", "none", ""]:
                                continue
                            
                            payload = {
                                "perfil": str(perfil_nome),
                                "ve_formulario": bool(row["ve_formulario"]) if pd.notnull(row["ve_formulario"]) else True,
                                "ve_produtividade": bool(row["ve_produtividade"]) if pd.notnull(row["ve_produtividade"]) else True,
                                "ve_apr": bool(row["ve_apr"]) if pd.notnull(row["ve_apr"]) else True,
                                "ve_estoque": bool(row["ve_estoque"]) if pd.notnull(row["ve_estoque"]) else False,
                                "ve_admin": bool(row["ve_admin"]) if pd.notnull(row["ve_admin"]) else False,
                                "ve_colaborador": bool(row["ve_colaborador"]) if pd.notnull(row["ve_colaborador"]) else True
                            }

                            id_val = row["id"]
                            
                            if pd.notnull(id_val) and str(id_val).strip() != "" and str(id_val).lower() != "nan":
                                supabase.table("PERMISSOES").update(payload).eq("id", int(id_val)).execute()
                            else:
                                supabase.table("PERMISSOES").insert(payload).execute()
                                
                            registros_salvos += 1

                        if registros_salvos > 0:
                            st.success("Permissões e Perfis salvos com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Nenhum perfil válido preenchido.")

                except Exception as e:
                    st.error(f"Erro ao gerenciar permissões: {e}")

            elif opcao_admin == "Perfis de Usuários":
                st.write("GERENCIAMENTO DE PERFIS E LPU POR TÉCNICO")
                try:
                    dados_tecnicos = supabase.table("TECNICOS").select("*").execute()
                    df_tecnicos = pd.DataFrame(dados_tecnicos.data)
                    
                    if "lpu_atribuida" not in df_tecnicos.columns:
                        df_tecnicos["lpu_atribuida"] = "LPU Padrão"
                    else:
                        df_tecnicos["lpu_atribuida"] = df_tecnicos["lpu_atribuida"].fillna("LPU Padrão")
                        df_tecnicos["lpu_atribuida"] = df_tecnicos["lpu_atribuida"].replace("", "LPU Padrão")

                    if "telegram_chat_id" not in df_tecnicos.columns:
                        df_tecnicos["telegram_chat_id"] = ""
                    else:
                        df_tecnicos["telegram_chat_id"] = df_tecnicos["telegram_chat_id"].fillna("")

                    if "data_nascimento" not in df_tecnicos.columns:
                        df_tecnicos["data_nascimento"] = ""
                    else:
                        df_tecnicos["data_nascimento"] = df_tecnicos["data_nascimento"].fillna("")
                        
                    config_colunas_tec = {
                        "id": None,
                        "created_at": None,
                        "primeiro_acesso": None,
                        "nome": st.column_config.TextColumn("Nome", required=True),
                        "cpf": st.column_config.TextColumn("CPF", required=True),
                        "email": st.column_config.TextColumn("E-mail"),
                        "telefone": st.column_config.TextColumn("Telefone"),
                        "telegram_chat_id": st.column_config.TextColumn("Chat ID Telegram"),
                        "data_nascimento": st.column_config.TextColumn("Data de Nascimento"),
                        "senha": st.column_config.TextColumn("Senha"),
                        "ativo": st.column_config.CheckboxColumn("Ativo"),
                        "perfil": st.column_config.SelectboxColumn("Perfil", options=lista_perfis_cadastrados, required=True),
                        "lpu_atribuida": st.column_config.SelectboxColumn("LPU Atribuída", options=["LPU Padrão", "DELIVERY", "LPU - MEI", "LPU DELIVERY - MEI"], required=True)
                    }

                    edited_df = st.data_editor(
                        df_tecnicos, 
                        use_container_width=True,
                        column_config=config_colunas_tec,
                        disabled=["id", "created_at", "primeiro_acesso"]
                    )

                    if st.button("SALVAR PERFIS", use_container_width=True):
                        for index, row in edited_df.iterrows():
                            lpu_val = row.get("lpu_atribuida")
                            if pd.isna(lpu_val) or not lpu_val:
                                lpu_val = "LPU Padrão"

                            dt_nasc = row.get("data_nascimento")
                            if pd.isna(dt_nasc) or str(dt_nasc).strip() == "" or str(dt_nasc).lower() in ["nan", "none"]:
                                dt_nasc_val = None
                            else:
                                dt_nasc_val = str(dt_nasc).strip()

                            chat_id_val = row.get("telegram_chat_id")
                            if pd.isna(chat_id_val) or str(chat_id_val).strip() == "" or str(chat_id_val).lower() in ["nan", "none"]:
                                chat_id_final = None
                            else:
                                try:
                                    chat_id_final = int(str(chat_id_val).strip())
                                except ValueError:
                                    chat_id_final = None
                                
                            supabase.table("TECNICOS").update({
                                "nome": row["nome"].upper() if pd.notnull(row["nome"]) else row["nome"],
                                "cpf": str(row["cpf"]).strip(),
                                "email": str(row["email"]).strip() if pd.notnull(row["email"]) else None,
                                "telefone": str(row["telefone"]).strip() if pd.notnull(row["telefone"]) else None,
                                "telegram_chat_id": chat_id_final,
                                "data_nascimento": dt_nasc_val,
                                "senha": str(row["senha"]).strip(),
                                "ativo": bool(row["ativo"]),
                                "perfil": str(row["perfil"]),
                                "lpu_atribuida": lpu_val
                            }).eq("id", row["id"]).execute()
                        st.success("Perfis atualizados com sucesso!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao carregar perfis: {e}")

            elif opcao_admin == "Cadastrar Novo Usuário":
                st.write("### CADASTRO DE NOVO TÉCNICO / ADMINISTRADOR")
                with st.form("form_cad_admin", clear_on_submit=True):
                    c_nome = st.text_input("NOME COMPLETO")
                    c_cpf = st.text_input("CPF (somente números)")
                    c_email = st.text_input("E-MAIL")
                    c_telefone = st.text_input("TELEFONE")
                    c_telegram = st.text_input("CHAT ID DO TELEGRAM (Apenas números)")
                    c_nascimento = st.text_input("DATA DE NASCIMENTO (Ex: DD/MM/AAAA ou AAAA-MM-DD)")
                    c_senha = st.text_input("SENHA INICIAL", value="123456", type="password")
                    c_perfil = st.selectbox("PERFIL DE ACESSO", lista_perfis_cadastrados)
                    c_lpu = st.selectbox("LPU ATRIBUÍDA", ["LPU Padrão", "DELIVERY", "LPU - MEI", "LPU DELIVERY - MEI"])
                    
                    if st.form_submit_button("CADASTRAR NOVO USUÁRIO", use_container_width=True):
                        if not c_nome or not c_cpf or not c_senha:
                            st.error("⚠️ Preencha os campos obrigatórios (Nome, CPF e Senha).")
                        else:
                            try:
                                data_formatada_banco = None
                                if c_nascimento and str(c_nascimento).strip() != "":
                                    c_nascimento_limpo = str(c_nascimento).strip()
                                    if "/" in c_nascimento_limpo:
                                        partes = c_nascimento_limpo.split("/")
                                        if len(partes) == 3:
                                            dia, mes, ano = partes
                                            if len(ano) == 4:
                                                data_formatada_banco = f"{ano}-{mes}-{dia}"
                                    else:
                                        data_formatada_banco = c_nascimento_limpo

                                telegram_val = None
                                if c_telegram and str(c_telegram).strip() != "":
                                    try:
                                        telegram_val = int(str(c_telegram).strip())
                                    except ValueError:
                                        pass

                                existe = supabase.table("TECNICOS").select("cpf").eq("cpf", c_cpf).execute()
                                if existe.data:
                                    st.error("⚠️ Este CPF já está cadastrado!")
                                else:
                                    payload_novo_usuario = {
                                        "nome": c_nome.upper(), 
                                        "cpf": str(c_cpf).strip(), 
                                        "email": str(c_email).strip() if c_email else None, 
                                        "telefone": str(c_telefone).strip() if c_telefone else None, 
                                        "telegram_chat_id": telegram_val,
                                        "data_nascimento": data_formatada_banco if data_formatada_banco else None,
                                        "senha": str(c_senha).strip(), 
                                        "perfil": str(c_perfil),
                                        "lpu_atribuida": str(c_lpu),
                                        "ativo": True,
                                        "primeiro_acesso": True if c_senha == "123456" else False
                                    }

                                    supabase.table("TECNICOS").insert(payload_novo_usuario).execute()
                                    st.success(f"Usuário {c_nome.upper()} cadastrado com sucesso!")
                            except Exception as e:
                                st.error(f"Erro ao cadastrar: {e}")

            elif opcao_admin == "Tabela LPU":
                st.write("GERENCIAMENTO DA LPU - FIELD")
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
                        disabled=["id", "created_at"],
                        key="editor_tabela_lpu_field"
                    )

                    if st.button("SALVAR LPU", use_container_width=True, key="btn_salvar_lpu_field"):
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
                                    "servico": str(servico_val).upper(),
                                    "valor": float(valor_val) if pd.notnull(valor_val) else 0.0,
                                    "descricao": str(descricao_val).upper() if pd.notnull(descricao_val) and descricao_val is not None else None,
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

            elif opcao_admin == "Tabela LPU Delivery":
                st.write("### GERENCIAMENTO DA LPU - DELIVERY")
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
                        disabled=["id", "created_at"],
                        key="editor_tabela_lpu_delivery"
                    )

                    if st.button("SALVAR LPU DELIVERY", use_container_width=True, key="btn_salvar_lpu_delivery"):
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
                                    "servico": str(servico_val).upper(),
                                    "valor": float(valor_val) if pd.notnull(valor_val) else 0.0,
                                    "descricao": str(descricao_val).upper() if pd.notnull(descricao_val) and descricao_val is not None else None,
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

            elif opcao_admin == "Tabela LPU - MEI":
                st.write("### GERENCIAMENTO DA LPU - MEI")
                try:
                    dados_lpu_mei = supabase.table("LPU_MEI").select("*").execute()
                    
                    if not dados_lpu_mei.data:
                        df_lpu_mei = pd.DataFrame(columns=["id", "created_at", "servico", "valor", "descricao", "min_metragem", "max_metragem"])
                    else:
                        df_lpu_mei = pd.DataFrame(dados_lpu_mei.data)
                    
                    configuracao_colunas_mei = {
                        "id": None,
                        "created_at": None,
                        "servico": st.column_config.TextColumn("Serviço", required=True),
                        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0),
                        "descricao": st.column_config.TextColumn("Descrição"),
                        "min_metragem": st.column_config.NumberColumn("Mín Metragem", min_value=0.0),
                        "max_metragem": st.column_config.NumberColumn("Máx Metragem", min_value=0.0)
                    }
                    
                    df_editada_lpu_mei = st.data_editor(
                        df_lpu_mei, 
                        use_container_width=True, 
                        num_rows="dynamic",
                        column_config=configuracao_colunas_mei,
                        disabled=["id", "created_at"],
                        key="editor_tabela_lpu_mei"
                    )

                    if st.button("SALVAR LPU - MEI", use_container_width=True, key="btn_salvar_lpu_mei"):
                        with st.spinner("Salvando..."):
                            for index, row in df_editada_lpu_mei.iterrows():
                                servico_val = row.get("servico")
                                valor_val = row.get("valor")
                                
                                if not servico_val or pd.isna(servico_val):
                                    continue
                                    
                                id_val = row.get("id")
                                descricao_val = row.get("descricao")
                                min_m_val = row.get("min_metragem")
                                max_m_val = row.get("max_metragem")
                                
                                dados_para_salvar = {
                                    "servico": str(servico_val).upper(),
                                    "valor": float(valor_val) if pd.notnull(valor_val) else 0.0,
                                    "descricao": str(descricao_val).upper() if pd.notnull(descricao_val) and descricao_val is not None else None,
                                    "min_metragem": float(min_m_val) if pd.notnull(min_m_val) and min_m_val is not None else None,
                                    "max_metragem": float(max_m_val) if pd.notnull(max_m_val) and max_m_val is not None else None
                                }
                                
                                if id_val is not None and pd.notnull(id_val) and str(id_val).strip() != "":
                                    supabase.table("LPU_MEI").update(dados_para_salvar).eq("id", id_val).execute()
                                else:
                                    supabase.table("LPU_MEI").insert(dados_para_salvar).execute()
                                    
                            st.success("Tabela LPU - MEI atualizada com sucesso!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao acessar tabela LPU_MEI: {e}")

            elif opcao_admin == "Tabela LPU Delivery - MEI":
                st.write("### GERENCIAMENTO DA LPU DELIVERY - MEI")
                try:
                    dados_lpu_deliv_mei = supabase.table("LPU_DELIVERY_MEI").select("*").execute()
                    
                    if not dados_lpu_deliv_mei.data:
                        df_lpu_deliv_mei = pd.DataFrame(columns=["id", "created_at", "servico", "valor", "descricao", "min_metragem", "max_metragem"])
                    else:
                        df_lpu_deliv_mei = pd.DataFrame(dados_lpu_deliv_mei.data)
                    
                    configuracao_colunas_deliv_mei = {
                        "id": None,
                        "created_at": None,
                        "servico": st.column_config.TextColumn("Serviço", required=True),
                        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0),
                        "descricao": st.column_config.TextColumn("Descrição"),
                        "min_metragem": st.column_config.NumberColumn("Mín Metragem", min_value=0.0),
                        "max_metragem": st.column_config.NumberColumn("Máx Metragem", min_value=0.0)
                    }
                    
                    df_editada_lpu_deliv_mei = st.data_editor(
                        df_lpu_deliv_mei, 
                        use_container_width=True, 
                        num_rows="dynamic",
                        column_config=configuracao_colunas_deliv_mei,
                        disabled=["id", "created_at"],
                        key="editor_tabela_lpu_delivery_mei"
                    )

                    if st.button("SALVAR LPU DELIVERY - MEI", use_container_width=True, key="btn_salvar_lpu_delivery_mei"):
                        with st.spinner("Salvando..."):
                            for index, row in df_editada_lpu_deliv_mei.iterrows():
                                servico_val = row.get("servico")
                                valor_val = row.get("valor")
                                
                                if not servico_val or pd.isna(servico_val):
                                    continue
                                    
                                id_val = row.get("id")
                                descricao_val = row.get("descricao")
                                min_m_val = row.get("min_metragem")
                                max_m_val = row.get("max_metragem")
                                
                                dados_para_salvar = {
                                    "servico": str(servico_val).upper(),
                                    "valor": float(valor_val) if pd.notnull(valor_val) else 0.0,
                                    "descricao": str(descricao_val).upper() if pd.notnull(descricao_val) and descricao_val is not None else None,
                                    "min_metragem": float(min_m_val) if pd.notnull(min_m_val) and min_m_val is not None else None,
                                    "max_metragem": float(max_m_val) if pd.notnull(max_m_val) and max_m_val is not None else None
                                }
                                
                                if id_val is not None and pd.notnull(id_val) and str(id_val).strip() != "":
                                    supabase.table("LPU_DELIVERY_MEI").update(dados_para_salvar).eq("id", id_val).execute()
                                else:
                                    supabase.table("LPU_DELIVERY_MEI").insert(dados_para_salvar).execute()
                                    
                            st.success("Tabela LPU DELIVERY - MEI atualizada com sucesso!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao acessar tabela LPU_DELIVERY_MEI: {e}")

            elif opcao_admin == "Cadastro de Equipamento":
                st.write("### GERENCIAMENTO DE CADASTRO DE EQUIPAMENTOS (CÓDIGO E DESCRIÇÃO)")
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
                        "descricao": st.column_config.TextColumn("Descrição", required=True)
                    }
                    
                    df_editada_cad_eq = st.data_editor(
                        df_cad_eq, 
                        use_container_width=True, 
                        num_rows="dynamic",
                        column_config=config_colunas_cad_eq,
                        disabled=["id", "created_at"],
                        key="editor_cadastro_equipamentos"
                    )

                    if st.button("SALVAR CADASTRO DE EQUIPAMENTOS", use_container_width=True, key="btn_salvar_cad_eq"):
                        with st.spinner("Salvando..."):
                            for index, row in df_editada_cad_eq.iterrows():
                                cod_val = row.get("codigo")
                                desc_val = row.get("descricao")
                                
                                if not cod_val or pd.isna(cod_val) or not desc_val or pd.isna(desc_val):
                                    continue
                                    
                                id_val = row.get("id")
                                
                                dados_para_salvar = {
                                    "codigo": str(cod_val).upper(),
                                    "descricao": str(desc_val).upper()
                                }
                                
                                if id_val is not None and pd.notnull(id_val) and str(id_val).strip() != "":
                                    supabase.table("CADASTRO_EQUIPAMENTOS").update(dados_para_salvar).eq("id", id_val).execute()
                                else:
                                    supabase.table("CADASTRO_EQUIPAMENTOS").insert(dados_para_salvar).execute()
                                    
                            st.success("Cadastro de Equipamentos atualizado com sucesso!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao acessar Cadastro de Equipamentos: {e}")

    if aba6 and perms_usuario.get("ve_colaborador", True):
        st.subheader("MÓDULO COLABORADOR")
        
        opcao_colaborador = sub_menu_colaborador if sub_menu_colaborador else "ATESTADO"
        
        if opcao_colaborador == "ATESTADO":
            st.markdown("### 📋 ENVIAR ATESTADO MÉDICO")
            
            with st.form("form_envio_atestado", clear_on_submit=True):
                col_at1, col_at2 = st.columns(2)
                with col_at1:
                    data_atestado = st.date_input("Data do Atestado", format="DD/MM/YYYY")
                    dias_afastamento = st.number_input("Dias de Afastamento", min_value=1, value=1, step=1)
                with col_at2:
                    motivo_atestado = st.text_input("Motivo / CID (Opcional)")
                    
                arquivo_atestado = st.file_uploader("Anexar Atestado (PDF, JPG, PNG)", type=['pdf', 'jpg', 'png', 'jpeg'])
                obs_atestado = st.text_area("Observações Adicionais")
                
                if st.form_submit_button("ENVIAR ATESTADO", use_container_width=True):
                    if not arquivo_atestado:
                        st.error("⚠️ Por favor, anexe o arquivo do atestado.")
                    else:
                        try:
                            timestamp = int(time.time())
                            caminho_atestado = f"atestados/{st.session_state.cpf_tecnico}_{timestamp}_{arquivo_atestado.name}"
                            
                            supabase.storage.from_("fotos_atendimentos").upload(caminho_atestado, arquivo_atestado.getvalue())
                            
                            supabase.table("ATESTADOS").insert({
                                "cpf_tecnico": st.session_state.cpf_tecnico,
                                "nome_tecnico": st.session_state.nome_tecnico,
                                "data_atestado": str(data_atestado),
                                "dias_afastamento": int(dias_afastamento),
                                "motivo": motivo_atestado.upper() if motivo_atestado else None,
                                "observacao": obs_atestado.upper() if obs_atestado else None,
                                "arquivo_url": caminho_atestado
                            }).execute()
                            
                            st.success("Atestado enviado com sucesso!")
                        except Exception as e:
                            st.error(f"Erro ao enviar atestado: {e}")

        elif opcao_colaborador == "CONTRA CHEQUE":
            st.markdown("### 💵 CONTRA CHEQUES / HOLERITES")
            st.info("Aqui você pode visualizar seus comprovantes de pagamento e holerites emitidos.")
            
            try:
                res_holerites = supabase.table("HOLERITES").select("*").eq("cpf_tecnico", st.session_state.cpf_tecnico).order("referencia", desc=True).execute()
                
                if res_holerites.data:
                    for item in res_holerites.data:
                        col_h1, col_h2 = st.columns([3, 1])
                        with col_h1:
                            st.write(f"**Referência:** {item.get('referencia', 'N/A')}")
                            st.caption(f"Descrição: {item.get('descricao', 'Holerite Mensal')}")
                        with col_h2:
                            caminho_file = item.get('arquivo_url')
                            if caminho_file:
                                try:
                                    file_bytes = supabase.storage.from_("fotos_atendimentos").download(caminho_file)
                                    st.download_button(
                                        label="📥 Baixar PDF",
                                        data=file_bytes,
                                        file_name=f"Holerite_{item.get('referencia', 'documento')}.pdf",
                                        mime="application/pdf",
                                        key=f"btn_hol_{item.get('id')}"
                                    )
                                except Exception:
                                    st.error("Erro ao baixar.")
                        st.divider()
                else:
                    st.info("Nenhum contra-cheque disponível no momento.")
            except Exception as e:
                st.info("Seus contra-cheques estarão disponíveis em breve nesta seção.")
