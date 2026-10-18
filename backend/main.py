import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.amazon_retrieval import search_amazon_products
from backend.ebay_retrieval import search_ebay_products


# --------------------------------------------------
# PATHS AND M3 IMPORT
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
M3_ROOT = PROJECT_ROOT / "member3_knowledge_graph"
M3_SRC = M3_ROOT / "src"
M3_DATA = M3_ROOT / "data"

sys.path.insert(0, str(M3_SRC))

try:
    from platform_router import route_query, parse_structured_query
except ImportError as exc:
    raise ImportError(
        "Could not import route_query and parse_structured_query "
        "from member3_knowledge_graph/src/platform_router.py. "
        "Check that both functions exist."
    ) from exc


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="M3 Electronics Search API",
    description=(
        "API connecting the React frontend to the "
        "M3 knowledge graph and adaptive platform router."
    ),
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# LOAD M3 DATA
# --------------------------------------------------

GRAPH_FILE = M3_DATA / "electronics_kg_combined.json"
CROSSWALK_FILE = M3_DATA / "category_crosswalk_candidates.json"


def load_json(path: Path) -> Any:
    """Load JSON data or report a useful error."""
    if not path.exists():
        raise FileNotFoundError(
            f"Required M3 data file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_graph_nodes(graph: Any) -> list:
    """Support common JSON graph layouts."""
    if isinstance(graph, list):
        return graph

    if isinstance(graph, dict):
        for key in ("nodes", "categories", "data"):
            value = graph.get(key)
            if isinstance(value, list):
                return value

    raise ValueError(
        "Could not find a node list in electronics_kg_combined.json. "
        "Expected a list or an object containing 'nodes' or 'categories'."
    )


def extract_crosswalk(crosswalk: Any) -> Any:
    """Preserve the crosswalk structure unless a candidate list is present."""
    if isinstance(crosswalk, dict):
        for key in ("candidates", "crosswalk", "mappings", "data"):
            value = crosswalk.get(key)
            if isinstance(value, list):
                return value

    return crosswalk


try:
    GRAPH_DATA = load_json(GRAPH_FILE)
    CROSSWALK_DATA = load_json(CROSSWALK_FILE)

    CATEGORIES = extract_graph_nodes(GRAPH_DATA)
    CROSSWALK = extract_crosswalk(CROSSWALK_DATA)

    DATA_LOAD_ERROR = None

except (OSError, json.JSONDecodeError, ValueError) as exc:
    GRAPH_DATA = None
    CROSSWALK_DATA = None
    CATEGORIES = []
    CROSSWALK = []
    DATA_LOAD_ERROR = str(exc)


# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=5, ge=1, le=20)
    min_routing_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


# --------------------------------------------------
# PRODUCT CONSTRAINT FILTERING
# --------------------------------------------------

def filter_products_by_constraints(
    products: list[dict],
    attributes: dict,
) -> list[dict]:
    """
    Apply explicit price constraints to retrieved products.

    If a price limit is specified, products without a usable price
    or currency are excluded. Currency conversion is not performed.
    """
    price_min = attributes.get("price_min")
    price_max = attributes.get("price_max")
    requested_currency = attributes.get("currency")

    if price_min is None and price_max is None:
        return products

    filtered = []

    for product in products:
        raw_price = product.get("price")
        currency = product.get("currency")

        if isinstance(raw_price, dict):
            currency = raw_price.get("currency", currency)
            raw_price = raw_price.get(
                "value",
                raw_price.get("amount"),
            )

        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            continue

        if price < 0 or not currency:
            continue

        if requested_currency:
            if str(currency).upper() != str(
                requested_currency
            ).upper():
                continue

        if price_min is not None and price < float(price_min):
            continue

        if price_max is not None and price > float(price_max):
            continue

        filtered.append(product)

    return filtered


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "M3 Electronics Search API",
        "m3_imported": True,
        "graph_loaded": DATA_LOAD_ERROR is None,
        "category_count": len(CATEGORIES),
        "crosswalk_loaded": DATA_LOAD_ERROR is None,
        "amazon_catalog_exists": (
            PROJECT_ROOT
            / "member3_knowledge_graph"
            / "data"
            / "amazon_electronics_products.jsonl"
        ).exists(),
        "data_error": DATA_LOAD_ERROR,
    }


# --------------------------------------------------
# SEARCH AND ROUTING
# --------------------------------------------------

@app.post("/api/search")
def search_products(request: SearchRequest):
    if DATA_LOAD_ERROR:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load M3 data: {DATA_LOAD_ERROR}",
        )

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="The search query cannot be empty.",
        )

    try:
        # Prepare categories for the M3 router.
        normalized_categories = []

        for node in CATEGORIES:
            if not isinstance(node, dict):
                continue

            category_name = (
                node.get("category_name")
                or node.get("name")
                or node.get("label")
                or node.get("title")
            )

            category_path = (
                node.get("category_path")
                or node.get("path")
                or category_name
            )

            if not category_name:
                continue

            normalized_categories.append({
                **node,
                "category_id": str(
                    node.get("category_id")
                    or node.get("id")
                    or ""
                ),
                "category_name": str(category_name),
                "category_path": str(category_path),
                "depth": node.get(
                    "depth",
                    len(str(category_path).split(">")),
                ),
            })

        # Step 1: Parse structured query constraints.
        structured_query = parse_structured_query(query)

        if not isinstance(structured_query, dict):
            raise ValueError(
                "parse_structured_query() did not return a dictionary."
            )

        attributes = structured_query.get("attributes", {})

        if not isinstance(attributes, dict):
            attributes = {}

        # Step 2: Route the query through M3.
        response = route_query(
            query=query,
            categories=normalized_categories,
            crosswalk=CROSSWALK,
            top_k=request.top_k,
            min_routing_score=request.min_routing_score,
        )

        if not isinstance(response, dict):
            raise ValueError(
                "route_query() did not return a dictionary."
            )

        response = dict(response)
        response["query"] = query
        response["products"] = []
        response["retrieval_errors"] = []
        response["retrieval_status"] = "not_attempted"
        response["query_attributes"] = attributes

        # Read routing decisions.
        ready_platforms = response.get(
            "retrieval_ready_platforms", []
        )
        selected_platforms = response.get(
            "selected_platforms", []
        )

        all_products = []
        retrieval_attempted = False

        # Step 3: Retrieve live eBay products.
        if "ebay" in ready_platforms:
            retrieval_attempted = True

            try:
                ebay_products = search_ebay_products(
                    query=query,
                    limit=min(request.top_k * 2, 20),
                )

                ebay_products = filter_products_by_constraints(
                    ebay_products,
                    attributes,
                )

                all_products.extend(ebay_products)

            except Exception as exc:
                response["retrieval_errors"].append({
                    "platform": "ebay",
                    "message": str(exc),
                })

        # Step 4: Retrieve products from the local Amazon catalog.
        # These are historical dataset records, not live listings.
        if "amazon" in selected_platforms:
            retrieval_attempted = True

            try:
                amazon_products = search_amazon_products(
                    query=query,
                    limit=request.top_k,
                    attributes=attributes,
                )

                # Apply the same price constraints as a safeguard.
                amazon_products = filter_products_by_constraints(
                    amazon_products,
                    attributes,
                )

                all_products.extend(amazon_products)

            except Exception as exc:
                response["retrieval_errors"].append({
                    "platform": "amazon",
                    "message": str(exc),
                })

        # Step 5: Return combined marketplace results.
        response["products"] = all_products

        if all_products:
            response["retrieval_status"] = "success"
        elif response["retrieval_errors"]:
            response["retrieval_status"] = "failed"
        elif retrieval_attempted:
            response["retrieval_status"] = "no_results"
        elif selected_platforms:
            response["retrieval_status"] = "no_supported_retriever"
        else:
            response["retrieval_status"] = "no_eligible_platform"

        return jsonable_encoder(response)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "M3 routing failed. Check the backend terminal. "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc
