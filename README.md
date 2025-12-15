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

## 📚 Como Usar (CLI)

O sistema possui uma CLI robusta em `src/agent.py` capaz de processar URLs, Arquivos PDF locais ou Texto Bruto.

**Sintaxe:**
```bash
python src/agent.py [FONTE] --name [NOME_DO_OUTPUT]
```

### Cenário 1: Analisando uma URL (Recomendado)
O sistema baixa o HTML/PDF, limpa menus/scripts e processa o conteúdo.

```bash
# Exemplo: Artigo sobre Transformers no ArXiv
python src/agent.py "https://arxiv.org/abs/1706.03762" --name analise_transformers
```

### Cenário 2: Analisando um PDF Local
Utiliza `pypdf` com validação de OCR.

```bash
python src/agent.py samples/meu_artigo.pdf --name analise_local
```

### Cenário 3: Analisando Texto Bruto
Ideal para testes rápidos.

```bash
python src/agent.py "We propose a new network architecture..." --name teste_texto
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

```bash
make test
# Ou: uv run pytest tests/ -v
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
