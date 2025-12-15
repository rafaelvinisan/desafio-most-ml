import os
import json
import re
import requests
import tempfile
from bs4 import BeautifulSoup
from pypdf import PdfReader
from typing import Any, Dict, Optional

# --- FUNÇÕES DE LEITURA (IO) ---

def read_pdf(file_path: str) -> str:
    """Extrai texto de um arquivo PDF local."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract:
                text += extract + "\n"
        
        if len(text.strip()) < 10: 
            raise ValueError("PDF ilegível ou vazio (sem OCR detectado).")
            
        return text
    except Exception as e:
        if "PDF ilegível" in str(e): raise e
        raise ValueError(f"Erro crítico ao ler PDF: {e}")

def read_remote_pdf(url: str) -> str:
    """Baixa um PDF da web, salva em temp e extrai o texto."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        print(f"  > 📥 Baixando PDF remoto: {url}...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(response.content)
            temp_path = temp_pdf.name
            
        # Lê usando a função existente
        try:
            text = read_pdf(temp_path)
        finally:
            # Garante que apaga o arquivo temporário
            os.remove(temp_path)
            
        return text
    except Exception as e:
        raise ValueError(f"Erro ao processar PDF remoto: {e}")

def read_url(url: str) -> str:
    """Baixa e extrai texto de página HTML."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.extract()
            
        content_tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'article', 'section'])
        text_clean = "\n\n".join([tag.get_text().strip() for tag in content_tags if len(tag.get_text().strip()) > 20])

        if len(text_clean) < 100:
             text_clean = soup.get_text()
             lines = (line.strip() for line in text_clean.splitlines())
             text_clean = '\n'.join(chunk for chunk in lines if chunk)

        if len(text_clean) < 100:
             raise ValueError("URL retornou pouco conteúdo útil.")
        
        return text_clean
    except Exception as e:
        raise ValueError(f"Erro URL HTML: {e}")

def process_input(source: str) -> str:
    """Identifica o tipo de entrada e retorna texto validado."""
    source = source.strip()
    
    # 1. URL de PDF (NOVO CASO)
    if source.lower().startswith("http") and source.lower().endswith(".pdf"):
        return read_remote_pdf(source)

    # 2. URL HTML
    if source.startswith("http://") or source.startswith("https://"):
        return read_url(source)
    
    # 3. Arquivo PDF Local
    if source.lower().endswith(".pdf"):
        if os.path.exists(source):
            return read_pdf(source)
        else:
            raise ValueError(f"Arquivo PDF não encontrado: {source}")

    # 4. Arquivo Texto Local
    if os.path.exists(source):
        try:
            with open(source, 'r', encoding='utf-8') as f: 
                content = f.read()
                if len(content.strip()) < 10: raise ValueError("Arquivo vazio.")
                return content
        except: pass

    # 5. Texto Bruto
    if len(source) < 20:
        raise ValueError("Texto muito curto/inválido.")
        
    return source

def clean_input_for_tool(input_data: Any) -> str:
    if isinstance(input_data, dict): return str(list(input_data.values())[0])
    return str(input_data).replace('{"query":', '').replace('}', '').replace('"', '').strip()

def extract_json_from_text(text: str) -> Optional[Dict]:
    if not text: return None
    
    # 1. Limpeza de Markdown
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # 2. Limpeza de Cabeçalhos/Rodapés (Chat)
    text = re.sub(r'^[^{]*', '', text) 
    text = re.sub(r'[^}]*$', '', text)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 3. Recuperação de erros comuns (vírgulas extras)
        try:
            # Remove vírgula antes de fechar chaves }
            text = re.sub(r',\s*}', '}', text)
            # Remove vírgula antes de fechar colchetes ]
            text = re.sub(r',\s*]', ']', text)
            return json.loads(text)
        except:
            return None