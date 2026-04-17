import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 1. Load environment variables
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path=env_path, verbose=True)

from agno.agent import Agent
from app.agents.factory import build_agent_model
from app.agents.customer_zoning_agent import customer_zoning_team

# ---------------------------------------------------------
# HARDCODED TEST CASES
# ---------------------------------------------------------
TEST_CASES = [
    {
        "id": "T-001",
        "type": "General Knowledge",
        "prompt": "What are the general rules for fences in commercial zones?",
    },
    {
        "id": "T-002",
        "type": "Specific Location (Auto-Standardizes)",
        "prompt": "Can I build a duplex at 3154 MARY ST # 4, Miami, FL 33133?",
    },
    {
        "id": "T-003",
        "type": "Specific Location (Requires Confirmation)",
        "prompt": "How high can I build a fence at 3148 Mary St?",
    }
]

# ---------------------------------------------------------
# EVALUATION SCHEMA & AGENT
# ---------------------------------------------------------
class EvaluationScore(BaseModel):
    is_location_specific: bool = Field(description="True if the user asked about a specific property or address.")
    address_standardized: bool = Field(description="True if the active_property state contains a formatted address.")
    gridics_data_retrieved: bool = Field(description="True if the gridics_summary state is populated with data.")
    response_correct: bool = Field(description="True if the agent answered the user's question accurately and helpfully.")
    reasoning: str = Field(description="A brief 1-sentence explanation of why the response was graded correct or incorrect.")

evaluator_agent = Agent(
    id="evaluator-agent",
    name="QA Evaluator",
    model=build_agent_model(provider="gemini", model_id="gemini-2.5-flash"),
    output_schema=EvaluationScore, # <--- Changed from response_model
    instructions=[
        "You are an expert QA tester for a Zoning AI Assistant.",
        "You will be provided with the user's prompt, the AI's final response, and the system's internal state variables.",
        "Grade the response based on the provided schema."
    ]
)

# ---------------------------------------------------------
# TEST RUNNER LOGIC
# ---------------------------------------------------------
def run_hardcoded_evals():
    client_id = os.getenv("TEST_CLIENT_ID", "org_3AhfzeTJJvPg6OvNf8KS1pf2m4N")
    print(f"[*] Starting Local Evaluation Suite for Client ID: {client_id}\n")
    
    # Inject dependencies
    customer_zoning_team.dependencies = {"client_id": client_id}
    
    results = []
    
    for index, test in enumerate(TEST_CASES):
        prompt = test["prompt"]
        print(f"[{test['id']}] Testing ({test['type']}): '{prompt}'")
        
        # 1. Reset Session State for strict isolation between tests
        session_id = f"eval_session_local_{index}"
        customer_zoning_team.session_state = {
            "active_property": None, 
            "pending_property": None, 
            "gridics_summary": None
        }
        
        # 2. First Turn
        response = customer_zoning_team.run(prompt, session_id=session_id)
        final_content = response.content
        
        # 3. Handle Mapbox Confirmation Pauses Auto-Magically
        if customer_zoning_team.session_state.get("pending_property"):
            print("    -> Agent paused for confirmation. Auto-injecting 'Yes'...")
            follow_up = customer_zoning_team.run("Yes, Miami FL 33133", session_id=session_id)
            final_content = follow_up.content
        
        # 4. Extract Internal State for the Evaluator
        state = customer_zoning_team.session_state
        
        eval_payload = f"""
        USER PROMPT: {prompt}
        AI FINAL RESPONSE: {final_content}
        
        INTERNAL STATE:
        - Active Property: {state.get('active_property')}
        - Gridics Summary Exists: {bool(state.get('gridics_summary'))}
        """
        
        # 5. Run the Evaluator
        eval_result: EvaluationScore = evaluator_agent.run(eval_payload).data
        
        # 6. Print the formatted grade
        print(f"    [Location Specific] : {'✅' if eval_result.is_location_specific else '➖'}")
        if eval_result.is_location_specific:
            print(f"    [Standardized]      : {'✅' if eval_result.address_standardized else '❌'}")
            print(f"    [Gridics Retrieved] : {'✅' if eval_result.gridics_data_retrieved else '❌'}")
        print(f"    [Response Correct]  : {'✅' if eval_result.response_correct else '❌'}")
        print(f"    [Reasoning]         : {eval_result.reasoning}\n")
        
        results.append(eval_result)

    # 7. Final Summary
    total = len(results)
    passed = sum(1 for r in results if r.response_correct)
    print("="*50)
    print(f" 🏆 EVALUATION SUMMARY: {passed}/{total} Passed ({(passed/total)*100:.1f}%)")
    print("="*50)

if __name__ == "__main__":
    run_hardcoded_evals()
