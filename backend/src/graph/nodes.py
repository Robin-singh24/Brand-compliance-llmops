import json
import os
import logging
import re
from typing import Any, Dict, List

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

# Import state schema
from backend.src.graph.state import VideoAuditState, ComplianceIssue

# Service import 
from backend.src.services.video_indexer import VideoIndexerService

# configure the logger
logger = logging.getLogger("brand-compliance-audit")
logging.basicConfig(level=-logging.INFO)

# NODE 1 indexer

def index_video_node(state: VideoAuditState) -> Dict[str,Any]:
    '''
    This node will take the yt video url 
    upload the video to Azure video indexer
    extract teh insights
    '''
    video_url = state.get("video_url")
    video_id = state.get("video_id")
    
    logger.info(f"---- [NODE: Indexer] Processing : {video_url}")
    
    local_file_path = "temp_audit_video.mp4"
    
    try: 
        vi_service = VideoIndexerService()
        
        #download the video 
        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_file_path)
        else:
            raise Exception("Please provide a valid Youtube URL")
        
        # upload the video to Azure video indexer
        azure_video_id = vi_service.upload_video(local_path, video_name=video_id_input)
        logger.info(f"Video successfully uploaded to Azure Video Indexer with ID: {azure_video_id}")     
        
        if os.path.exists(local_path):
            os.remove(local_path)
        
        # wait for the video to be processed and get the insights
        raw_insights = vi_service.wait_for_processing(azure_video_id)
        
        #extract
        clean_data = vi_service.extract_data(raw_insights)
        logger.info(f"----[NODE: Indexer] Extraction completed ----")
        return clean_data
    
    except Exception as e:
        logger.error(f"Video indexer node failed: {e}")
        return{
            "errors": [str(e)],
            "final_status": "FAIL",
            "trancript": "",
            "ocr_text": []
        }
        
        
# NODE 2 : Compliance Auditor
def audio_content_node(state: VideoAuditState) -> Dict[str,Any]:
    '''
    Performs RAG to audit the content 

    '''
    
    logger.info("----[NODE: Auditor] querying Knowledge base and LLM")
    transcript = state.get("transcript", "")
    if not transcript:
        logger.warning("No transcript available for auditing. Skipping the audit video ")
        return {
            "final_status": "FAIL",
            "final_report": "No Transcript available. Audit skipped coz video processing failed",
        }
        
    
    # initialize Azure services
    llm = AzureChatOpenAI(
        azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.0
    )
    
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    
    vector_store = AzureSearch(
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key = os.getenv("AZURE_SEARCH_API_KEY"),
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
    )