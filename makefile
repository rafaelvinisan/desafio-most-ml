.PHONY: setup index mcp agent test clean test1 test2 test3

# Variáveis de Ambiente
PYTHON := uv run python
PYTEST := uv run pytest

# --- 1. COMANDOS DE SETUP E INFRA (Conforme Edital) ---

# "make setup"
setup:
	@echo "🔧 [SETUP] Instalando dependências..."
	uv sync
	@echo "✅ Setup concluído."

# "make index" - Constrói e popula o vector store
index:
	@echo "📚 [INDEX] Ingerindo PDFs e criando Vector Store..."
	$(PYTHON) src/ingest.py

# "make mcp" - Sobe o servidor MCP (Teste de sanidade)
# Nota: Como usamos stdio, isso vai iniciar e ficar aguardando input. 
# O avaliador deve usar Ctrl+C para sair.
mcp:
	@echo "📡 [MCP] Iniciando Servidor HTTP SSE na porta 8000..."
	@echo "ℹ️  Mantenha este terminal aberto."
	@echo "ℹ️  O servidor estará disponível em: http://localhost:8000/sse"
	@# O comando abaixo aponta para o arquivo src.mcp_server e o objeto app
	uv run uvicorn src.mcp_server:app --port 8000 --reload

# "make agent" - Inicia o cliente (Agente)
agent:
	@echo "🤖 [AGENT] Conectando ao Servidor MCP Local..."
	$(PYTHON) src/agent.py "$(SOURCE)" --name "$(NAME)"


# --- 2. ROTINAS DE TESTE (Cenários do Edital) ---

# Teste Geral (Unitários + Hardening)
test:
	@echo "🧪 [TEST] Executando bateria de testes automatizados..."
	$(PYTEST) tests/ -v

# Teste 1: PDF Local (Classificar e extrair)
# Requer que você tenha o arquivo samples/input_article_1.pdf
test1:
	@echo "📝 [TESTE 1] PDF Local (samples/input_article_1.pdf)"
	$(PYTHON) src/agent.py samples/input_article_1.pdf --name extraction_1

# Teste 2: URL (Artigo curto/Abstract)
test2:
	@echo "🌐 [TESTE 2] URL Externa (ArXiv)"
	$(PYTHON) src/agent.py "https://arxiv.org/abs/1706.03762" --name extraction_url_2

# Teste 3: Edge Case (Artigo fora das 3 áreas -> Schrodinger Physics)
test3:
	@echo "⚠️ [TESTE 3] Edge Case (Física Teórica)"
	$(PYTHON) src/agent.py samples/schrodinger-1935-cat.pdf --name extraction_edge_case

# --- 3. UTILITÁRIOS ---

clean:
	@echo "🧹 Limpando ambiente..."
	rm -rf db/chroma_data
	rm -rf out/*
	rm -rf __pycache__