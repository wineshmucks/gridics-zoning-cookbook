import os
import json
import urllib.parse
import urllib.request
from agno.tools import tool
from agno.agent import RunContext

@tool
def standardize_address(address: str, run_context: RunContext) -> str:
    """
    Standardizes a property address using the Mapbox Geocoding API.
    Call this FIRST whenever a user asks about a specific property to ensure
    the address is fully qualified (Street, City, State, ZIP).
    """
    # Ensure session state is initialized
    if not run_context.session_state:
        run_context.session_state = {}

    mapbox_token = os.getenv("MAPBOX_API_KEY")
    if not mapbox_token:
        return "SYSTEM: Error - MAPBOX_API_KEY environment variable is missing. Cannot standardize address."

    # 1. Call Mapbox Geocoding API
    query = urllib.parse.quote(address)
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?access_token={mapbox_token}&types=address&country=us"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return f"SYSTEM: Error calling Mapbox API: {str(e)}. Proceed with original address: {address}"

    if not data.get("features"):
        return f"SYSTEM: Could not find a standardized match for '{address}'. Ask the user to verify the address."

    # 2. Extract the best match and context
    best_match = data["features"][0]
    standardized_address = best_match.get("place_name", address)
    
    # Mapbox returns context arrays (city, state, zip)
    context_data = best_match.get("context", [])
    resolved_zip = next((c["text"] for c in context_data if c["id"].startswith("postcode")), "")
    resolved_city = next((c["text"] for c in context_data if c["id"].startswith("place")), "")

    # 3. Determine if the address is "Materially Different"
    # A simple heuristic: If Mapbox added a city or zip code that the user didn't provide in their input.
    address_lower = address.lower()
    materially_different = False
    
    if resolved_zip and resolved_zip.lower() not in address_lower:
        materially_different = True
    if resolved_city and resolved_city.lower() not in address_lower:
        materially_different = True

    # 4. Handle State and Route Instructions to the LLM
    if materially_different:
        # Save as pending and force the LLM to pause for confirmation
        run_context.session_state["pending_property"] = standardized_address
        return (
            f"SYSTEM: The address was standardized to '{standardized_address}'. "
            "Because the user did not provide the full city/zip context, this is a material change. "
            "STOP DELEGATING. Reply directly to the user asking them to confirm if they meant "
            f"'{standardized_address}' before proceeding."
        )
    else:
        # Save as active, clear pending, and instruct LLM to proceed
        run_context.session_state["active_property"] = standardized_address
        run_context.session_state.pop("pending_property", None)
        return (
            f"SYSTEM: Address successfully standardized to '{standardized_address}' with no material difference. "
            "The property is now active in the session. You may proceed to delegate to the Property Specialist."
        )

@tool
def confirm_pending_address(run_context: RunContext) -> str:
    """
    Call this tool when the user confirms that the pending standardized address is correct.
    """
    if not run_context.session_state:
        run_context.session_state = {}
        
    pending_address = run_context.session_state.get("pending_property")
    
    if pending_address:
        # Promote from pending to active
        run_context.session_state["active_property"] = pending_address
        run_context.session_state.pop("pending_property", None)
        return f"SYSTEM: Address '{pending_address}' is now confirmed and active. Delegate to the Property Specialist."
    
    return "SYSTEM: No pending address found to confirm."

@tool
def analyze_customer_zoning_request(run_context: RunContext) -> str:
    """
    Fetches Gridics parcel data for the active property.
    """
    if not run_context.session_state:
        run_context.session_state = {}
        
    active_property = run_context.session_state.get("active_property")
    if not active_property:
        return "SYSTEM: Error - No active property found. Standardize and confirm an address first."
    
    # TODO: Call your actual Gridics client here
    # return gridics_client.get_property_record(address=active_property)
    return f"Gridics Data for {active_property}: Zone is CI, Max Height 5 Stories."

@tool
def query_customer_zoning_code(query: str, run_context: RunContext) -> str:
    """
    Searches the zoning code knowledge base for legal text and citations.
    """
    # TODO: Call your vector DB / RAG system here
    return f"Zoning Code Result for '{query}': Permitted uses include Office and Residential. (Source: Article 4)"
