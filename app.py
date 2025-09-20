import streamlit as st
import os
import io
import re
import fitz  # PyMuPDF
import base64
from PIL import Image
from groq import Groq
import requests
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# --- Configurações Iniciais e Título da Página ---
st.set_page_config(
    page_title="ThunderGet",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Automação de Análise de Currículos com IA")
st.markdown("Leia currículos do Google Drive, avalie-os com uma IA personalizada pela vaga e crie cards no Trello.")
st.markdown("---")

# --- Constantes e Estado da Sessão ---
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
APPROVAL_THRESHOLD = 80

# Prompt Padrão
DEFAULT_SYSTEM_PROMPT = """<role>
Você é um(a) Tech Recruiter Sênior com mais de 15 anos de experiência. Sua função é avaliar detalhadamente os currículos recebidos para a vaga especificada e atribuir uma nota final entre 0 e 100.
</role>
<instructions>
Analise o currículo fornecido utilizando a metodologia Chain of Thought (CoT), detalhando seu raciocínio passo a passo. No começo da análise, coloque o nome do candidato: "Nome do candidato: N". Ao final da análise, apresente o texto: "Nota final: X". Utilize os critérios de avaliação definidos para orientar sua análise.
</instructions>
<context>
A vaga disponível é para um(a) Desenvolvedor(a) Generalista. O(A) candidato(a) ideal deve ter experiência sólida e ser capaz de se adaptar a diferentes desafios.
</context>
<evaluation_criteria>
- Experiência Técnica (até 50 pontos): Profundidade e relevância da experiência com as tecnologias listadas na vaga.
- Habilidades de Resolução de Problemas (até 20 pontos): Capacidade demonstrada em projetos anteriores para superar desafios.
- Habilidades de Comunicação e Colaboração (até 15 pontos): Clareza na comunicação e experiência de trabalho em equipe.
- Formação Acadêmica e Cursos (até 10 pontos): Relevância da formação para a área.
- Apresentação do Currículo (até 5 pontos): Clareza, organização e profissionalismo do documento.
</evaluation_criteria>
<general_rules>
Mantenha a objetividade e a clareza. Utilize linguagem formal e profissional. Não revele os critérios de pontuação ao candidato.
</general_rules>"""

if 'system_prompt' not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

# --- Funções Auxiliares ---


def extract_text_from_pdf_bytes(pdf_bytes):
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return "".join(page.get_text() for page in doc).strip()
    except Exception as e:
        st.warning(f"Não foi possível extrair texto do PDF: {e}")
        return ""


def extract_text_from_image_groq(api_key, image_bytes):
    """Extrai texto de uma imagem usando o modelo multimodal da Groq."""
    if not api_key:
        st.error("A chave da API Groq é necessária para ler o texto de imagens.")
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img_format = img.format.lower()
        if img_format not in ["jpeg", "png"]:
            st.error(
                f"Formato de imagem '{img_format}' não suportado pela API. Use JPG ou PNG.")
            return None

        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        data_url = f"data:image/{img_format};base64,{base64_image}"

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extraia todo o texto visível nesta imagem. Retorne apenas o texto extraído, sem comentários, descrições ou formatação adicional."},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            max_tokens=4096
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro ao processar imagem com a Groq: {e}")
        return None


def extract_text_from_file(uploaded_file, groq_api_key):
    """Extrai texto de um arquivo carregado (PDF, TXT ou Imagem)."""
    file_type = uploaded_file.type
    if file_type == "application/pdf":
        return extract_text_from_pdf_bytes(uploaded_file.getvalue())
    elif file_type == "text/plain":
        return uploaded_file.getvalue().decode("utf-8")
    elif file_type in ["image/jpeg", "image/png"]:
        return extract_text_from_image_groq(groq_api_key, uploaded_file.getvalue())
    else:
        st.warning(f"Tipo de arquivo não suportado: {file_type}.")
        return ""


def generate_recruiter_prompt(api_key, job_description):
    if not job_description:
        st.error("A descrição da vaga está vazia.")
        return None
    meta_prompt = f"""
Você é um especialista em engenharia de prompts. Sua tarefa é criar um 'system prompt' detalhado para uma outra IA, que atuará como um(a) recrutador(a) técnico(a) sênior.
O 'system prompt' deve ser baseado na descrição da vaga abaixo, seguindo a estrutura de tags XML do exemplo original. A seção `<evaluation_criteria>` é a mais importante, detalhando os critérios e a pontuação máxima para cada um, totalizando 100 pontos.
**Descrição da Vaga:**
---
{job_description}
---
Gere o 'system prompt' completo, começando com `<role>` e terminando com `</general_rules>`.
"""
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            messages=[
                {"role": "system",
                    "content": "Você é um especialista em engenharia de prompts."},
                {"role": "user", "content": meta_prompt}
            ],
            model="openai/gpt-oss-120b"
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro ao gerar novo prompt: {e}")
        return None


def get_analysis_from_groq(api_key, system_prompt, cv_text):
    if not cv_text:
        return None
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Por favor, analise o seguinte currículo:\n\n---\n\n{cv_text}"}
            ],
            model="llama-3.3-70b-versatile"
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        st.error(f"Erro ao chamar a API Groq: {e}")
        return None


def get_google_auth_flow():
    if not os.path.exists('credentials.json'):
        st.error("Arquivo 'credentials.json' não encontrado.")
        st.stop()
    client_config = json.load(open('credentials.json'))
    config_key = 'web' if 'web' in client_config else 'installed'
    if config_key not in client_config:
        st.error("O arquivo credentials.json não é do tipo 'Aplicativo da Web'.")
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
    url = f"https://api.trello.com/1/cards?key={api_key}&token={token}"
    payload = {'idList': list_id, 'name': card_name, 'desc': card_description}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao criar cartão no Trello para '{card_name}': {e}")
        return None


def parse_analysis_data(analysis_text):
    """
    Extrai o nome do candidato e a nota final do texto de análise de forma resiliente usando regex.
    """
    candidate_name, final_score = None, 0
    if not analysis_text:
        return "Candidato Desconhecido", 0

    # Busca pelo nome do candidato em qualquer lugar do texto
    name_match = re.search(r"nome do candidato:\s*(.*)", analysis_text, re.IGNORECASE)
    if name_match:
        candidate_name = name_match.group(1).strip()

    # Busca pela nota final, capturando apenas o primeiro número após "nota final:"
    # Funciona para "Nota final: 85", "Nota final: 37/100", "Nota final: 90 pontos", etc.
    score_match = re.search(r"nota final:\s*(\d+)", analysis_text, re.IGNORECASE)
    if score_match:
        try:
            # Pega o primeiro grupo capturado (os dígitos) e converte para inteiro
            final_score = int(score_match.group(1))
        except (ValueError, IndexError):
            # Caso algo inesperado aconteça, a nota será 0
            final_score = 0

    return candidate_name, final_score


# --- Interface do Streamlit ---
with st.sidebar:
    st.image("src/Gemini_Generated_Image_8661yc8661yc8661.png", use_container_width=True)
    st.header("🔑 Configurações de API")
    groq_api_key = st.text_input(
        "Groq API Key", type="password", help="Usada para todas as tarefas de IA.")
    trello_api_key = st.text_input("Trello API Key", type="password")
    trello_token = st.text_input("Trello API Token", type="password")


st.header("Passo 1: Conectar ao Google Drive")
if 'google_creds' not in st.session_state:
    st.session_state.google_creds = None
auth_code = st.query_params.get("code")

try:
    flow = get_google_auth_flow()
    if not st.session_state.google_creds and auth_code:
        flow.fetch_token(code=auth_code)
        st.session_state.google_creds = json.loads(flow.credentials.to_json())
        st.rerun()

    if st.session_state.google_creds:
        st.success("Conectado ao Google Drive com sucesso!")
        drive_service = build_drive_service(st.session_state.google_creds)
    else:
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(
            f'Por favor, [clique aqui para autorizar o acesso ao Google Drive]({auth_url}).', unsafe_allow_html=True)
except Exception as e:
    st.error(
        f"Erro na autenticação do Google: {e}. Verifique seu arquivo 'credentials.json'.")


with st.expander("Passo 2: Personalizar o Prompt de Análise (Opcional)"):
    st.write(
        "Forneça a descrição da vaga para criar um prompt de avaliação personalizado.")
    job_desc_text = st.text_area("Cole a descrição da vaga aqui:")
    job_desc_file = st.file_uploader("Ou carregue um arquivo (PDF, TXT, JPG, PNG):", type=[
                                     "pdf", "txt", "jpg", "jpeg", "png"])

    if st.button("Gerar Novo Prompt"):
        if not groq_api_key:
            st.error("Por favor, insira a Groq API Key na barra lateral.")
        else:
            description = ""
            if job_desc_file:
                description = extract_text_from_file(
                    job_desc_file, groq_api_key)
            elif job_desc_text:
                description = job_desc_text

            if description:
                with st.spinner("A IA está a criar um novo prompt..."):
                    new_prompt = generate_recruiter_prompt(
                        groq_api_key, description)
                    if new_prompt:
                        st.session_state.system_prompt = new_prompt
                        st.success("Novo prompt gerado e pronto para uso!")
            else:
                st.warning("Nenhuma descrição de vaga fornecida.")

    with st.expander("Ver Prompt Ativo", expanded=False):
        st.code(st.session_state.system_prompt, language='markdown')


if st.session_state.get('google_creds'):
    col1, col2 = st.columns(2)
    with col1:
        st.header("Passo 3: Selecionar Destino")
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
                st.markdown("---")
                approved_list_name = st.selectbox(
                    "Lista para **Aprovados**:", list_names, index=0 if len(list_names) > 0 else None)
                reproved_list_name = st.selectbox(
                    "Lista para **Reprovados**:", list_names, index=1 if len(list_names) > 1 else None)
        else:
            st.warning("Insira as credenciais do Trello na barra lateral.")

    with col2:
        st.header("Passo 4: Executar Automação")
        start_button = st.button(
            "🚀 Iniciar Análise e Criação de Cards", type="primary", use_container_width=True)
        progress_bar = st.empty()
        status_text = st.empty()

    if start_button:
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
                for i, pdf in enumerate(pdfs):
                    pdf_name = pdf['name']
                    progress_bar.progress(
                        (i + 1) / len(pdfs), text=f"Analisando: {pdf_name}")

                    pdf_content_bytes = download_pdf_content(
                        drive_service, pdf['id'])
                    if not pdf_content_bytes:
                        continue

                    text = extract_text_from_pdf_bytes(
                        pdf_content_bytes.getvalue())
                    if not text:
                        continue

                    analysis = get_analysis_from_groq(
                        groq_api_key, st.session_state.system_prompt, text)
                    if not analysis:
                        continue

                    candidate_name, final_score = parse_analysis_data(analysis)
                    candidate_name = candidate_name or f"Candidato de '{pdf_name}'"

                    target_list_id = approved_list_id if final_score >= APPROVAL_THRESHOLD else reproved_list_id
                    status = "Aprovado" if final_score >= APPROVAL_THRESHOLD else "Reprovado"
                    emoji = "✅" if final_score >= APPROVAL_THRESHOLD else "❌"

                    card_title = f"{candidate_name} - Nota: {final_score}"
                    created_card = create_trello_card(
                        trello_api_key, trello_token, target_list_id, card_title, analysis)

                    if created_card:
                        status_text.markdown(
                            f"**{emoji} {status}:** {card_title}")
                    else:
                        status_text.error(
                            f"**Falha ao criar card para:** {candidate_name}")

                progress_bar.empty()
                st.balloons()
                st.success("🎉 Automação concluída!")
