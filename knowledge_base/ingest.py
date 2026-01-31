import os
import getpass
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

# 1. SECURITY CHECK
if "OPENAI_API_KEY" not in os.environ:
    # If key is missing, ask for it (Fallback)
    print("⚠️  Security Check: API Key missing from environment.")
    raw_key = getpass.getpass(prompt="🔑 Please paste your OpenAI API Key here: ")
    os.environ["OPENAI_API_KEY"] = raw_key.strip()

def load_all_documents():
    raw_dir = "knowledge_base/raw/"
    docs = []
    
    # DYNAMIC SCANNING: Look at every file in the folder
    if not os.path.exists(raw_dir):
        os.makedirs(raw_dir)
        
    files = [f for f in os.listdir(raw_dir) if f.endswith(".txt")]
    
    print(f"Ingest System: Scanning {raw_dir}...")
    
    for filename in files:
        filepath = os.path.join(raw_dir, filename)
        try:
            with open(filepath, "r") as f:
                content = f.read()
                # Tag the memory with its source (e.g., "eve_ui_sop.txt")
                docs.append(Document(page_content=content, metadata={"source": filename}))
                print(f"  - Loaded: {filename}")
        except Exception as e:
            print(f"  - Error loading {filename}: {e}")
            
    print(f"Ingest System: Successfully loaded {len(docs)} source files.")
    return docs

def split_and_store(docs):
    # Split text into chunks (Logic vs Physics vs Interface)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        separators=["\n\n", "Chapter", "SOP:", "Rule:", "Formula:"]
    )
    chunks = splitter.split_documents(docs)
    
    # Index into the Brain
    db = Chroma.from_documents(
        documents=chunks,
        embedding=OpenAIEmbeddings(),
        persist_directory="./knowledge_base/chroma_db"
    )
    print(f"✅ Eve Knowledge Base: {len(chunks)} Core Rules Synced Successfully.")

if __name__ == "__main__":
    docs = load_all_documents()
    if docs:
        split_and_store(docs)
    else:
        print("❌ Error: No source files found. Please check knowledge_base/raw/")
