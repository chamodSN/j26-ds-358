├── member1_retrieval/              # Nethmina's module
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api.py                      # FastAPI entry point
│   ├── __init__.py
│   ├── src/
│   │   ├── __init__.py
│   │   ├── classifier.py           # Query intent classifier (Exact/Semantic/Hybrid)
│   │   ├── hyde_generator.py       # Fine-tuned T5 spec generator
│   │   ├── retriever.py            # BM25 + FAISS dense retrieval
│   │   └── router.py               # Confidence-weighted blend
│   ├── data/                       # gitignored — put ESCI data here
│   │   └── .gitkeep
│   ├── models/                     # gitignored — put trained model checkpoints here
│   │   └── .gitkeep
│   ├── notebooks/                  # Jupyter notebooks for experiments
│   │   └── .gitkeep
│   └── tests/
│       ├── __init__.py
│       └── test_retrieval.py