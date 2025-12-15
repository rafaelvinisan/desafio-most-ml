import sys
import os
import asyncio
import json
import time
import argparse
from typing import Any
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from mcp import ClientSession
from dotenv import load_dotenv
from src.utils import process_input, extract_json_from_text, clean_input_for_tool
from mcp.client.sse import sse_client

load_dotenv()
MCP_SERVER_URL = "http://localhost:8000/sse"

if not os.getenv("GEMINI_API_KEY"):
    print("❌ ERRO: GEMINI_API_KEY não encontrada.")
    sys.exit(1)

# Modelo Estável
CURRENT_LLM = "gemini/gemini-2.5-flash-lite"

PYTHON_PATH = sys.executable
SERVER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), 'mcp_server.py'))

# --- TOOLS ---
class SearchArticlesTool(BaseTool):
    name: str = "Search Articles"
    description: str = "Search reference database via MCP Server."
    
    def _run(self, query: Any) -> str:
        clean_q = clean_input_for_tool(query)
        print(f"  > 🔍 [Tool: Search] Conectando ao servidor em {MCP_SERVER_URL}...")
        
        async def run_remote_mcp():
            try:
                # Conecta via HTTP (SSE)
                async with sse_client(MCP_SERVER_URL) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool("search_articles", arguments={"query": clean_q})
                        return str(result.content)
            except Exception as e:
                return f"❌ ERRO DE CONEXÃO: Não foi possível conectar ao servidor MCP em {MCP_SERVER_URL}. Verifique se rodou 'make mcp'."

        return asyncio.run(run_remote_mcp())

class GetContentTool(BaseTool):
    name: str = "Get Article Content"
    description: str = "Get full content via MCP Server."
    
    def _run(self, id: Any) -> str:
        clean_id = clean_input_for_tool(id)
        print(f"  > 📖 [Tool: GetContent] Solicitando ID: '{clean_id}'...")
        
        async def run_remote_mcp():
            try:
                async with sse_client(MCP_SERVER_URL) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool("get_article_content", arguments={"id": clean_id})
                        return str(result.content)
            except Exception as e:
                return f"❌ ERRO DE CONEXÃO: O servidor MCP está offline."

        return asyncio.run(run_remote_mcp())

search_tool = SearchArticlesTool()
content_tool = GetContentTool()

# --- AGENTES ---

researcher = Agent(
    role='Scientific Taxonomist',
    goal='Classify the article into one of the allowed categories.',
    backstory="""You are a strict classifier. 
    You MUST map any scientific topic into one of these three buckets: [Computacao, Medicina, Quimica].
    Even if the topic is Physics, Biology, or Mathematics, you MUST force it into the closest bucket above.""",
    tools=[search_tool, content_tool],
    verbose=True,
    memory=False,
    llm=CURRENT_LLM,
    max_iter=2,
    max_rpm=5
)

analyst = Agent(
    role='Scientific Extractor',
    goal='Extract data keeping original language and write review in Portuguese.',
    backstory="""You are a precise data analyst. 
    1. You extract technical details maintaining the SOURCE TEXT LANGUAGE (e.g., if input is English, extraction is English).
    2. You write the review ONLY in Portuguese.""",
    verbose=True,
    memory=False,
    llm=CURRENT_LLM,
    max_rpm=5
)

# --- TASKS ---

def create_crew(input_text: str):
    
    # Task 1: Classificação Rigorosa
    task_classify = Task(
        description=f"""
        Input Summary: "{input_text[:800]}..."
        
        CRITICAL INSTRUCTION:
        You are FORBIDDEN from using your internal training knowledge to classify this.
        You MUST validate the classification against the Vector Store.

        Steps:
        1. MANDATORY: Use the 'Search Articles' tool to find similar papers in the Reference Database.
        2. Analyze the 'Area' field of the retrieved metadata.
        3. If the retrieved articles are predominantly 'Computacao', classify input as 'Computacao'. Same for 'Medicina' or 'Quimica'.
        
        EVIDENCE REQUIREMENT:
        You must justify your choice by citing the ID of the article found in the database (e.g., "Classified as Medicina because it is similar to reference ID: doc_chunk_15").
        
        Output: The Area Name and the Reference ID used as proof.
        """,
        expected_output="Scientific Area and Reference ID Evidence.",
        agent=researcher
    )

    # Task 2: Extração e Resenha (Ajustada para o Edital)
    task_final = Task(
        description=f"""
        Analyze the ORIGINAL INPUT below.
        
        === ORIGINAL INPUT START ===
        {input_text[:25000]} 
        === ORIGINAL INPUT END ===

        Generate a JSON object strictly following these rules:

        1. AREA (CRITICAL): 
           - You MUST output EXACTLY one of these strings: "Computacao", "Medicina", "Quimica".
           - Even if the article is Physics, Biology, or Math, map it to the closest allowed category based on the Researcher's findings.
           - Trust the Researcher's classification.

        2. EXTRACTION (Same Language as Input):
           - Detect the language of the input.
           - Extract "what problem...", "step by step...", and "conclusion" using THAT DETECTED LANGUAGE.
           - DO NOT TRANSLATE THESE FIELDS TO PORTUGUESE if the text is in English.

        3. REVIEW (Must be in PORTUGUESE):
           - You MUST write a critical review in PT-BR.
           - CRITICAL REQUIREMENT: You MUST explicitly cover these specific points:
             * Aspectos Positivos (Strengths)
             * Possíveis Falhas ou Limitações (Weaknesses/Flaws)
             * Metodologia e Validade

        REQUIRED JSON FORMAT:
        {{
            "area": "...", 
            "extraction": {{
                "what problem does the artcle propose to solve?": "...",
                "step by step on how to solve it": ["..."],
                "conclusion": "..."
            }},
            "review_markdown": "## Resenha Crítica\\n\\n**Aspectos Positivos:** ...\\n\\n**Possíveis Falhas:** ...\\n\\n**Metodologia e Validade:** ..."
        }}

        IMPORTANT: Output ONLY the raw JSON string.
        """,
        expected_output="Valid JSON string.",
        agent=analyst,
        context=[task_classify]
    )

    return Crew(
        agents=[researcher, analyst],
        tasks=[task_classify, task_final],
        process=Process.sequential,
        verbose=True
    )

def run_agent(source: str, output_name: str = "output"):
    print(f"📥 Entrada: {source}")
    try:
        raw_text = process_input(source)
    except Exception as e:
        print(f"❌ Erro de Leitura: {e}")
        return

    print(f"🚀 Iniciando Agentes ({CURRENT_LLM})...")
    crew = create_crew(raw_text)
    
    try:
        result = crew.kickoff()
    except Exception as e:
        print(f"❌ Erro no CrewAI: {e}")
        return

    json_data = extract_json_from_text(str(result))
    
    if json_data:
        os.makedirs("out", exist_ok=True)
        with open(f"out/{output_name}.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        if "review_markdown" in json_data:
            with open(f"out/review_{output_name}.md", "w", encoding="utf-8") as f:
                f.write(json_data["review_markdown"])
        print(f"\n✅ SUCESSO! Salvo em 'out/{output_name}.json'")
        print(json.dumps(json_data, indent=2, ensure_ascii=False))
    else:
        print("❌ Falha: JSON inválido.")
        print(result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Arquivo/URL")
    parser.add_argument("--name", default="output")
    args = parser.parse_args() if len(sys.argv) > 1 else argparse.Namespace(source="Test...", name="test")
    run_agent(args.source, args.name)