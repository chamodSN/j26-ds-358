from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.api import service
from app.api.demo_data import DEMO_LISTINGS

app = FastAPI(title="Cross-platform entity resolution & schema harmonization", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


class Listing(BaseModel):
    id: str
    source: str = "unknown"
    title: str
    attributes: dict[str, str] = {}


class ResolveRequest(BaseModel):
    listings: list[Listing] = Field(min_length=2, max_length=300)
    use_llm: bool = True


@app.get("/health")
def health():
    s = service.schema()
    return dict(status="ok", schema_version=s["version"], schema_attributes=s["n_attributes"],
                lo=service.LO, hi=service.HI, max_llm_calls=service.MAX_LLM_CALLS)


@app.get("/demo")
def demo():
    return dict(listings=DEMO_LISTINGS)


@app.post("/resolve")
def resolve(req: ResolveRequest):
    try:
        return service.resolve([l.model_dump() for l in req.listings], use_llm=req.use_llm)
    except FileNotFoundError as e:
        raise HTTPException(500, f"missing file: {e}")