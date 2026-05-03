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
