import sys
import json
import re
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
import chromadb
from chromadb.utils import embedding_functions

# --- CONFIGURAÇÃO ---
DB_PATH = "./db/chroma_data"
COLLECTION_NAME = "scientific_articles"

# --- INICIALIZAÇÃO DO BANCO ---
try:
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_func)
    print(f"✅ [SERVER] ChromaDB carregado: {collection.count()} docs.", file=sys.stderr)
except Exception as e:
    print(f"⚠️ [SERVER] Erro ao carregar ChromaDB: {e}", file=sys.stderr)
    collection = None

def clean_text(text: str) -> str:
    if not text: return ""
    text = text.replace("<EOS>", "").replace("<pad>", "")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# --- DEFINIÇÃO DO SERVIDOR MCP ---
server = Server("scientific-knowledge-server")
sse = SseServerTransport("/messages") # Endpoint para POST

# 1. LISTAR FERRAMENTAS DISPONÍVEIS
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_articles",
            description="Search for articles by similarity. Returns Metadata and Snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search phrase"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_article_content",
            description="Get full content by ID. Returns JSON string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Article ID (e.g., 'doc_chunk_1')"}
                },
                "required": ["id"]
            }
        )
    ]

# 2. EXECUTAR FERRAMENTAS
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent | ImageContent | EmbeddedResource]:
    if not arguments:
        return [TextContent(type="text", text="Error: No arguments provided.")]
    
    if not collection:
        return [TextContent(type="text", text="Error: Database not initialized. Run 'make index'.")]

    # --- LÓGICA DA BUSCA ---
    if name == "search_articles":
        query = arguments.get("query", "")
        print(f"🔎 [SERVER] Buscando: '{query}'", file=sys.stderr)
        
        try:
            results = collection.query(query_texts=[query], n_results=5)
            if not results['ids'] or not results['ids'][0]:
                return [TextContent(type="text", text="No results found.")]

            resp = f"=== SEARCH RESULTS FOR: '{query}' ===\n"
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            ids = results['ids'][0]
            dists = results['distances'][0] if 'distances' in results else [0]*len(ids)
            
            for i, doc in enumerate(docs):
                score = 1 - dists[i]
                resp += f"\n--- RESULT {i+1} ---\n"
                resp += f"ID: {ids[i]}\n"
                resp += f"Area: {metas[i].get('area')}\n"
                resp += f"Source: {metas[i].get('source')}\n"
                resp += f"Score: {score:.4f}\n"
                resp += f"Snippet: {clean_text(doc)[:300]}...\n"
            
            return [TextContent(type="text", text=resp)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    # --- LÓGICA DA LEITURA ---
    elif name == "get_article_content":
        doc_id = arguments.get("id", "")
        print(f"📖 [SERVER] Lendo ID: '{doc_id}'", file=sys.stderr)
        
        try:
            result = collection.get(ids=[doc_id])
            if not result['documents']:
                return [TextContent(type="text", text="Error: ID not found.")]
            
            full_text = clean_text(result['documents'][0])
            meta = result['metadatas'][0]
            
            json_resp = json.dumps({
                "id": doc_id,
                "title": meta.get('source'),
                "area": meta.get('area'),
                "content": full_text
            }, ensure_ascii=False)
            
            return [TextContent(type="text", text=json_resp)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return [TextContent(type="text", text=f"Error: Tool {name} not found.")]

# --- ROTAS DO STARLETTE (O SERVIDOR WEB) ---

class SSEHandler:
    """Gerencia a conexão persistente SSE (Server-Sent Events)."""
    async def __call__(self, scope, receive, send):
        # Desempacota a tupla diretamente em (read, write)
        async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
            await server.run(
                read_stream, 
                write_stream, 
                server.create_initialization_options()
            )

class MessagesHandler:
    """Gerencia os comandos POST enviados pelo cliente."""
    async def __call__(self, scope, receive, send):
        await sse.handle_post_message(scope, receive, send)

# --- APLICAÇÃO STARLETTE ---
from starlette.applications import Starlette
from starlette.routing import Route

app = Starlette(routes=[
    Route("/sse", endpoint=SSEHandler()),
    Route("/messages", endpoint=MessagesHandler(), methods=["POST"])
])

if __name__ == "__main__":
    # Este bloco só roda se chamar direto o arquivo, mas o Makefile usa uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)