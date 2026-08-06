├── member2_entity_resolution/      # Watareka's module
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api.py
│   ├── __init__.py
│   ├── src/
│   │   ├── __init__.py
│   │   ├── blocker.py              # Embedding-based blocking
│   │   ├── matcher.py              # Pairwise entity matching model
│   │   └── harmonizer.py          # Schema harmonization
│   ├── data/
│   │   └── .gitkeep
│   ├── models/
│   │   └── .gitkeep
│   ├── notebooks/
│   │   └── .gitkeep
│   └── tests/
│       ├── __init__.py
│       └── test_entity_resolution.py