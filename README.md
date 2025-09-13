# ThunderGet
Automação de Fluxo com Streamlit, Google Drive, Groq e Trello
Este projeto utiliza Streamlit para criar uma interface web que automatiza um fluxo de trabalho: ler PDFs do Google Drive, analisá-los com um modelo de linguagem da Groq e adicionar os resultados como comentários em cartões do Trello.

# ⚙️ Pré-requisitos
Antes de executar a aplicação, você precisará instalar as dependências Python necessárias.

## 1. Instalação de Pacotes
Crie um arquivo chamado requirements.txt com o seguinte conteúdo:

- streamlit
- google-api-python-client
- google-auth-httplib2
- google-auth-oauthlib
- PyMuPDF
- groq
- requests

Em seguida, instale os pacotes usando o pip:

pip install -r requirements.txt

## 2. Configuração das Credenciais
A aplicação requer credenciais para acessar as APIs do Google, Groq e Trello.

a. Google Drive API (credentials.json)
Acesse o Google Cloud Console.

Crie um novo projeto (ou use um existente).

No menu de navegação, vá para "APIs e Serviços" > "Biblioteca".

Procure por "Google Drive API" e ative-a.

Vá para "APIs e Serviços" > "Tela de consentimento OAuth".

Escolha "Externo" e crie a tela. Preencha o nome do aplicativo, e-mail de suporte e e-mail do desenvolvedor.

Nos escopos, não precisa adicionar nada.

Adicione usuários de teste (seu próprio e-mail do Google).

Vá para "APIs e Serviços" > "Credenciais".

Clique em "Criar Credenciais" > "ID do cliente OAuth".

Selecione "Aplicativo da Web" como tipo de aplicativo.

Dê um nome, por exemplo, "Streamlit Drive App".

Em URIs de redirecionamento autorizados, adicione o endereço onde sua aplicação Streamlit estará rodando. Para desenvolvimento local, adicione http://localhost:8501.

Clique em "Criar". Uma janela pop-up mostrará seu "ID do cliente" e "Chave secreta do cliente".

Clique em "FAZER O DOWNLOAD DO JSON". Renomeie o arquivo baixado para credentials.json e coloque-o na mesma pasta do seu script Python.

b. Groq API Key
Acesse o site da Groq e crie uma conta.

Navegue até a seção de chaves de API no seu painel de controle: https://console.groq.com/keys.

Crie uma nova chave secreta e copie-a.

c. Trello API Key e Token
Faça login na sua conta do Trello.

Acesse https://trello.com/app-key para obter sua API Key.

Na mesma página, você verá um link para gerar um Token. Clique nele, autorize o acesso, e o token será exibido. Copie-o.

## 🚀 Como Executar a Aplicação
Certifique-se de que os arquivos automacao_fluxo.py, credentials.json e requirements.txt estão no mesmo diretório.

Abra seu terminal ou prompt de comando.

Navegue até o diretório do projeto.

Execute o seguinte comando:

streamlit run app.py

A aplicação será aberta no seu navegador. Siga os passos na interface:

Insira suas chaves de API na barra lateral.

Clique no link para autorizar o acesso ao Google Drive e permita o acesso.

Selecione a pasta, o quadro, a lista e o cartão desejados.

Clique em "Iniciar Processamento" para executar a automação.