horizon-travel-ai/
├── .env.example            # Template for OPENROUTER_API_KEY, etc.
├── README.md               # Overview of PRD v2.0 and setup instructions
├── requirements.txt        # Core dependencies (Streamlit, Pydantic, OpenAI/LangChain)
├── app.py                  # Streamlit entry point (The "View" layer)
├── src/
│   ├── __init__.py
│   ├── orchestrator.py     # Root Orchestrator (The "Brain")
│   ├── agents/             # Specialist Agent definitions
│   │   ├── __init__.py
│   │   ├── base.py         # BaseAgent class
│   │   ├── concierge.py    # Conversational flow
│   │   ├── extractor.py    # Preference/Slot-filling logic
│   │   ├── architect.py    # Itinerary planning logic
│   │   └── dna_learner.py  # Profile update logic
│   ├── models/             # Pydantic state schemas
│   │   ├── __init__.py
│   │   ├── state.py        # Shared TravelState definition
│   │   └── preferences.py  # Structured preference model
│   └── tools/              # Simulated tools/mock APIs
│       ├── __init__.py
│       └── mock_data.py    # Deterministic mock functions
└── tests/                  # Unit tests for agents/orchestrator
    ├── test_extraction.py
    └── test_orchestration.py
