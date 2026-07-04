# tests/test_orchestrator.py
from src.orchestrator import RootOrchestrator
from src.models.state import TravelState

def test_orchestration_loop():
    orchestrator = RootOrchestrator()
    state = TravelState(session_id="test")
    # Verify state initializes and triggers Concierge
    assert state.active_agent == "Concierge"
