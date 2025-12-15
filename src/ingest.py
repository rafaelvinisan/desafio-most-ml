import os
import re
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
# from dotenv import load_dotenv # Não precisamos mais carregar .env para embeddings

# --- CONFIGURAÇÕES ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
DB_PATH = "./db/chroma_data"
DATA_PATH = "./data/pdfs"
COLLECTION_NAME = "scientific_articles"

def clean_text_robust(text: str) -> str:
    """
    Limpeza robusta de texto extraído de PDFs.
    Remove caracteres especiais, corrige hifens quebrados, normaliza espaços.
    """
    if not text:
        return ""
    
    # Remove caracteres de controle e tokens especiais
    text = text.replace("<EOS>", "").replace("<pad>", "").replace("\x00", "")
    
    # Corrige hifens quebrados no final de linha (ex: "texto-\nquebrado" -> "textoquebrado")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # Remove múltiplas quebras de linha e substitui por espaço simples
    text = re.sub(r'\n+', ' ', text)
    
    # Remove múltiplos espaços em branco
    text = re.sub(r'\s+', ' ', text)
    
    # Remove caracteres não-ASCII problemáticos, mas mantém acentos
    text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\{\}\"\'\@\#\$\%\&\*\+\=\<\>\|\~\`\/\\áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]', '', text)
    
    # Remove espaços no início e fim
    text = text.strip()
    
    # Remove espaços antes de pontuação
    text = re.sub(r'\s+([\.\,\;\:\!\?])', r'\1', text)
    
    return text

def get_files_from_data():
    """Varre a pasta data/pdfs e retorna lista de caminhos e áreas baseadas nas subpastas."""
    documents = []
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
        print(f"📁 Pasta criada: {DATA_PATH}. Adicione subpastas com os artigos lá.")
        return []

    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith(".pdf"):
                area = os.path.basename(root)
                full_path = os.path.join(root, file)
                documents.append({"path": full_path, "area": area, "filename": file})
    return documents

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract: text += extract + "\n"
        return text
    except Exception as e:
        print(f"❌ Erro ao ler {pdf_path}: {e}")
        return None

def main():
    # 1. Configurar Cliente ChromaDB
    client = chromadb.PersistentClient(path=DB_PATH)
    
    
    print("⚙️  Carregando modelo de embeddings local (pode demorar um pouco na 1ª vez)...")
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"🗑️  Coleção anterior removida para reinício limpo.")
    except Exception as e:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_func
    )

    # 2. Ler Arquivos
    docs_metadata = get_files_from_data()
    if not docs_metadata:
        print("⚠️  Nenhum PDF encontrado. Verifique as pastas em 'data/pdfs/'.")
        return

    print(f"📚 Encontrados {len(docs_metadata)} artigos. Processando...")

    # 3. Splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )

    # 4. Processamento
    total_chunks = 0
    
    for doc in docs_metadata:
        raw_text = extract_text_from_pdf(doc['path'])
        if not raw_text: continue

        # Limpa o texto ANTES de fazer o split
        cleaned_text = clean_text_robust(raw_text)
        
        chunks = text_splitter.split_text(cleaned_text)
        
        ids = []
        metadatas = []
        documents_content = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc['filename']}_chunk_{i}"
            ids.append(chunk_id)
            documents_content.append(chunk)
            # Metadados são cruciais para o RAG depois
            metadatas.append({
                "source": doc['filename'],
                "area": doc['area'],
                "chunk_index": i
            })

        if ids:
            collection.add(ids=ids, documents=documents_content, metadatas=metadatas)
            total_chunks += len(ids)
            print(f"✅ {doc['filename']} ({doc['area']}): {len(ids)} chunks.")

    print(f"\n🎉 Sucesso! {total_chunks} chunks indexados localmente em '{DB_PATH}'.")

if __name__ == "__main__":
    main()