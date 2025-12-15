import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, ConnectionError

# Adiciona src ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import process_input

# --- TESTE 1: PDF VAZIO OU ILEGÍVEL ---
@patch('src.utils.PdfReader')
def test_pdf_extraction_empty(mock_pdf_reader):
    """
    Simula um PDF que abre, mas não tem texto (ex: imagem escaneada sem OCR).
    O sistema deve recusar processar para não gastar tokens à toa.
    """
    # Simula página vazia
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "" # Retorna nada
    mock_pdf_reader.return_value.pages = [mock_page]

    # Cria arquivo dummy
    with open("temp_empty.pdf", "w") as f: f.write("dummy")

    try:
        with pytest.raises(ValueError) as excinfo:
            process_input("temp_empty.pdf")
        
        # Verifica se a mensagem de erro é informativa
        assert "PDF ilegível" in str(excinfo.value) or "muito curto" in str(excinfo.value)
    finally:
        os.remove("temp_empty.pdf")

# --- TESTE 2: TIMEOUT DE URL ---
@patch('src.utils.requests.get')
def test_url_timeout(mock_get):
    """Simula um site que demora demais para responder."""
    mock_get.side_effect = Timeout("O servidor demorou demais")

    with pytest.raises(ValueError) as excinfo:
        process_input("http://site-lento.com/artigo")
    
    # CORREÇÃO: Verifica se "Erro" E "URL" estão na mensagem (mais flexível)
    assert "Erro" in str(excinfo.value) and "URL" in str(excinfo.value)

# --- TESTE 3: ERRO 404 (Link Quebrado) ---
@patch('src.utils.requests.get')
def test_url_404(mock_get):
    """Simula link que não existe."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("404 Client Error")
    mock_get.return_value = mock_response

    with pytest.raises(ValueError) as excinfo:
        process_input("http://site-inexistente.com/nada")
    
    assert "Erro" in str(excinfo.value) and "URL" in str(excinfo.value)

# --- TESTE 4: INPUT LIXO (GIGO - Garbage In, Garbage Out) ---
def test_input_garbage():
    """
    Simula usuário enviando texto aleatório curto.
    O sistema deve barrar na entrada.
    """
    garbage_input = "   ...   "
    
    with pytest.raises(ValueError) as excinfo:
        process_input(garbage_input)
    
    # O validador deve pegar antes de chamar qualquer IA
    assert "muito curto" in str(excinfo.value)