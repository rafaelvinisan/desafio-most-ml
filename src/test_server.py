import sys
import os

# Setup de path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.mcp_server import search_articles

def test_manual():
    print("\n🚀 INICIANDO DIAGNÓSTICO DO SERVIDOR MCP\n")

    # TESTE: BUSCA (Agora retorna String formatada, não lista)
    print("--- Teste de Busca Semântica ---")
    try:
        # Busca algo que sabemos que existe no PDF 'transformers'
        query = "attention mechanism"
        print(f"🔎 Buscando por: '{query}'...")
        
        resultado = search_articles(query)
        
        print("\n📄 RETORNO DO SERVIDOR:")
        print("=" * 60)
        # Mostra os primeiros 500 caracteres para não poluir o terminal
        print(resultado[:500] + "\n... [continua] ...")
        print("=" * 60)

        if "No results" in resultado:
            print("⚠️  Aviso: Nenhum artigo encontrado.")
        elif "---" in resultado:
            print("✅ SUCESSO! O servidor retornou o contexto formatado.")
        else:
            print("⚠️  Retorno inesperado (verifique se o banco está vazio).")

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        print("Dica: Verifique se rodou 'python src/ingest.py' antes.")

if __name__ == "__main__":
    test_manual()