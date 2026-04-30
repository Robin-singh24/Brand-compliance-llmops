# pyright: basic
import json
import uuid
import logging 

from pprint import pprint
from dotenv import load_dotenv

from backend.src.graph.workflow import app

logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s -%(levelname)s - %(message)s'
)

logger = logging.getLogger("brand-comliance-video")

def run_cli_simulation():
    '''
    Simulates the video compliance audit request
    '''
    
    # generate the UUID
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session : {session_id}")
    
    # define the initial state
    initial_inputs = {
        "video_url" : "",
        "video_id" : f"vid_{session_id[:8]}",
        "compliance_results" : [],
        "errors" : []
    }
    
    print("\n----------INITIALIZING WORKFLOW----------")
    print(f"Input payload : {json.dumps(initial_inputs, indent=2)}")
    
    try:
        final_state = app.invoke(initial_inputs)
        print("\n--------------Workflow execution completed--------------")
        
        print("\n Compliance Audit Report == ")
        print(f"Video ID : {final_state.get('video_id')}")
        print(f"Status : {final_state.get('final_status')}")
        print("\n [VIOLATIONS DETECTED]")
        results = final_state.get('compliance_results', [])
        
        if results:
            for issue in results:
                print(f"[{issue.get('severity')}] [{issue.get('category')}] : [{issue.get('description')}]")
        print("\n[FINAL SUMMARY]")
        print(final_state.get('fnal_report'))
    
    except Exception as e:
        logger.error(f"Workflow Execution Failed : {str(e)}")
        raise e
    
if __name__ == "main":
    run_cli_simulation()
    
