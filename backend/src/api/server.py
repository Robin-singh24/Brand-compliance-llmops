# pyright: basic
'''
FAST API 
'''

import uuid
import logging

from fastapi import FastAPI, HTTPException

from pydantic import BaseModel
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv(override=True)


# initialize the telemetry
from backend.src.api.telemetry import setup_telemetry
setup_telemetry()

# import workflow graph
from backend.src.graph.workflow import app as compliance_graph

# configure logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("api-server")

# FastAPI application

app = FastAPI(
    title="Brand Compliance AI APP",
    description="API for checking the compliance of the Ads ran by brands",
    version="1.0.0"
)

# Define Data Models
class AuditRequest(BaseModel):
    '''
    Define the base structure of the incoming API requests
    '''
    video_url : str
    
class ComplianceIssue(BaseModel):
    category: str
    severity: str
    description: str

class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]
    
""" MAIN ENDPOINT """
@app.post("/audit", response_model=AuditResponse)

async def audit_video(request: AuditRequest):
    '''
    Main API endpoint that triggers the brand compliance audit workflow
    '''
    session_id = str(uuid.uuid4())
    video_id_short = f"vid_{session_id[:8]}"
    logger.info(f"Recieved the audit request : {request.video_url} (Session : {session_id})")

    initial_inputs = {
        "video_url" : request.video_url,
        "video_id" : video_id_short,
        "compliance_results" : [],
        "errors" : []
    }
    
    try:
        final_state = compliance_graph.invoke(initial_inputs)
        return AuditResponse(
            session_id = session_id,
            video_id = final_state.get("video_id"),
            status = final_state.get("final_status","UNKNOWN"),
            final_report = final_state.get("final_report") or "No Report Generated",
            compliance_results = final_state.get("compliance_result", [])
        )
    except Exception as e:
        logger.error(f"Audit failed : {str(e)}")
        raise HTTPException(
            status_code=500 ,
            detail=f"Workflow Execution Fialed: {str(e)}"
        )
        
# Health check point
@app.get("/health")
def health_check():
    return {"status" : "Healthy" , "service" : "Brand Compliance AI"}