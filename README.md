# Sistema Multi-Agente Científico (RAG + MCP)

Este projeto implementa um sistema autônomo de análise científica utilizando uma arquitetura **Multi-Agente** orquestrada pelo **CrewAI**. O sistema é capaz de classificar a área científica, extrair dados estruturados e gerar resenhas críticas a partir de diversas fontes de entrada (PDF, URL ou Texto).

O diferencial técnico é o uso do **Model Context Protocol (MCP)** para desacoplar a camada de dados (Vector Store) da camada cognitiva, além de uma estratégia de **RAG Híbrido** para garantir precisão e mitigar alucinações.

---

## 🏗️ Arquitetura da Solução

O sistema resolve o desafio de equilibrar a criatividade do LLM com a precisão dos dados através de dois fluxos distintos (Hybrid Context Strategy):

### 1. Camada de Classificação (RAG / Vector Store)
* **Agente:** `Scientific Taxonomist` (Pesquisador).
* **Mecanismo:** Utiliza a ferramenta `search_articles` (via servidor MCP) para consultar o **Vector Store** (ChromaDB) populado com artigos de referência.
* **Lógica:** *"Few-Shot Retrieval"*. O agente busca artigos semanticamente similares na base para determinar a qual área (Computação, Medicina, Química) o novo input pertence. Isso evita a criação de categorias não permitidas (ex: "Física").

### 2. Camada de Extração (Direct Context)
* **Agente:** `Scientific Reviewer` (Analista).
* **Mecanismo:** Recebe a classificação do Pesquisador + o **texto original** do input injetado diretamente no prompt.
* **Lógica:** Garante que a extração (JSON) e a resenha sejam fiéis ao artigo *novo*, e não contaminadas pelos dados dos artigos de referência (evitando *Data Leakage*).

---

## 🛠️ Stack Tecnológico e Justificativas

Conforme solicitado, abaixo apresento a justificativa para a escolha da stack, priorizando flexibilidade, custo-benefício e robustez.

| Componente | Escolha | Justificativa Técnica |
| :--- | :--- | :--- |
| **Orquestração** | **CrewAI** | Diferente de frameworks puramente conversacionais (AutoGen) ou baseados em grafos complexos (LangGraph), o CrewAI oferece um padrão robusto de **Processos Sequenciais**. Isso garante determinismo no fluxo (Pesquisa → Extração), essencial para pipelines de produção. |
| **Vector Store** | **ChromaDB** | Banco vetorial nativo Python, open-source e com persistência em arquivo local. Elimina a necessidade de subir containers Docker pesados (como Weaviate/Milvus) apenas para a avaliação, facilitando o "One-Click Run". |
| **Protocolo** | **MCP** | O uso do *Model Context Protocol* padroniza a exposição das ferramentas (`search_articles`, `get_article_content`). Isso desacopla o Agente da implementação do banco: podemos trocar o ChromaDB por Pinecone no futuro sem alterar uma linha do código do Agente. |
| **LLM** | **Gemini Flash** | Em testes de carga comparativos, a família **Google Gemini 1.5/2.0 Flash** demonstrou limites de TPM (Tokens Por Minuto) e Janela de Contexto (1M tokens) superiores ao Llama 3 (Groq) no tier gratuito, permitindo processar PDFs inteiros sem cortes ou *Rate Limits* agressivos. |

---

## 🚀 Guia de Instalação e Execução

### Pré-requisitos
* Python 3.10+
* Gerenciador de pacotes `uv` (Recomendado) ou `pip`.
* Uma chave de API do Google AI Studio.

### 1. Configuração de Ambiente
Crie um arquivo `.env` na raiz do projeto:
```env
GEMINI_API_KEY=sua_chave_aqui
```

### 2. Setup Automático (Via Makefile)
Utilize o make para instalar dependências e indexar os artigos de referência (localizados em `data/pdfs/`).

```bash
# 1. Instala dependências
make setup

# 2. Processa os PDFs e popula o banco vetorial local (db/)
make index
```

### 3. Subindo o Servidor MCP (HTTP + SSE)

O servidor MCP agora roda como um **servidor HTTP** com **Server-Sent Events (SSE)**.

Em um terminal separado, execute:

```bash
make mcp
```

Isso irá:
- **Subir um servidor Uvicorn** apontando para `src/mcp_server.py`.
- Expor o endpoint SSE em `http://localhost:8000/sse`.
- Expor o endpoint de mensagens em `http://localhost:8000/messages` (usado internamente pelo MCP).

Mantenha este terminal **aberto**, pois o agente/cliente se conecta a esse servidor.

## 📚 Como Usar (CLI)

O sistema possui uma CLI robusta em `src/agent.py` capaz de processar URLs, Arquivos PDF locais ou Texto Bruto.
Internamente, o agente se conecta ao servidor MCP via SSE usando o endpoint:

```text
MCP_SERVER_URL = "http://localhost:8000/sse"
```

Por isso, **certifique-se de que o comando `make mcp` está rodando em outro terminal** antes de executar o agente.

### 1. Execução via Makefile (Recomendado)

**Sintaxe (via `make agent`):**

```bash
make mcp                               # em um terminal separado
make agent SOURCE="FONTE" NAME="nome"  # em outro terminal
```

Onde:
- **`SOURCE`**: caminho de arquivo PDF, URL ou texto bruto.
- **`NAME`**: nome-base para os arquivos de saída em `out/` (sem extensão).

#### Exemplos com `make agent`

- **URL (Transformers no ArXiv)**:

```bash
make mcp
make agent SOURCE="https://arxiv.org/abs/1706.03762" NAME="analise_transformers"
```

- **PDF Local**:

```bash
make mcp
make agent SOURCE="samples/input_article_1.pdf" NAME="analise_local"
```

- **Texto Bruto**:

```bash
make mcp
make agent SOURCE="We propose a new network architecture..." NAME="teste_texto"
```

### 2. Execução direta via Python (Alternativa)

Você também pode chamar diretamente o script `src/agent.py`:

```bash
make mcp                              # em um terminal separado
uv run python src/agent.py [FONTE] --name [NOME_DO_OUTPUT]
```

Exemplos equivalentes:

```bash
# URL
make mcp
uv run python src/agent.py "https://arxiv.org/abs/1706.03762" --name analise_transformers

# PDF Local
make mcp
uv run python src/agent.py samples/input_article_1.pdf --name analise_local

# Texto Bruto
make mcp
uv run python src/agent.py "We propose a new network architecture..." --name teste_texto
```

## 📦 Saída e Resultados

Todos os resultados são salvos automaticamente na pasta `out/`. Para cada execução:

* **`{nome}.json`**: Dados estruturados.
  * Mantém o idioma original na extração (conforme edital).
  * Inclui a chave obrigatória com typo: `what problem does the artcle propose to solve?`.
* **`review_{nome}.md`**: Resenha crítica formatada em Português.

## 🛡️ Robustez e Hardening

O projeto implementa camadas de defesa ("Hardening") validadas por testes:

* **Validação de Input**: O sistema rejeita textos muito curtos ou PDFs corrompidos/vazios antes de chamar a API, economizando custos.
* **Rate Limiting Manual**: Implementação de `sleep` estratégico e `max_rpm` no CrewAI para respeitar as cotas estritas do tier gratuito do Gemini.
* **Parser JSON Resiliente**: Utiliza Regex para extrair e corrigir JSONs mal formatados pelo LLM (ex: vírgulas extras), garantindo que o pipeline não quebre por erros de sintaxe.
* **Tratamento de Erros**: Captura falhas de rede, timeouts do servidor MCP e erros de API com mensagens claras ao usuário.

## ✅ Testes Automatizados

O projeto inclui uma suíte de testes (`pytest`) cobrindo lógica de extração, limpeza de input e cenários de falha.

### 1. Testes gerais

```bash
make test
# Ou: uv run pytest tests/ -v
```

### 2. Cenários específicos do edital (atalhos via Makefile)

Cada cenário já está mapeado em um alvo `make`:

- **`make test1`** – PDF local de exemplo:

```bash
make mcp
make test1
```

- **`make test2`** – URL externa (ArXiv):

```bash
make mcp
make test2
```

- **`make test3`** – Edge case (Física Teórica / Schrodinger):

```bash
make mcp
make test3
```

## 📂 Estrutura do Projeto

```
.
├── data/pdfs/         # Artigos de referência (Base de Conhecimento)
├── db/                # Banco vetorial (ChromaDB - Gerado no setup)
├── out/               # Artefatos gerados (JSON e Markdown)
├── samples/           # Arquivos de exemplo para testes
├── src/
│   ├── agent.py       # Orquestração dos Agentes e CLI
│   ├── ingest.py      # Pipeline de Ingestão e Indexação
│   ├── mcp_server.py  # Servidor MCP (Ferramentas de Busca)
│   └── utils.py       # Parsers, Scrapers e Validadores (Testáveis)
├── tests/             # Testes Unitários e de Hardening
├── Makefile           # Automação de comandos
└── pyproject.toml     # Dependências
```
