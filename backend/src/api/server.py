# pyright: basic
"""
FAST API
Entry point for the Brand Compliance AI application.
Defines the FastAPI app, request/response models, and the main audit endpoint
that triggers the LangGraph compliance workflow.
"""

import uuid
import logging

from fastapi import FastAPI, HTTPException

from pydantic import BaseModel
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file, overriding any existing system env vars
load_dotenv(override=True)


# Initialize OpenTelemetry tracing/metrics for observability
from backend.src.api.telemetry import setup_telemetry
setup_telemetry()

# Import the compiled LangGraph workflow (aliased to avoid name collision with FastAPI app)
from backend.src.graph.workflow import app as compliance_graph

# Configure root logger to INFO level — captures workflow, request, and error logs
logging.basicConfig(level=logging.INFO)

# Module-level logger scoped to the API server for structured log filtering
logger = logging.getLogger("api-server")


# ---------------------------------------------------------------------------
# FastAPI Application Instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Brand Compliance AI APP",
    description="API for checking the compliance of the Ads ran by brands",
    version="1.0.0"
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class AuditRequest(BaseModel):
    """
    Incoming payload for a compliance audit request.

    Attributes:
        video_url: Publicly accessible URL of the advertisement video to audit.
    """
    video_url: str


class ComplianceIssue(BaseModel):
    """
    Represents a single compliance violation detected in the video.

    Attributes:
        category:    High-level category of the violation (e.g. "Audio", "Visual").
        severity:    Impact level of the issue (e.g. "LOW", "MEDIUM", "HIGH").
        description: Human-readable explanation of what was flagged and why.
    """
    category: str
    severity: str
    description: str


class AuditResponse(BaseModel):
    """
    Outgoing payload returned after the compliance workflow completes.

    Attributes:
        session_id:         UUID generated per request for end-to-end traceability.
        video_id:           Short identifier derived from session_id (e.g. "vid_a1b2c3d4").
        status:             Final workflow status (e.g. "COMPLIANT", "NON_COMPLIANT").
        final_report:       Narrative summary produced by the reporting node.
        compliance_results: List of individual ComplianceIssue objects found during audit.
    """
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    Trigger a full brand compliance audit on the provided video.

    Flow:
        1. Generate a unique session ID and a short video identifier.
        2. Build the initial state dict expected by the LangGraph workflow.
        3. Invoke the compliance graph synchronously and await its final state.
        4. Map the final state fields onto the AuditResponse model and return.

    Args:
        request: AuditRequest containing the video URL to analyse.

    Returns:
        AuditResponse with session metadata, workflow status, narrative report,
        and a list of detected compliance issues.

    Raises:
        HTTPException 500: If the workflow raises an unhandled exception.
    """
    # Generate a UUID for this session; derive a short video ID from its prefix
    session_id = str(uuid.uuid4())
    video_id_short = f"vid_{session_id[:8]}"

    logger.info(f"Received the audit request : {request.video_url} (Session : {session_id})")

    # Construct the initial state that seeds the LangGraph workflow nodes
    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id_short,
        "compliance_results": [],   # Populated progressively by compliance-check nodes
        "errors": []                # Accumulates any non-fatal errors during the run
    }

    try:
        # Invoke the LangGraph workflow and block until the final state is returned
        final_state = compliance_graph.invoke(initial_inputs)

        # Map workflow output fields to the structured API response
        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id"),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report") or "No Report Generated",
            compliance_results=final_state.get("compliance_result", [])
        )

    except Exception as e:
        # Log full error details server-side before surfacing a generic 500 to the client
        logger.error(f"Audit failed : {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Workflow Execution Failed: {str(e)}"
        )


@app.get("/health")
def health_check():
    """
    Liveness probe endpoint.
    Used by load balancers and container orchestrators (e.g. Kubernetes) to verify
    the service is running and ready to accept traffic.

    Returns:
        JSON dict with service status and name.
    """
    return {"status": "Healthy", "service": "Brand Compliance AI"}