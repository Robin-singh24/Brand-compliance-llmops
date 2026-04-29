# pyright: basic
'''
This module defines the DAG. Directed acyclic graph. 
it basically orchestrates the compliance audit process.
It connects the nodes which are using the StateGraph from LangGraph

START -> index_video_node -> audit_content_node -> END

'''

from langgraph.graph import END, StateGraph

from backend.src.graph.state import VideoAuditState
from backend.src.graph.nodes import (
    audio_content_node, 
    index_video_node
)

def create_graph():
    '''
        Constructs and compiles the LangGraph workflow.
        Returns:
        Compliled graph: runnable graph object for execution.
        
    '''
    # Initialize the graph with the state schema
    workflow = StateGraph(VideoAuditState)
    
    # add the nodes
    workflow.add_node("indexer", index_video_node)
    workflow.add_node("auditor", audio_content_node) 
    
    # define the entry point
    workflow.set_entry_point("indexer")
    
    #define the edges
    workflow.add_edge("indexer", "auditor")
    
    # the workflow ends after the auditor node
    workflow.add_edge("auditor", END)
    
    # compile the graph
    app = workflow.compile()
    return app

app = create_graph()