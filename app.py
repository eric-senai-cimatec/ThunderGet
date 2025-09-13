import streamlit as st
import os
import io
import fitz  # PyMuPDF
from groq import Groq
import requests
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# --- Configurações Iniciais e Título da Página ---
st.set_page_config(
    page_title="Automação de Recrutamento com IA",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Automação de Análise de Currículos com IA")
st.markdown("""
Esta aplicação lê currículos em PDF de uma pasta do Google Drive, utiliza a IA da Groq para
avaliá-los e cria um card para cada candidato na lista correta do Trello (Aprovados ou Reprovados).
""")
st.markdown("---")

# --- Constantes e Configurações de API ---
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
APPROVAL_THRESHOLD = 80  # Nota de corte para aprovação

# --- Funções Auxiliares para APIs ---

# 1. Funções do Google Drive (sem alterações)


def get_google_auth_flow():
    if not os.path.exists('credentials.json'):
        st.error(
            "Arquivo 'credentials.json' não encontrado. Por favor, faça o upload do arquivo.")
        st.stop()
    client_config = json.load(open('credentials.json'))
    config_key = 'web' if 'web' in client_config else 'installed'
    if config_key not in client_config:
        st.error("O arquivo credentials.json não é do tipo 'Aplicativo da Web'. Por favor, gere o arquivo correto no Google Cloud Console.")
        st.stop()
    redirect_uri = client_config[config_key]['redirect_uris'][0]
    return Flow.from_client_config(client_config=client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def build_drive_service(creds_json):
    try:
        creds = Credentials.from_authorized_user_info(creds_json, SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro ao construir o serviço do Drive: {e}")
        return None


def list_drive_folders(service):
    try:
        results = service.files().list(q="mimeType='application/vnd.google-apps.folder'",
                                       pageSize=100, fields="files(id, name)").execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"Não foi possível buscar as pastas: {e}")
        return []


def get_pdfs_from_folder(service, folder_id):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf'", pageSize=100, fields="files(id, name)").execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"Não foi possível buscar os PDFs da pasta: {e}")
        return []


def download_pdf_content(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        return io.BytesIO(request.execute())
    except Exception as e:
        st.error(f"Falha no download do PDF (ID: {file_id}): {e}")
        return None

# 2. Função de Extração de Texto (sem alterações)


def extract_text_from_pdf(pdf_content):
    try:
        with fitz.open(stream=pdf_content, filetype="pdf") as doc:
            return "".join(page.get_text() for page in doc).strip()
    except Exception as e:
        st.warning(f"Não foi possível extrair texto do PDF: {e}")
        return ""

# 3. Função da API Groq (sem alterações)


def get_analysis_from_groq(api_key, text):
    if not text:
        return None
    system_prompt = """<role>
Você é um(a) Tech Recruiter Sênior com mais de 15 anos de experiência, especializado(a) no recrutamento de talentos para as áreas de Inteligência Artificial e Ciência de Dados. Sua função é avaliar detalhadamente os currículos recebidos para a posição de ESPECIALISTA II - LLM/GENAI e atribuir uma nota final entre 0 e 100.
</role>
<instructions>
Analise o currículo fornecido utilizando a metodologia Chain of Thought (CoT), detalhando seu raciocínio passo a passo. No começo da análise, coloque o nome do candidato: "Nome do candidato: N", substituindo N pelo nome completo do candidato. Ao final da análise, apresente o texto: "Nota final: X", substituindo X pela nota atribuída. Utilize os critérios de avaliação definidos para orientar sua análise.
</instructions>
<context>
A vaga disponível é para ESPECIALISTA II - LLM/GENAI (Cientista de Dados Pleno). O(A) candidato(a) ideal deve ter experiência prática no desenvolvimento e implementação de soluções utilizando Large Language Models (LLMs) e Inteligência Artificial Generativa. Espera-se que o(a) profissional seja capaz de trabalhar em todo o ciclo de vida de projetos de GenAI, desde a prova de conceito até a produção, colaborando com equipes de engenharia de dados e produto para criar soluções inovadoras que gerem valor para o negócio.
</context>
<evaluation_criteria>
- Experiência Prática em LLM/GenAI (até 35 pontos): Profundidade e relevância da experiência com frameworks (e.g., LangChain, LlamaIndex), fine-tuning de modelos, técnicas de RAG (Retrieval-Augmented Generation), uso de APIs (OpenAI, Hugging Face) e familiaridade com Vector Stores.
- Fundamentos de Machine Learning e Ciência de Dados (até 20 pontos): Solidez dos conhecimentos em NLP tradicional, modelos preditivos (classificação, regressão), estatística e análise de dados com Python (Pandas, Scikit-learn).
- Engenharia e MLOps (até 20 pontos): Habilidade para colocar modelos em produção. Avaliar experiência com desenvolvimento de APIs (FastAPI, Flask), containerização (Docker), orquestração e uso de plataformas de nuvem (AWS SageMaker, GCP Vertex AI, Azure ML).
- Formação Acadêmica e Teórica (até 10 pontos): Nível e área de formação (Ciência da Computação, Engenharia, Estatística, etc.). Mestrado ou publicações na área são diferenciais.
- Habilidades de Negócio e Comunicação (até 10 pontos): Capacidade de traduzir problemas de negócio em soluções de IA, quantificar o impacto de projetos e comunicar resultados técnicos para stakeholders não-técnicos.
- Apresentação do Currículo (até 5 pontos): Clareza na descrição de projetos, organização, objetividade e profissionalismo do documento.
</evaluation_criteria>
<general_rules>
Mantenha a objetividade e a clareza em sua análise.
Utilize linguagem formal e profissional.
Não revele os critérios de pontuação ao candidato.
Respeite a confidencialidade das informações apresentadas.
Evite comentários pessoais, preconceituosos ou discriminatórios.
</general_rules>"""
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(messages=[{"role": "system", "content": system_prompt}, {
                                                         "role": "user", "content": f"Por favor, analise o seguinte currículo:\n\n---\n\n{text}"}], model="llama-3.3-70b-versatile")
        return chat_completion.choices[0].message.content
    except Exception as e:
        st.error(f"Erro ao chamar a API Groq: {e}")
        return None

# 4. Funções da API do Trello (ATUALIZADAS)


def get_trello_boards(api_key, token):
    url = f"https://api.trello.com/1/members/me/boards?key={api_key}&token={token}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar quadros do Trello: {e}")
        return []


def get_trello_lists(api_key, token, board_id):
    url = f"https://api.trello.com/1/boards/{board_id}/lists?key={api_key}&token={token}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar listas do Trello: {e}")
        return []


def create_trello_card(api_key, token, list_id, card_name, card_description):
    """Cria um novo cartão com descrição."""
    url = f"https://api.trello.com/1/cards?key={api_key}&token={token}"
    payload = {'idList': list_id, 'name': card_name, 'desc': card_description}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao criar cartão no Trello para '{card_name}': {e}")
        return None

# 5. Funções de Extração de Dados (ATUALIZADAS)


def parse_analysis_data(analysis_text):
    """Extrai o nome do candidato e a nota final do texto de análise."""
    candidate_name = None
    final_score = 0
    if not analysis_text:
        return "Candidato Desconhecido", 0

    for line in analysis_text.splitlines():
        line_lower = line.lower()
        if "nome do candidato:" in line_lower:
            candidate_name = line.split(":", 1)[1].strip()
        elif "nota final:" in line_lower:
            try:
                score_str = line.split(":", 1)[1].strip()
                final_score = int(score_str)
            except (ValueError, IndexError):
                final_score = 0  # Define 0 se não conseguir extrair
    return candidate_name, final_score


# --- Interface do Streamlit ---
with st.sidebar:
    st.header("🔑 Configurações de API")
    groq_api_key = st.text_input("Groq API Key", type="password")
    trello_api_key = st.text_input("Trello API Key", type="password")
    trello_token = st.text_input("Trello API Token", type="password")

st.header("1. Conexão com Google Drive")
if 'google_creds' not in st.session_state:
    st.session_state.google_creds = None
auth_code = st.query_params.get("code")
flow = get_google_auth_flow()

if not st.session_state.google_creds and auth_code:
    try:
        flow.fetch_token(code=auth_code)
        st.session_state.google_creds = json.loads(flow.credentials.to_json())
        st.rerun()
    except Exception as e:
        st.error(f"Falha ao obter o token de acesso: {e}")

if st.session_state.google_creds:
    st.success("Conectado ao Google Drive com sucesso!")
    drive_service = build_drive_service(st.session_state.google_creds)
else:
    auth_url, _ = flow.authorization_url(prompt='consent')
    st.markdown(
        f'Por favor, [clique aqui para autorizar o acesso ao Google Drive]({auth_url}) e retorne a esta aba.', unsafe_allow_html=True)

if st.session_state.google_creds:
    col1, col2 = st.columns(2)
    with col1:
        st.header("2. Seleção de Destino")
        folders = list_drive_folders(drive_service)
        folder_dict = {f['name']: f['id'] for f in folders}
        selected_folder_name = st.selectbox(
            "Selecione a pasta com os currículos:", folder_dict.keys())

        if trello_api_key and trello_token:
            boards = get_trello_boards(trello_api_key, trello_token)
            board_dict = {b['name']: b['id'] for b in boards}
            selected_board_name = st.selectbox(
                "Selecione um quadro do Trello:", board_dict.keys())

            if selected_board_name:
                board_id = board_dict[selected_board_name]
                lists = get_trello_lists(
                    trello_api_key, trello_token, board_id)
                list_names = [l['name'] for l in lists]
                list_dict = {l['name']: l['id'] for l in lists}

                # Seleção para Aprovados e Reprovados
                st.markdown("---")
                approved_list_name = st.selectbox(
                    "Selecione a lista para **Aprovados**:", list_names)
                reproved_list_name = st.selectbox(
                    "Selecione a lista para **Reprovados**:", list_names)
        else:
            st.warning("Insira as credenciais do Trello na barra lateral.")

    with col2:
        st.header("3. Executar Automação")
        start_button = st.button(
            "🚀 Iniciar Análise e Criação de Cards", type="primary", use_container_width=True)
        # Placeholder para o progresso
        progress_bar = st.empty()
        status_text = st.empty()

    if start_button:
        # Validação
        if not all([groq_api_key, trello_api_key, trello_token, selected_folder_name, 'approved_list_name' in locals()]):
            st.error(
                "ERRO: Preencha todas as chaves de API e selecione as pastas e listas de destino.")
        elif approved_list_name == reproved_list_name:
            st.error(
                "ERRO: A lista de Aprovados e Reprovados não pode ser a mesma.")
        else:
            folder_id = folder_dict[selected_folder_name]
            approved_list_id = list_dict[approved_list_name]
            reproved_list_id = list_dict[reproved_list_name]

            pdfs = get_pdfs_from_folder(drive_service, folder_id)
            if not pdfs:
                st.warning(
                    f"Nenhum PDF encontrado na pasta '{selected_folder_name}'.")
            else:
                total_files = len(pdfs)
                for i, pdf in enumerate(pdfs):
                    pdf_name = pdf['name']
                    # Atualiza a barra de progresso
                    progress_bar.progress(
                        (i + 1) / total_files, text=f"Analisando: {pdf_name}")

                    pdf_content = download_pdf_content(
                        drive_service, pdf['id'])
                    if not pdf_content:
                        continue

                    text = extract_text_from_pdf(pdf_content)
                    if not text:
                        continue

                    analysis = get_analysis_from_groq(groq_api_key, text)
                    if not analysis:
                        continue

                    candidate_name, final_score = parse_analysis_data(analysis)
                    candidate_name = candidate_name or f"Candidato de '{pdf_name}'"

                    # Lógica de decisão
                    if final_score >= APPROVAL_THRESHOLD:
                        target_list_id = approved_list_id
                        status = "Aprovado"
                        emoji = "✅"
                    else:
                        target_list_id = reproved_list_id
                        status = "Reprovado"
                        emoji = "❌"

                    # Cria o card com a análise na descrição
                    card_title = f"{candidate_name} - Nota: {final_score}"
                    created_card = create_trello_card(
                        trello_api_key, trello_token, target_list_id, card_title, analysis)

                    # Atualiza o status em linha única
                    if created_card:
                        status_text.markdown(
                            f"**{emoji} {status}:** {card_title}")
                    else:
                        status_text.error(
                            f"**Falha ao criar card para:** {candidate_name}")

                progress_bar.empty()
                st.balloons()
                st.success("🎉 Automação concluída!")
