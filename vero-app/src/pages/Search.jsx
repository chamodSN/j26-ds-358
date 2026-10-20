import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { RefreshCw, Search as SearchIcon } from "lucide-react";
import SearchBar from "../components/SearchBar";
import FiltersBar from "../components/FiltersBar";
import ProductGrid from "../components/ProductGrid";
import ProductSkeleton from "../components/ProductSkeleton";
import PipelineBadge from "../components/PipelineBadge";
import EmptyState from "../components/EmptyState";
import CountUp from "../components/CountUp";
import { useSaved } from "../hooks/useSaved";
import { api } from "../utils/api";

const PAGE = 24;
const MAX = 60;

export default function Search() {
    const [params, setParams] = useSearchParams();
    const q = params.get("q") ?? "";
    const filters = {
        category: params.get("category") ?? "",
        condition: params.get("condition") ?? "",
        min: params.get("min") ?? "",
        max: params.get("max") ?? "",
        sort: params.get("sort") ?? "best",
        limit: Math.min(Number(params.get("limit")) || PAGE, MAX),
    };

    const { ids, toggle } = useSaved();
    const query = useQuery({
        queryKey: ["search", q, filters],
        queryFn: ({ signal }) => api.search({ q, ...filters }, signal),
        enabled: q.trim().length > 0,
        placeholderData: keepPreviousData,
    });

    // Change some URL params. Changing any filter resets "show more".
    function update(patch) {
        const next = new URLSearchParams(params);
        Object.entries(patch).forEach(([k, v]) => {
            if (v === "" || v == null || (k === "sort" && v === "best")) next.delete(k);
            else next.set(k, String(v));
        });
        if (!("limit" in patch)) next.delete("limit");
        setParams(next, { replace: false });
    }

    const data = query.data;
    const loadingFirst = query.isLoading;

    return (
        <div className="mx-auto max-w-6xl px-5 pb-10 pt-8">
            <div className="sticky top-16 z-30 -mx-5 bg-ink-950/80 px-5 py-3 backdrop-blur-md">
                <SearchBar key={q} defaultValue={q} onSubmit={(text) => update({ q: text })} />
            </div>

            <div className="mt-5">
                <FiltersBar filters={filters} onChange={update} />
            </div>

            {!q.trim() && (
                <EmptyState icon={<SearchIcon className="h-6 w-6" />} title="What are you looking for?" text="Type a product above, like 'iphone 13 128gb' or 'gaming laptop'." />
            )}

            {q.trim() && (
                <>
                    <div className="mt-8 flex flex-wrap items-end justify-between gap-4">
                        <div>
                            <h1 className="font-display text-3xl font-semibold tracking-tight">
                                {data ? (
                                    <>
                                        <CountUp value={data.count} /> results for <span className="text-volt-400">&ldquo;{data.query}&rdquo;</span>
                                    </>
                                ) : (
                                    <>Searching for &ldquo;{q}&rdquo;</>
                                )}
                            </h1>
                            {data && data.total > data.count && (
                                <p className="mt-1 text-sm text-fog-500">eBay has about {data.total.toLocaleString()} listings. Showing the best {data.count}.</p>
                            )}
                        </div>
                        {data && <PipelineBadge data={data} />}
                    </div>

                    <div className={`mt-6 transition-opacity duration-300 ${query.isFetching && data ? "opacity-60" : "opacity-100"}`}>
                        {loadingFirst && (
                            <div className="grid grid-cols-2 gap-3 sm:gap-5 md:grid-cols-3 lg:grid-cols-4">
                                {Array.from({ length: 8 }).map((_, i) => <ProductSkeleton key={i} />)}
                            </div>
                        )}

                        {query.isError && !data && (
                            <EmptyState
                                title={query.error.status === 503 ? "eBay is not connected yet" : "Search did not work"}
                                text={query.error.message}
                                icon={<RefreshCw className="h-6 w-6" />}
                                action={<button type="button" onClick={() => query.refetch()} className="btn-ghost">Try again</button>}
                            />
                        )}

                        {data && data.items.length === 0 && (
                            <EmptyState icon={<SearchIcon className="h-6 w-6" />} title="No listings found" text="Try fewer words, a different spelling, or remove a filter." />
                        )}

                        {data && data.items.length > 0 && (
                            <ProductGrid products={data.items} showRank={filters.sort === "best"} savedIds={ids} onToggleSave={toggle} />
                        )}
                    </div>

                    {data && data.count >= filters.limit && filters.limit < MAX && (
                        <motion.div className="mt-10 flex justify-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                            <button type="button" onClick={() => update({ limit: Math.min(filters.limit + PAGE, MAX) })} className="btn-ghost">
                                Show more
                            </button>
                        </motion.div>
                    )}
                </>
            )}
        </div>
    );
}