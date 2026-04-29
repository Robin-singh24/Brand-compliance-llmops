# pyright: basic
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
logging.basicConfig(level=logging.INFO)

# NODE 1 indexer
# Video to text
def index_video_node(state: VideoAuditState) -> Dict[str,Any]:
    '''
    This node will take the yt video url 
    upload the video to Azure video indexer
    extract teh insights
    '''
    video_url = state.get("video_url")
    video_id_input = state.get("video_id", "vid_demo")
    
    logger.info(f"---- [NODE: Indexer] Processing : {video_url}")
    
    local_file_path = "temp_audit_video.mp4"
    
    try: 
        vi_service = VideoIndexerService()
        
        # Download the video 
        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_file_path)
        else:
            raise Exception("Please provide a valid Youtube URL")
        
        # upload the video to Azure video indexer
        azure_video_id = vi_service.upload_video(local_path, video_name = video_id_input)
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
        azure_deployment = "text-embedding-3-small",
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    
    vector_store = AzureSearch(
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key = os.getenv("AZURE_SEARCH_API_KEY"),
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function = embeddings.embed_query
    )
    
    # RAG Retrieval
    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript} {''.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text, k=3)      # retrive 3 nearest text results from the knowledge base
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])
    
    # System prompt 
    system_prompt = f"""
        You are a senior brand compliance auditor with 15+ years of experience in regulated industries.
    You are precise, conservative, and evidence-driven — you flag only what is explicitly present in the content, never what you infer or assume.

    Your task is to audit the provided video content against the OFFICIAL REGULATORY GUIDELINES below.

    --- REGULATORY GUIDELINES ---
    {retrieved_rules}
    --- END GUIDELINES ---

    REASONING PROCESS (follow this order):
    1. Read all rules carefully and note each rule's scope and conditions.
    2. Review the TRANSCRIPT and OCR TEXT below.
    3. For each rule, explicitly check: does the content VIOLATE, SATISFY, or NOT ADDRESS it?
    4. Only include a violation if you find direct evidence in the transcript or OCR text.
    5. If you are uncertain whether something is a violation, do NOT include it.

    OUTPUT FORMAT:
    Return ONLY a valid JSON object. No preamble, no explanation, no markdown fences.

    JSON SCHEMA:
    {
        "compliance_result": [
            {
                "category": "e.g. Claim Validation, Disclosure, Branding",
                "severity": "CRITICAL | HIGH | MEDIUM | LOW",
                "description": "What was said/shown, which rule it violates, and why"

            }
        ],
        "status": "PASS | FAIL",
        "final_report": "2-3 sentence summary of overall compliance posture"
    }

    SEVERITY DEFINITIONS:
    - CRITICAL — legal or regulatory breach, immediate action required
    - HIGH     — significant violation likely to cause harm or penalty
    - MEDIUM   — clear rule breach but limited impact
    - LOW      — minor or technical deviation

    RULES:
    - If no violations are found, set "status" to "PASS" and "compliance_result" to [].
    - Each violation must map to a specific rule from the guidelines via "rule_reference".
    - Do NOT fabricate violations. Do NOT flag ambiguity as a violation.
    - "location" is mandatory — every finding must be traceable to the source material.

    --- CONTENT TO AUDIT ---
    TRANSCRIPT:
    {transcript}

    OCR TEXT:
    {ocr_text}
    --- END CONTENT ---
    """
    
    user_message = f"""
                VIDEO_METADATA: {state.get('video_metadata',{})}
                TRANSCRIPT: {transcript}
                ON-SCREEN TEXT(OCR): {ocr_text}
            """
            
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        content = response.content
        
        if "```" in content:
           content = re.search(r"```(?:json)?(.?)```", content, re.DOTALL).group(1) 
        
        audit_data = json.loads(content.strip())
        return {
            "compliance_result": audit_data.get("compliance_result",[]),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "No report generated") 
        }
    except Exception as e:
        logger.error(f"System error in Auditor node: {str(e)}")
        # Logging the raw response for debugging
        logger.error(f"RAW LLM response: {response.content if 'response' in locals() else 'NONE'}")
        
        return{
            "errors": str(e),
            "final_status": "FAIL"
        }