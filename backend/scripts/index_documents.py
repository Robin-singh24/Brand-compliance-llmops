#pyright: basic
import os
import glob
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

# document loaders and splitters
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Azure components
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("indexer")

def index_docs():
    '''
    Reads the PDFs, chunks them and uploads them to Azure Search
    
    '''
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir,"../../backend/data")
    
    # check on the env variables
    logger.info("="*60)
    logger.info("Environment configuration check: ")
    logger.info(f"AZURE_OPENAI_ENDPOINT: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    logger.info(f"AZURE_OPENAI_API_VERSION: {os.getenv('AZURE_OPENAI_API_VERSION')}")
    logger.info(f"Embedding Deployment: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small')}")
    logger.info(f"AZURE_SEARCH_ENDPOINT: {os.getenv('AZURE_SEARCH_ENDPOINT')}")
    logger.info(f"AZURE_SEARCH_INDEX_NAME: {os.getenv('AZURE_SEARCH_INDEX_NAME')}")
    logger.info("="*60)
    
    # validate the required environment variables
    required_vars=[
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
        "AZURE_SEARCH_INDEX_NAME"
    ]
    
    misssing_vars = [var for var in required_vars if not os.getenv(var)]
    if misssing_vars:
        logger.error(f"Missing required environment variables: {misssing_vars}")
        logger.error("Please check your .env file and ensure all the required variables are set.")
        return
    
    # initialize the embedding model : text into vectors
    try:
        logger.info("Initializing Azure OpenAI Embeddings...")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment= os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small'),
            azure_endpoint= os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key = os.getenv('AZURE_OPENAI_API_KEY'),
            openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01'),
        )
        logger.info("Embedding model initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialze embeddings: {e}")
        logger.error("Please verify your Azure OpenAI deployment Name and Endpoint.")
        return 
    
    # Initialize the Azure Search vector db
    index_name = os.getenv('AZURE_SEARCH_INDEX_NAME')
    try:
        logger.info("Initializing Azure AI Search Vector Store...")
        vector_store = AzureSearch(
            azure_search_endpoint = os.getenv('AZURE_SEARCH_ENDPOINT'),
            azure_search_key= os.getenv('AZURE_SEARCH_API_KEY'),
            index_name = index_name,
            embedding_function = embeddings.embed_query,
        )
        logger.info(f"✓ Vector store initialized for index: {index_name}")
    except Exception as e:
        logger.error(f"Failed to initialze Search: {e}")
        logger.error("Please verify your Azure Search Endpoint API key and Index name.")
        return 
        
    # Find PDFs 
    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDFs found in {data_folder}. Please add files")
    logger.info(f"Found {len(pdf_files)} PDFs to process : {[os.path.basename(f) for f in pdf_files]}")
    
    all_splits = []
    
    # process each pdf
    for pdf_path in pdf_files:
        try:
            logger.info(f"Loading: {os.path.basename(pdf_path)}")
            loader = PyPDFLoader(pdf_path)
            raw_docs = loader.load()
            
            # Chunking Strategy
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = 1000,
                chunk_overlap = 200
            )
            splits = text_splitter.split_documents(raw_docs)
            for split in splits:
                split.metadata["source"] = os.path.basename(pdf_path)
                
            all_splits.extend(splits)
            logger.info(f"Split into {len(splits)} chunks.")
        except Exception as e:
            logger.error(f"Failed to process {pdf_path} : {e}")
            
    # upload to Azure
    if all_splits:
        logger.info(f"Uploading {len(all_splits)} chunks to Azure AI search index '{index_name}'...")
        try:
            # Azure search accepts bactches automatically 
            vector_store.add_documents(documents = all_splits)
            logger.info("="*60)
            logger.info(f"Indexing complete! Knowledge base is complete...")
            logger.info(f"Total chunks indexed : {len(all_splits)}")
        except Exception as e:
            logger.error(f"Failed to upload the documents to Azure search : {e}")
            logger.error("Please check the Azure Search configuration and try again.")
    else:
        logger.warning(f"No documents were processed")
            
if __name__ == "__main__":
    index_docs()