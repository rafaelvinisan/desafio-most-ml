import sys
import os
import json
import pytest

# Garante que o python enxergue a pasta src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import extract_json_from_text, clean_input_for_tool

# --- TESTES DE EXTRAÇÃO DE JSON (O Coração do Analista) ---

def test_json_simple():
    """Deve extrair um JSON simples e limpo."""
    entrada = '{"area": "Computacao"}'
    resultado = extract_json_from_text(entrada)
    assert resultado == {"area": "Computacao"}

def test_json_with_markdown():
    """Deve ignorar blocos de código Markdown."""
    entrada = """
    Aqui está o resultado:
    ```json
    {
        "area": "Medicina",
        "score": 10
    }
    ```
    """
    resultado = extract_json_from_text(entrada)
    assert resultado["area"] == "Medicina"
    assert resultado["score"] == 10

def test_json_dirty_text():
    """Deve encontrar JSON no meio de texto sujo."""
    entrada = "Eu pensei muito e conclui que: {\"chave\": \"valor\"} é a resposta."
    resultado = extract_json_from_text(entrada)
    assert resultado == {"chave": "valor"}

def test_json_incomplete_recovery():
    """Deve tentar recuperar JSON com vírgula sobrando (erro comum de LLM)."""
    # Note a vírgula depois de 'valor'
    entrada = '{"chave": "valor",}' 
    resultado = extract_json_from_text(entrada)
    assert resultado == {"chave": "valor"}

# --- TESTES DE LIMPEZA DE INPUT (Proteção do Researcher) ---

def test_clean_input_dict():
    """Deve extrair string de um dicionário acidental."""
    entrada = {"query": "busca real"}
    assert clean_input_for_tool(entrada) == "busca real"

def test_clean_input_nested_json():
    """Deve limpar string que parece JSON aninhado."""
    entrada = '{"query": "busca real"}'
    assert clean_input_for_tool(entrada) == "busca real"