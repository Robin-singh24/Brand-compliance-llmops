# pyright: basic

'''
This file does the following things:
1. Sets up the audit request
2. Runs the AI workflow
3. Displays the final compliance report

'''

import json
import uuid
import logging 

from pprint import pprint
from dotenv import load_dotenv

from backend.src.graph.workflow import app

# Configure logging - sets up the "flight recorder" for your application
logging.basicConfig(
    level = logging.INFO,               # INFO = show important events (DEBUG would show everything)
    format = '%(asctime)s - %(name)s -%(levelname)s - %(message)s'
    # Format: timestamp - logger_name - severity - message
    # Example: "2024-01-15 10:30:45 - brand-guardian - INFO - Starting audit"
)

logger = logging.getLogger("brand-comliance-video")         # Creates a named logger for this module

def run_cli_simulation():
    '''
    Simulates the video compliance audit request
    
    This function orchestrates the entire audit process:
    - Creates a unique session ID
    - Prepares the video URL and metadata
    - Runs it through the AI workflow
    - Displays the compliance results
    
    '''
    
    # Generate the UUID
    # Creates a unique identifier for this audit session
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session : {session_id}")
    
    # Define the initial state
    # This dictionary contains all the input data for the workflow
    initial_inputs = {
        # The YouTube video to audit
        "video_url" : "https://www.youtube.com/watch?v=CcfZqA_R7Tc",
        # Shortened video ID for easier tracking (first 8 chars of session ID)
        "video_id" : f"vid_{session_id[:8]}",
        # To store the compliance violations found
        "compliance_results" : [],
        "errors" : []
    }
    
    # ========== DISPLAY SECTION: INPUT SUMMARY ==========
    print("\n----------INITIALIZING WORKFLOW----------")
    print(f"Input payload : {json.dumps(initial_inputs, indent=2)}")
    
    try:
        # app.invoke() triggers the LangGraph workflow
        # It passes through: START → Indexer → Auditor → END
        # Returns the final state with all results
        final_state = app.invoke(initial_inputs)
        print("\n--------------Workflow execution completed--------------")
        
        print("\n Compliance Audit Report == ")
        
        # .get() safely retrieves values (returns None if key doesn't exist)
        # Displays the video ID that was audited
        print(f"Video ID :      {final_state.get('video_id')}")
        print(f"Status :        {final_state.get('final_status')}")
        
        print("\n [VIOLATIONS DETECTED]")
        
        # Extract the list of compliance violations
        # Default to empty list if no results
        results = final_state.get('compliance_results', [])
        
        if results:
            for issue in results:
                
                # Each issue is a dict with: severity, category, description
                print(f"[{issue.get('severity')}] [{issue.get('category')}] : [{issue.get('description')}]")    
        else: 
            # No violations found (clean video)
            print("No violations found.")
            
        print("\n[FINAL SUMMARY]")
        print(final_state.get('fnal_report'))
    
    except Exception as e:
        logger.error(f"Workflow Execution Failed : {str(e)}")
        raise e
    
if __name__ == "main":
    run_cli_simulation()