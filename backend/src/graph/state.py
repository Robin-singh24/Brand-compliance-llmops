from typing import Annotated, Dict, List, Optional, Any, TypedDict
import operator


class ComplianceIssue(TypedDict):
    category: str
    description: str                # detailed description of the compliance issue
    severity: str                   # CRITICAL | WARNING
    timestamp: Optional[str]
    
    
class VideoAuditState(TypedDict):
    '''
    Defines the data schema for the langgraph execution content
    '''
    #input parameters
    video_url: str
    video_id: str
    
    # ingestion and extracting data
    local_file_path: Optional[str]
    video_metadata: Optional[Dict[str,Any]]
    trancsript: Optional[str]
    ocr_text: List[str]
    
    # analysis results
    compliance_result: Annotated[List[ComplianceIssue], operator.add]
    
    # final deliverables
    final_status: str
    final_result: str               # probably a MD file
    
    # system observability
    errors: Annotated[List[str], operator.add]
    
    