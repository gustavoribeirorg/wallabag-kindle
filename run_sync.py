import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from bs4 import BeautifulSoup
import base64
from urllib.parse import urljoin

# --- CONFIGURAÇÕES - CARREGADAS DAS VARIÁVEIS DE AMBIENTE DO RENDER ---
WALLABAG_URL = os.getenv('WALLABAG_URL')
WALLABAG_CLIENT_ID = os.getenv('WALLABAG_CLIENT_ID')
WALLABAG_CLIENT_SECRET = os.getenv('WALLABAG_CLIENT_SECRET')
WALLABAG_USERNAME = os.getenv('WALLABAG_USERNAME')
WALLABAG_PASSWORD = os.getenv('WALLABAG_PASSWORD')
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
KINDLE_EMAIL = os.getenv('KINDLE_EMAIL')

# --- FUNÇÕES (COPIE SUAS FUNÇÕES EXISTENTES AQUI SEM ALTERAÇÃO) ---
def get_wallabag_token():
    """Obtém o token de acesso da API do Wallabag."""
    # (código da função)
    token_url = f"{WALLABAG_URL}/oauth/v2/token"
    payload = {'grant_type': 'password','client_id': WALLABAG_CLIENT_ID,'client_secret': WALLABAG_CLIENT_SECRET,'username': WALLABAG_USERNAME,'password': WALLABAG_PASSWORD}
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        return response.json()['access_token']
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter token do Wallabag: {e}")
        return None

# (Cole aqui as outras funções: get_unread_articles, get_article_data, clean_html_content, send_to_kindle, mark_as_read)
def get_unread_articles(token):
    articles_url = f"{WALLABAG_URL}/api/entries.json"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'archive': 0, 'sort': 'created', 'order': 'desc'}
    try:
        response = requests.get(articles_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()['_embedded']['items']
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar artigos: {e}")
        return []

def get_article_data(token, article_id):
    article_url = f"{WALLABAG_URL}/api/entries/{article_id}.json"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(article_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados do artigo {article_id}: {e}")
        return None

def clean_html_content(html_content, title, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()
    for img_tag in soup.find_all('img'):
        img_url = img_tag.get('src')
        if not img_url: continue
        img_url = urljoin(base_url, img_url)
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            img_response = requests.get(img_url, headers=headers, timeout=15)
            img_response.raise_for_status()
            mime_type = img_response.headers.get('Content-Type', 'image/jpeg')
            img_data = img_response.content
            base64_data = base64.b64encode(img_data).decode('utf-8')
            img_tag['src'] = f"data:{mime_type};base64,{base64_data}"
        except requests.exceptions.RequestException as e:
            print(f"Erro ao baixar imagem {img_url}: {e}. Removendo tag.")
            img_tag.decompose()
    cleaned_body = soup.find('body')
    if not cleaned_body: cleaned_body = soup
    final_html = f"""<html><head><meta charset="UTF-8"><title>{title}</title></head><body><h1>{title}</h1>{cleaned_body.prettify()}</body></html>"""
    return final_html.encode('utf-8')

def send_to_kindle(cleaned_html, title):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = KINDLE_EMAIL
    msg['Subject'] = "Convert"
    filename = f"{title.replace(' ', '_').replace('/', '_')}.html"
    part = MIMEBase('text', 'html')
    part.set_payload(cleaned_html)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
    msg.attach(part)
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, KINDLE_EMAIL, msg.as_string())
        server.quit()
        print(f"Artigo '{title}' enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar e-mail para '{title}': {e}")

def mark_as_read(token, article_id):
    mark_url = f"{WALLABAG_URL}/api/entries/{article_id}.json"
    headers = {'Authorization': f'Bearer {token}'}
    payload = {'archive': 1}
    try:
        response = requests.patch(mark_url, headers=headers, data=payload)
        response.raise_for_status()
        print(f"Artigo {article_id} marcado como lido.")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao marcar o artigo {article_id} como lido: {e}")

# --- BLOCO PRINCIPAL DE EXECUÇÃO ---
if __name__ == '__main__':
    # Checagem para garantir que todas as variáveis foram carregadas
    if not all([WALLABAG_URL, WALLABAG_CLIENT_ID, WALLABAG_CLIENT_SECRET, WALLABAG_USERNAME, WALLABAG_PASSWORD, GMAIL_USER, GMAIL_APP_PASSWORD, KINDLE_EMAIL]):
        print("Erro: Uma ou mais variáveis de ambiente não foram definidas.")
        exit()

    print("Iniciando o script de envio para o Kindle...")
    token = get_wallabag_token()
    if token:
        articles = get_unread_articles(token)
        if not articles:
            print("Nenhum artigo não lido encontrado.")
        else:
            print(f"Encontrados {len(articles)} artigos não lidos.")
            for article in articles:
                # Lógica de processamento do artigo
                article_id = article['id']
                title = article['title']
                print(f"\nProcessando artigo: '{title}' (ID: {article_id})")
                article_data = get_article_data(token, article_id)
                if article_data and 'content' in article_data:
                    cleaned_html = clean_html_content(article_data['content'], title, WALLABAG_URL)
                    send_to_kindle(cleaned_html, title)
                    mark_as_read(token, article_id)
    print("\nScript finalizado.")