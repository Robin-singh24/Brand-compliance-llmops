# pyright: basic
'''
AZURE OPEN TELEMETRY INGESTION
'''

import os 
import logging

from azure.monitor.opentelemetry import configure_azure_monitor

# create a logger
logger = logging.getLogger("brand-compliance-teelemetry")

def setup_telemetry():
    '''
    Initialises the Azure Monitor Opentelemetry.
    Track https req, database queries, errors and performance metrics 
    sends data to azure monitor
    
    It auto captures every API,
    No manual logging req
    '''
    
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    
    # check if configured
    if not connection_string:
        logger.warning("No key found... Telemetry is disabled!!!!!!")
        return
    
    # configure the monitor
    try:
        configure_azure_monitor(
            connection_string = connection_string,
            logger_name = "brand_compliance_tracing"
        )
        logger.info("Azure Monitor Tracking enabled and connected...")
    except Exception as e:
        logger.error(f"Failed to initialize Azure Monitor : {e}")
        
    