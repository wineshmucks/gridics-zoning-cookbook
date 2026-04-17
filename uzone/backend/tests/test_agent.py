import os
from typing import Any
from dotenv import load_dotenv

# 1. Load environment variables
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
load_dotenv(dotenv_path=env_path, verbose=True)

from app.agents.customer_zoning_agent import (
    customer_zoning_team,
    code_researcher_agent,
    property_specialist_agent
)

# Approximate Gemini 1.5/2.5 Flash Pricing (Per 1 Million Tokens)
# Adjust these values based on your exact Google Cloud billing tier
COST_PER_1M_INPUT = 0.075 
COST_PER_1M_OUTPUT = 0.30

class TelemetryTracker:
    """Helper class to track tokens, time, and costs across a session."""
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_time_seconds = 0.0

    def process_turn(self, metrics: Any) -> dict:
        # Agno v2 returns a RunMetrics object, so we use getattr instead of .get()
        in_tokens = getattr(metrics, "input_tokens", 0) or 0
        out_tokens = getattr(metrics, "output_tokens", 0) or 0
        turn_time = getattr(metrics, "time", 0.0) or 0.0

        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self.total_time_seconds += turn_time

        cost = (in_tokens / 1_000_000 * COST_PER_1M_INPUT) + (out_tokens / 1_000_000 * COST_PER_1M_OUTPUT)
        
        return {
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "time": turn_time,
            "cost": cost
        }

    def print_summary(self):
        total_cost = (self.total_input_tokens / 1_000_000 * COST_PER_1M_INPUT) + (self.total_output_tokens / 1_000_000 * COST_PER_1M_OUTPUT)
        print("\n" + "="*50)
        print(" 📊 SESSION TELEMETRY SUMMARY")
        print("="*50)
        print(f"Total Input Tokens  : {self.total_input_tokens:,}")
        print(f"Total Output Tokens : {self.total_output_tokens:,}")
        print(f"Total Tokens        : {self.total_input_tokens + self.total_output_tokens:,}")
        print(f"Total Time          : {self.total_time_seconds:.2f} seconds")
        print(f"Estimated Cost      : ${total_cost:.5f}")
        print("="*50 + "\n")

def run_simulation():
    # 2. Inject the Jurisdiction / Client ID
    # Pull from .env (e.g., TEST_CLIENT_ID="org_12345") or fallback to a string
    client_id = os.getenv("TEST_CLIENT_ID", "your_default_client_id_here")
    print(f"[*] Initializing Session for Client ID: {client_id}")
    
    # Agno passes dependencies to the RunContext. We inject it into the team and sub-agents here.
    dependencies = {"client_id": client_id}
    customer_zoning_team.dependencies = dependencies
    code_researcher_agent.dependencies = dependencies
    property_specialist_agent.dependencies = dependencies

    print("========================================")
    print("  ZONING AGENT TEAM SIMULATION")
    print("========================================\n")
    
    session_id = "test_simulation_session_001"
    tracker = TelemetryTracker()
    
    turns = [
        "What are the general rules for fences in commercial zones?",
        "How high can I build a fence at 3148 Mary St?",
        "Yes, in Miami FL 33133.",
        "What about adding a pool to that same lot?"
    ]
    
    for i, query in enumerate(turns, 1):
        print(f"USER (Turn {i}): {query}")
        
        # Run the agent
        response = customer_zoning_team.run(query, session_id=session_id)
        print(f"\nAGENT: {response.content}")
        
        # Extract metrics and update tracker
        # Agno populates response.metrics with token and latency counts
        metrics = getattr(response, "metrics", {})
        turn_stats = tracker.process_turn(metrics)
        
        # Print Turn Telemetry
        print(f"\n[⏱️ Turn {i} Stats | "
              f"In: {turn_stats['input_tokens']:,} | "
              f"Out: {turn_stats['output_tokens']:,} | "
              f"Time: {turn_stats['time']:.2f}s | "
              f"Cost: ${turn_stats['cost']:.5f}]")
        print("-" * 60 + "\n")

    # Output the final summary and state
    tracker.print_summary()
    print("FINAL SESSION STATE:")
    print(customer_zoning_team.session_state)
    print("========================================")

if __name__ == "__main__":
    run_simulation()