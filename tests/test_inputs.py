import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Adiciona src ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import process_input

# --- TESTE 1: TEXTO BRUTO ---
def test_input_raw_text():
    """Testa se o sistema reconhece e retorna texto simples."""
    texto = "Este é apenas um texto bruto de teste."
    # Se não é URL nem arquivo, deve retornar o próprio texto
    resultado = process_input(texto)
    assert resultado == texto

# --- TESTE 2: URL (Simulado/Mockado) ---
@patch('src.utils.requests.get')
def test_input_url(mock_get):
    """
    Testa o processamento de URL simulando uma resposta da internet.
    Não faz requisição real para não quebrar sem internet.
    """
    # 1. Configuramos o "falso" site
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Simula um HTML com texto suficiente para passar no Hardening (>50 chars)
    texto_longo = "Conteudo do Artigo Cientifico " * 5  # Multiplica para ficar longo
    mock_response.content = f"<html><body><p>{texto_longo}</p></body></html>".encode('utf-8')
    mock_get.return_value = mock_response

    # 2. Chamamos a função com uma URL fake
    url = "http://site-teste.com/artigo"
    resultado = process_input(url)

    # 3. Verificamos se ele limpou o HTML e pegou o texto
    assert "Conteudo do Artigo Cientifico" in resultado
    # Verifica se o requests.get foi chamado corretamente
    mock_get.assert_called_with(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)

# --- TESTE 3: PDF (Simulado/Mockado) ---
@patch('src.utils.PdfReader')
def test_input_pdf_mock(mock_pdf_reader):
    """
    Testa a extração de PDF simulando a biblioteca pypdf.
    Isso evita precisar de um arquivo .pdf real na pasta do teste.
    """
    # 1. Criamos uma "falsa" página de PDF
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Texto extraido do PDF."
    
    # 2. Configuramos o leitor para retornar essa página
    mock_pdf_reader.return_value.pages = [mock_page]

    # 3. Criamos um arquivo dummy (vazio) só para o os.path.exists passar
    dummy_filename = "teste_fake.pdf"
    with open(dummy_filename, "w") as f:
        f.write("dummy")
    
    try:
        # 4. Executa
        resultado = process_input(dummy_filename)
        assert "Texto extraido do PDF" in resultado
    finally:
        # 5. Limpeza: remove o arquivo fake
        if os.path.exists(dummy_filename):
            os.remove(dummy_filename)

# --- TESTE 4: PDF REAL (Integração) ---
def test_integration_sample_pdf():
    """
    Verifica se conseguimos ler um dos samples reais do projeto, se existirem.
    Isso garante que a biblioteca pypdf está instalada e funcionando de verdade.
    """
    sample_path = "samples/input_article_1.pdf"
    
    # Só roda este teste se você tiver criado o sample (como sugerimos antes)
    if os.path.exists(sample_path):
        print(f"Testando leitura real de: {sample_path}")
        resultado = process_input(sample_path)
        # O resultado não pode ser vazio e deve ser string
        assert isinstance(resultado, str)
        assert len(resultado) > 100 
    else:
        pytest.skip(f"Sample {sample_path} não encontrado, pulando teste de integração.")