import { useState } from 'react';
import {
  Search,
  GitBranch,
  Sparkles,
  Headphones,
  Laptop,
  Network,
  Camera,
  Cable,
  SlidersHorizontal,
  Store,
  ShieldCheck,
  Zap,
  Clock3,
  CheckCircle2,
  LoaderCircle,
  ArrowRight,
  CircleHelp,
  Filter,
  ExternalLink,
  ShoppingBag,
  ImageOff,
} from 'lucide-react';

const API =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

const examples = [
  { label: 'Wireless headphones', Icon: Headphones },
  { label: 'Gaming keyboard', Icon: Laptop },
  { label: 'Wi-Fi router', Icon: Network },
  { label: 'Digital camera', Icon: Camera },
  { label: 'Phone charger', Icon: Cable },
];

const platformName = (platform) =>
  ({
    ebay: 'eBay',
    amazon: 'Amazon',
    aliexpress: 'AliExpress',
  }[String(platform || '').toLowerCase()] || platform || 'Marketplace');

const percent = (value) =>
  typeof value === 'number'
    ? `${Math.round(value * 100)}%`
    : '—';

const getProducts = (data) => {
  const value =
    data?.products ??
    data?.product_results ??
    data?.ebay_results ??
    data?.retrieved_products ??
    [];

  return Array.isArray(value) ? value : [];
};

const getProductImage = (product) =>
  product?.image_url ||
  product?.imageUrl ||
  product?.image?.imageUrl ||
  product?.thumbnail ||
  (typeof product?.image === 'string' ? product.image : '') ||
  '';

const getProductUrl = (product) =>
  product?.product_url ||
  product?.itemWebUrl ||
  product?.item_url ||
  product?.url ||
  '';

const getProductPrice = (product) => {
  const price = product?.price;

  if (price && typeof price === 'object') {
    const amount = price.value ?? price.amount;
    const currency = price.currency ?? product?.currency ?? '';

    return amount != null
      ? `${currency} ${amount}`.trim()
      : 'Price unavailable';
  }

  if (price != null && price !== '') {
    return `${product?.currency || ''} ${price}`.trim();
  }

  return 'Price unavailable';
};

const getProductDetails = (product) => {
  const details = [];

  if (product?.condition) {
    details.push(`Condition: ${product.condition}`);
  }

  if (product?.brand) {
    details.push(`Brand: ${product.brand}`);
  }

  if (product?.model) {
    details.push(`Model: ${product.model}`);
  }

  const shipping =
    product?.shipping_cost ?? product?.shippingCost;

  if (shipping != null && shipping !== '') {
    details.push(`Shipping: ${shipping}`);
  }

  if (Array.isArray(product?.localizedAspects)) {
    product.localizedAspects.slice(0, 3).forEach((aspect) => {
      if (aspect?.name && aspect?.value) {
        details.push(`${aspect.name}: ${aspect.value}`);
      }
    });
  }

  if (Array.isArray(product?.specifications)) {
    product.specifications.slice(0, 3).forEach((item) => {
      if (typeof item === 'string') {
        details.push(item);
      } else if (item?.name && item?.value) {
        details.push(`${item.name}: ${item.value}`);
      }
    });
  }

  return [...new Set(details)].slice(0, 4);
};

function ProductCard({ product }) {
  const title =
    product?.title ||
    product?.name ||
    'Marketplace product';

  const imageUrl = getProductImage(product);
  const productUrl = getProductUrl(product);
  const platform =
    product?.platform ||
    product?.marketplace ||
    'ebay';

  const details = getProductDetails(product);

  return (
    <article className="product-card">
      <a
        className="product-image-link"
        href={productUrl || undefined}
        target={productUrl ? '_blank' : undefined}
        rel={productUrl ? 'noreferrer' : undefined}
        aria-label={`Open ${title} on ${platformName(platform)}`}
        onClick={
          !productUrl
            ? (event) => event.preventDefault()
            : undefined
        }
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={title}
            loading="lazy"
            onError={(event) => {
              event.currentTarget.style.display = 'none';
            }}
          />
        ) : (
          <span className="product-image-fallback">
            <ImageOff size={28} />
            <small>No image supplied</small>
          </span>
        )}

        <span
          className={`product-platform platform-${String(
            platform
          ).toLowerCase()}`}
        >
          <Store size={12} />
          {platformName(platform)}
        </span>
      </a>

      <div className="product-card-body">
        <h4 title={title}>{title}</h4>

        <div className="product-price">
          {getProductPrice(product)}
        </div>

        {product?.shortDescription || product?.description ? (
          <p className="product-description">
            {product.shortDescription || product.description}
          </p>
        ) : null}

        {details.length > 0 ? (
          <ul className="product-details">
            {details.map((detail, index) => (
              <li key={`${detail}-${index}`}>{detail}</li>
            ))}
          </ul>
        ) : (
          <p className="product-description">
            Additional specifications were not supplied by the listing.
          </p>
        )}

        {productUrl ? (
          <a
            className="product-open-link"
            href={productUrl}
            target="_blank"
            rel="noreferrer"
          >
            View original listing
            <ExternalLink size={14} />
          </a>
        ) : (
          <span className="product-no-link">
            <CircleHelp size={13} />
            Listing URL unavailable
          </span>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [backend, setBackend] = useState('unknown');
  const [threshold, setThreshold] = useState('0.60');
  const [topK, setTopK] = useState('5');
  const [details, setDetails] = useState(true);

  async function searchProducts(value = query) {
    const cleanQuery = value.trim();

    if (!cleanQuery) {
      setError('Enter a product query or choose an example search.');
      return;
    }

    setQuery(cleanQuery);
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await fetch(`${API}/api/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: cleanQuery,
          top_k: Number(topK),
          min_routing_score: Number(threshold),
        }),
      });

      if (!response.ok) {
        throw new Error(
          `API returned HTTP ${response.status}: ${await response.text()}`
        );
      }

      const data = await response.json();

      setResult(data);
      setBackend('online');
    } catch (err) {
      setBackend('offline');
      setError(
        `Could not connect to ${API}. Check the FastAPI backend. Details: ${err.message}`
      );
    } finally {
      setLoading(false);
    }
  }

  const matches = result?.category_matches || [];
  const selected = result?.selected_platforms || [];
  const ready = result?.retrieval_ready_platforms || [];
  const scores = result?.platform_routing_scores || {};
  const freshness = result?.observation_freshness || {};
  const reasons = result?.routing_reasons || result?.reasons || [];
  const products = getProducts(result);

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#">
          <span className="brand-icon">
            <GitBranch size={19} />
          </span>
          <b>orbit<span>.</span></b>
          <i />
          <small>RESEARCH PROTOTYPE</small>
        </a>

        <div className="connection">
          <span className={`dot ${backend}`} />
          {backend === 'online'
            ? 'M3 backend connected'
            : backend === 'offline'
              ? 'Backend offline'
              : 'M3 routing interface'}
          <span className="version">M3 · v0.1</span>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow">
            <Sparkles size={14} />
            KNOWLEDGE-GUIDED PRODUCT DISCOVERY
          </div>

          <h1>
            Find the right tech.
            <br />
            <em>Across marketplaces.</em>
          </h1>

          <p>
            Electronics search with adaptive platform routing powered by a
            product taxonomy, category mappings, and temporal freshness
            signals.
          </p>

          <form
            className="search"
            onSubmit={(event) => {
              event.preventDefault();
              searchProducts();
            }}
          >
            <Search size={20} />

            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Try wireless headphones or gaming keyboard..."
              aria-label="Search electronics"
            />

            <button type="submit" disabled={loading}>
              {loading ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Search size={17} />
              )}
              {loading ? 'Searching...' : 'Search'}
            </button>
          </form>

          <div className="examples">
            <span>TRY A SEARCH</span>

            {examples.map(({ label, Icon }) => (
              <button
                key={label}
                type="button"
                onClick={() => searchProducts(label)}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
        </section>

        {error && (
          <div className="error" role="alert">
            <CircleHelp size={18} />

            <div>
              <b>Search couldn't complete</b>
              <p>{error}</p>
            </div>

            <button
              onClick={() => setError('')}
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        <section className="workspace">
          <aside className="sidebar">
            <h2>
              <SlidersHorizontal size={16} />
              Routing controls
            </h2>

            <p className="muted">
              Tune M3 routing. These settings affect platform selection,
              not product ranking.
            </p>

            <label className="field-label">
              Minimum routing score
              <strong>{threshold}</strong>
            </label>

            <input
              className="range"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
            />

            <div className="range-labels">
              <span>More coverage</span>
              <span>More selective</span>
            </div>

            <label className="field-label" htmlFor="topk">
              Category matches
            </label>

            <select
              id="topk"
              value={topK}
              onChange={(event) => setTopK(event.target.value)}
            >
              <option value="3">Top 3 matches</option>
              <option value="5">Top 5 matches</option>
              <option value="10">Top 10 matches</option>
            </select>

            <hr />

            <h2>
              <Store size={16} />
              Platform status
            </h2>

            <div className="platform-status">
              <span className="logo ebay">e</span>
              <div>
                <b>eBay</b>
                <small>Browse API configured</small>
              </div>
              <label className="tag ready">Live-ready</label>
            </div>

            <div className="platform-status">
              <span className="logo amazon">a</span>
              <div>
                <b>Amazon</b>
                <small>Taxonomy available</small>
              </div>
              <label className="tag candidate">Candidate</label>
            </div>

            <div className="platform-status">
              <span className="logo ali">A</span>
              <div>
                <b>AliExpress</b>
                <small>Not integrated</small>
              </div>
              <label className="tag disabled">Disabled</label>
            </div>

            <div className="sidebar-note">
              <ShieldCheck size={17} />
              <p>
                <b>Separation by design</b>
                <br />
                A platform can be selected by routing without being ready
                for live retrieval.
              </p>
            </div>
          </aside>

          <section className="results">
            {!result && !loading ? (
              <div className="empty">
                <div className="empty-icon">
                  <GitBranch size={30} />
                </div>

                <h2>Your search starts here</h2>

                <p>
                  Enter an electronics query to see M3's category matching
                  and platform-routing decision.
                </p>

                <div className="feature-row">
                  <span>
                    <CheckCircle2 size={14} /> Taxonomy matching
                  </span>
                  <span>
                    <CheckCircle2 size={14} /> Platform selection
                  </span>
                  <span>
                    <CheckCircle2 size={14} /> Freshness signals
                  </span>
                </div>
              </div>
            ) : loading ? (
              <div className="empty">
                <LoaderCircle className="spin loading-icon" size={32} />
                <h2>Searching marketplaces</h2>
                <p>
                  Matching taxonomy categories, evaluating platform
                  eligibility, and loading available results...
                </p>
              </div>
            ) : (
              <>
                <div className="results-title">
                  <div>
                    <div className="eyebrow left">
                      <CheckCircle2 size={13} />
                      SEARCH COMPLETE
                    </div>

                    <h2>Search intelligence</h2>

                    <p>
                      Decision summary for{' '}
                      <b>“{result.query || query}”</b>
                    </p>
                  </div>

                  <button
                    className="subtle-button"
                    onClick={() => setDetails(!details)}
                  >
                    <Filter size={14} />
                    {details ? 'Hide details' : 'Show details'}
                  </button>
                </div>

                <div className="metrics">
                  <div>
                    <span className="metric-icon purple">
                      <GitBranch size={17} />
                    </span>
                    <small>Selected candidates</small>
                    <strong>{selected.length}</strong>
                    <label>Routing decision</label>
                  </div>

                  <div>
                    <span className="metric-icon green">
                      <Zap size={17} />
                    </span>
                    <small>Live-ready platforms</small>
                    <strong>{ready.length}</strong>
                    <label>Available to retrieve</label>
                  </div>

                  <div>
                    <span className="metric-icon blue">
                      <Network size={17} />
                    </span>
                    <small>Category matches</small>
                    <strong>{matches.length}</strong>
                    <label>Taxonomy candidates</label>
                  </div>
                </div>

                {/* LIVE PRODUCT RESULTS */}
                <article className="card product-results-card">
                  <div className="card-heading">
                    <div>
                      <small>01 / LIVE PRODUCT RETRIEVAL</small>
                      <h3>Marketplace results</h3>
                    </div>

                    <span className="count">
                      {products.length} products
                    </span>
                  </div>

                  {products.length > 0 ? (
                    <div className="product-grid">
                      {products.map((product, index) => (
                        <ProductCard
                          key={
                            product?.product_id ||
                            product?.itemId ||
                            product?.id ||
                            `${product?.title || 'product'}-${index}`
                          }
                          product={product}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="products-empty">
                      <span className="products-empty-icon">
                        <ShoppingBag size={22} />
                      </span>

                      <div>
                        <b>No live product listings returned</b>
                        <p>
                          M3 routing completed, but the API response contains
                          no product listings. The backend needs to retrieve
                          products from eBay and return them in the
                          <code> products </code> array.
                        </p>
                      </div>
                    </div>
                  )}
                </article>

                {/* CATEGORY MATCHES */}
                <article className="card">
                  <div className="card-heading">
                    <div>
                      <small>02 / TAXONOMY</small>
                      <h3>Matched categories</h3>
                    </div>

                    <span className="count">
                      {matches.length} matches
                    </span>
                  </div>

                  {matches.length ? (
                    matches.map((match, index) => (
                      <div
                        className="category-row"
                        key={`${match.path || match.name}-${index}`}
                      >
                        <span className="rank">
                          {String(index + 1).padStart(2, '0')}
                        </span>

                        <div className="category-name">
                          <b>
                            {match.name ||
                              match.category ||
                              match.category_name ||
                              'Category match'}
                          </b>

                          <small>
                            {match.path ||
                              match.category_path ||
                              'Taxonomy path unavailable'}
                          </small>
                        </div>

                        <div className="match-score">
                          <b>
                            {typeof match.score === 'number'
                              ? match.score.toFixed(2)
                              : '—'}
                          </b>
                          <small>match score</small>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="muted">
                      No category matches returned.
                    </p>
                  )}
                </article>

                {/* PLATFORM ROUTING */}
                <article className="card">
                  <div className="card-heading">
                    <div>
                      <small>03 / PLATFORM ROUTING</small>
                      <h3>Candidate vs. live retrieval</h3>
                    </div>

                    <span className="count">
                      {selected.length} selected
                    </span>
                  </div>

                  <div className="platform-grid">
                    <div className="platform-box">
                      <h4>
                        <GitBranch size={15} />
                        Selected candidates
                      </h4>

                      <p>
                        Platforms M3 considers suitable for this query.
                      </p>

                      {selected.length ? (
                        selected.map((platform) => (
                          <div className="route-row" key={platform}>
                            <span className={`logo ${platform}`}>
                              {platform === 'ebay'
                                ? 'e'
                                : platform === 'amazon'
                                  ? 'a'
                                  : 'A'}
                            </span>

                            <div>
                              <b>{platformName(platform)}</b>
                              <small>
                                Routing score:{' '}
                                {typeof scores[platform]?.routing_score ===
                                'number'
                                  ? percent(scores[platform].routing_score)
                                  : 'Not provided'}
                              </small>
                            </div>

                            <label className="tag candidate">
                              Selected
                            </label>
                          </div>
                        ))
                      ) : (
                        <p className="muted">
                          No platforms passed routing policy.
                        </p>
                      )}
                    </div>

                    <div className="platform-box">
                      <h4 className="green-text">
                        <Zap size={15} />
                        Live retrieval targets
                      </h4>

                      <p>
                        Only these platforms should be called by the
                        retrieval layer.
                      </p>

                      {ready.length ? (
                        ready.map((platform) => (
                          <div className="route-row" key={platform}>
                            <span className={`logo ${platform}`}>
                              {platform === 'ebay'
                                ? 'e'
                                : platform === 'amazon'
                                  ? 'a'
                                  : 'A'}
                            </span>

                            <div>
                              <b>{platformName(platform)}</b>
                              <small>Integration available</small>
                            </div>

                            <label className="tag ready">
                              <CheckCircle2 size={11} />
                              Ready
                            </label>
                          </div>
                        ))
                      ) : (
                        <p className="muted">
                          No selected platforms are currently live-ready.
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="guardrail">
                    <ShieldCheck size={17} />
                    <p>
                      <b>Pipeline guardrail:</b> M1 should retrieve only from{' '}
                      <code>retrieval_ready_platforms</code>, never all{' '}
                      <code>selected_platforms</code>. Amazon may remain a
                      routing candidate while live retrieval is pending.
                    </p>
                  </div>
                </article>

                {/* ROUTING EXPLANATION */}
                {details && (
                  <article className="card">
                    <div className="card-heading">
                      <div>
                        <small>04 / EXPLANATION</small>
                        <h3>Routing explanation</h3>
                      </div>
                      <Clock3 size={17} />
                    </div>

                    <ul className="reasons">
                      {(reasons.length
                        ? reasons
                        : [
                            'Routing uses the matched electronics taxonomy and configured category policy.',
                            'Live retrieval readiness is distinct from routing candidacy.',
                          ]
                      ).map((reason, index) => (
                        <li key={index}>
                          <CheckCircle2 size={15} />
                          {typeof reason === 'string'
                            ? reason
                            : reason.description ||
                              reason.reason ||
                              JSON.stringify(reason)}
                        </li>
                      ))}
                    </ul>

                    <div className="freshness">
                      <h4>
                        <Clock3 size={15} />
                        Observation freshness
                      </h4>

                      <p>
                        Freshness describes when M3 last observed candidate
                        information. It does not prove the marketplace
                        listing's last-update time.
                      </p>

                      {Object.keys(freshness).length ? (
                        Object.entries(freshness).map(
                          ([platform, value]) => (
                            <span key={platform}>
                              <b>{platformName(platform)}</b>{' '}
                              {typeof value === 'object'
                                ? value.freshness_score != null
                                  ? percent(value.freshness_score)
                                  : value.status || 'Unknown'
                                : String(value)}
                            </span>
                          )
                        )
                      ) : (
                        <small>
                          No observation timestamps supplied · freshness
                          unknown
                        </small>
                      )}
                    </div>
                  </article>
                )}

                <div className="pipeline">
                  <span className="active">M3 · Platform routing</span>
                  <ArrowRight size={14} />
                  <span>M1 · Retrieval</span>
                  <ArrowRight size={14} />
                  <span>M2 · Entity resolution</span>
                  <ArrowRight size={14} />
                  <span>M4 · Reranking</span>
                </div>
              </>
            )}
          </section>
        </section>
      </main>

      <footer>
        <span>ORBIT / ADAPTIVE MARKETPLACE ROUTING</span>
        <span>Research prototype · Results may be incomplete</span>
        <span>React + Vite</span>
      </footer>
    </div>
  );
}