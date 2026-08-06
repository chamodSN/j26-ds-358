├── member3_knowledge_graph/        # Prarthana's module
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api.py
│   ├── __init__.py
│   ├── src/
│   │   ├── __init__.py
│   │   ├── graph_builder.py        # Builds KG from Google Product Taxonomy
│   │   ├── platform_router.py      # Decides which platforms to query
│   │   └── staleness_tracker.py    # Per-category decay rate
│   ├── data/
│   │   └── .gitkeep
│   ├── notebooks/
│   │   └── .gitkeep
│   └── tests/
│       ├── __init__.py
│       └── test_kg.py