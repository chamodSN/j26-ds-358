import { useRef, useState } from "react";
import { Heart } from "lucide-react";
import SearchBar from "./components/SearchBar";
import ClarifyFlow from "./components/ClarifyFlow";
import ProductCard from "./components/ProductCard";
import ProductDetail from "./components/ProductDetail";
import { queries, exampleQueries } from "./data/mockProducts";
import { ambiguousQueries, resolveAmbiguous } from "./data/ambiguousQueries";

function LoadingState() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 px-6 py-24 text-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-amber-500" />
      <p className="text-sm text-ink-soft">Finding the best matches…</p>
    </div>
  );
}

export default function App() {
  const [query, setQuery] = useState(exampleQueries[0]);
  const [showFairPrice, setShowFairPrice] = useState(true);
  const [sortBy, setSortBy] = useState("match");
  const [view, setView] = useState("results"); // results | loading | clarify | detail
  const [activeQuery, setActiveQuery] = useState(exampleQueries[0]);
  const [brandFilter, setBrandFilter] = useState(null);
  const [contextLabel, setContextLabel] = useState(null);
  const [clarifyTrigger, setClarifyTrigger] = useState(null);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [saved, setSaved] = useState(new Set());
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  function showToast(message) {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
  }

  function toggleSave(id) {
    setSaved((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        showToast("Removed from saved items");
      } else {
        next.add(id);
        showToast("Saved for later");
      }
      return next;
    });
  }

  function startSearch(datasetKey, brand = null, label = null) {
    setBrandFilter(brand);
    setContextLabel(label);
    setView("loading");
    setTimeout(() => {
      setActiveQuery(datasetKey);
      setView("results");
    }, 550);
  }

  function handleSearch() {
    const q = query.trim();
    const lower = q.toLowerCase();
    if (ambiguousQueries[lower]) {
      setClarifyTrigger(lower);
      setView("clarify");
      return;
    }
    const datasetKey = queries[q] ? q : exampleQueries[0];
    startSearch(datasetKey);
  }

  function handleClarifyComplete(answers) {
    const { datasetKey, brand, contextLabel: label } = resolveAmbiguous(clarifyTrigger, answers);
    startSearch(datasetKey, brand, label);
  }

  function openDetail(product) {
    setSelectedProduct(product);
    setView("detail");
  }

  const baseProducts = queries[activeQuery]?.products ?? [];
  const brandMatches = brandFilter
    ? baseProducts.filter((p) => p.brand.toLowerCase() === brandFilter.toLowerCase())
    : baseProducts;
  const brandMismatch = brandFilter && brandMatches.length === 0;
  const shownProducts = brandMismatch ? baseProducts : brandMatches;

  const sortedProducts = [...shownProducts].sort((a, b) => {
    if (sortBy === "price-asc") return a.bestPrice.amount - b.bestPrice.amount;
    if (sortBy === "price-desc") return b.bestPrice.amount - a.bestPrice.amount;
    return a.rank - b.rank;
  });

  const related = selectedProduct
    ? baseProducts.filter((p) => p.id !== selectedProduct.id).slice(0, 3)
    : [];

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <span className="font-display text-xl text-ink">Vero</span>
          <span className="flex items-center gap-1.5 text-sm text-ink-soft">
            <Heart className="h-4 w-4 text-amber-500" fill={saved.size ? "currentColor" : "none"} />
            Saved ({saved.size})
          </span>
        </div>
      </header>

      {view !== "detail" && (
        <SearchBar
          query={query}
          setQuery={setQuery}
          onSearch={handleSearch}
          examples={exampleQueries}
        />
      )}

      {view === "loading" && <LoadingState />}

      {view === "clarify" && clarifyTrigger && (
        <ClarifyFlow
          trigger={query}
          questions={ambiguousQueries[clarifyTrigger].questions}
          onComplete={handleClarifyComplete}
        />
      )}

      {view === "results" && (
        <main className="mx-auto max-w-3xl px-6 py-10">
          {contextLabel && (
            <p className="mb-3 text-sm text-ink-faint">
              Showing results for <span className="font-medium text-ink">{contextLabel}</span>
            </p>
          )}
          {brandMismatch && (
            <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-600">
              No exact matches for {brandFilter} in this range — showing the closest options instead.
            </p>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-soft">
              <span className="font-medium text-ink">{sortedProducts.length} products</span> found
            </p>

            <div className="flex flex-wrap items-center gap-4">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink-soft"
              >
                <option value="match">Best match</option>
                <option value="price-asc">Price: low to high</option>
                <option value="price-desc">Price: high to low</option>
              </select>

              <label className="flex items-center gap-2 text-sm text-ink-soft">
                Fair price
                <button
                  type="button"
                  role="switch"
                  aria-checked={showFairPrice}
                  onClick={() => setShowFairPrice(!showFairPrice)}
                  className={`relative h-5 w-9 rounded-full transition-colors ${showFairPrice ? "bg-moss-500" : "bg-line"
                    }`}
                >
                  <span
                    className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${showFairPrice ? "translate-x-[18px]" : "translate-x-0.5"
                      }`}
                  />
                </button>
              </label>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {sortedProducts.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                showFairPrice={showFairPrice}
                isSaved={saved.has(p.id)}
                onToggleSave={toggleSave}
                onOpen={openDetail}
              />
            ))}
          </div>
        </main>
      )}

      {view === "detail" && selectedProduct && (
        <ProductDetail
          product={selectedProduct}
          related={related}
          isSaved={saved.has(selectedProduct.id)}
          onToggleSave={toggleSave}
          onBack={() => setView("results")}
          onOpenRelated={openDetail}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-ink px-4 py-2 text-sm text-paper shadow-lg">
          {toast}
        </div>
      )}

      <footer className="border-t border-line px-6 py-8 text-center text-xs text-ink-faint">
        Prices shown are illustrative for this preview. "Visit store" links go to a real search
        on the actual platform.
      </footer>
    </div>
  );
}