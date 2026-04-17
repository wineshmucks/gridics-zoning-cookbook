import json
import urllib.parse
import urllib.request
import re
from agno.tools import tool
from agno.run import RunContext
import os

from app.services.gridics_client import _build_gridics_client, extract_compressed_zoning_summary
from app.services.zoning_knowledge_service import query_customer_zoning_knowledge
from app.db.session import SessionLocal
from app.db.models import TenantClient
from sqlalchemy import select

def _get_tenant_client(client_id: str):
    with SessionLocal() as db:
        return db.scalar(select(TenantClient).where(TenantClient.client_id == client_id))

@tool
def standardize_address(address: str, run_context: RunContext) -> str:
    """
    Standardizes a property address. Call this FIRST whenever a user asks about a specific property.
    """
    if not run_context.session_state:
        run_context.session_state = {}

    mapbox_token = os.getenv("MAPBOX_API_KEY")
    if not mapbox_token:
        # Fallback if no token is set
        run_context.session_state["active_property"] = address
        return f"SYSTEM: Address set to '{address}'. Delegate to Property Specialist."

    query = urllib.parse.quote(address)
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?access_token={mapbox_token}&types=address&country=us"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if not data.get("features"):
                return f"SYSTEM: Could not find a match for '{address}'. Ask user to verify."
                
            best_match = data["features"][0]
            standardized_address = best_match.get("place_name", address)
            
            # Heuristic: If the original address was just a street (no commas), it lacks city/zip context
            if len(address.split(",")) < 2:
                run_context.session_state["pending_property"] = standardized_address
                return (
                    f"SYSTEM: The address was standardized to '{standardized_address}'. "
                    "This is a material change. STOP DELEGATING. Reply directly to the user "
                    "and ask them to confirm if this is the correct address."
                )
            else:
                run_context.session_state["active_property"] = standardized_address
                run_context.session_state.pop("pending_property", None)
                return f"SYSTEM: Address standardized to '{standardized_address}'. Delegate to Property Specialist."
    except Exception as e:
        run_context.session_state["active_property"] = address
        return f"SYSTEM: Mapbox API failed ({str(e)}). Proceeding with unstandardized address '{address}'."

@tool
def confirm_pending_address(run_context: RunContext) -> str:
    """Call this when the user confirms the pending standardized address is correct."""
    if not run_context.session_state:
        run_context.session_state = {}
        
    pending = run_context.session_state.get("pending_property")
    if pending:
        run_context.session_state["active_property"] = pending
        run_context.session_state.pop("pending_property", None)
        return f"SYSTEM: Address '{pending}' is confirmed. Delegate to Property Specialist."
    return "SYSTEM: No pending address to confirm."

@tool
def analyze_customer_zoning_request(run_context: RunContext) -> str:
    """Fetches compressed Gridics parcel data for the active property in the session."""
    if not run_context.session_state or not run_context.session_state.get("active_property"):
        return "SYSTEM: No active property. Standardize an address first."
    
    active_address = run_context.session_state["active_property"]
    
    try:
        client = _build_gridics_client()
        
        # 1. Extract the street address (everything before the first comma)
        street_address = active_address.split(",")[0].strip()
        
        # 2. Extract the 5-digit ZIP code
        zip_match = re.search(r"\b(\d{5})\b", active_address)
        zip_code = zip_match.group(1) if zip_match else ""
        
        if not zip_code:
            return "SYSTEM: Could not extract a ZIP code from the active address. Please re-standardize the address."
        
        # 3. Call the API with all required parameters
        raw_record = client.get_property_record(
            state_env="fl", 
            address=street_address, 
            zip_code=zip_code
        )
        
        summary = extract_compressed_zoning_summary(raw_record)
        
        # Save summary to state so other tools/agents can reference it later
        run_context.session_state["gridics_summary"] = summary
        
        # Return compressed JSON to LLM
        return json.dumps(summary)
        
    except Exception as e:
        return f"SYSTEM: Gridics API failed: {str(e)}"

@tool
def query_customer_zoning_code(query: str, run_context: RunContext, limit: int = 5) -> str:
    """Searches the zoning code knowledge base for legal text and citations."""
    
    # Silently extract the client_id from the context dependencies injected by the Orchestrator
    client_id = run_context.dependencies.get("client_id") if run_context.dependencies else None
    
    tenant = _get_tenant_client(client_id) if client_id else None
    if not tenant:
        return "SYSTEM: Cannot query knowledge base without a valid client_id."
        
    try:
        with SessionLocal() as db:
            raw_results = query_customer_zoning_knowledge(db, tenant, query=query, limit=limit)
            
        # Compress results to save LLM context
        cleaned = []
        for res in raw_results.get("results", []):
            cleaned.append({
                "title": res.get("meta_data", {}).get("section_title"),
                "url": res.get("meta_data", {}).get("page_url"),
                "content": res.get("content", "")[:1000] # Truncate long content
            })
        return json.dumps(cleaned)
    except Exception as e:
        return f"SYSTEM: Knowledge Base query failed: {str(e)}"
