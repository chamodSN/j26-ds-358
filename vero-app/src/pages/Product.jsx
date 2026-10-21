import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ExternalLink, Heart, ImageOff, MapPin, Star, Truck } from "lucide-react";
import ProductGrid from "../components/ProductGrid";
import EmptyState from "../components/EmptyState";
import { useSaved } from "../hooks/useSaved";
import { api } from "../utils/api";
import { formatLKR, formatMoney } from "../utils/format";

function Skeleton() {
    return (
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-10 md:grid-cols-2">
            <div className="skeleton aspect-square rounded-3xl" />
            <div className="space-y-4">
                <div className="skeleton h-8 w-4/5 rounded" />
                <div className="skeleton h-8 w-1/2 rounded" />
                <div className="skeleton mt-8 h-14 w-2/3 rounded" />
            </div>
        </div>
    );
}

function ProductView({ item }) {
    const navigate = useNavigate();
    const { ids, toggle } = useSaved();
    const [active, setActive] = useState(0);
    const [more, setMore] = useState(false);
    const images = item.images.length ? item.images : item.image_url ? [item.image_url] : [];
    const saved = ids.has(item.id);
    const desc = item.description || "";

    return (
        <div className="mx-auto max-w-6xl px-5 py-8">
            <button type="button" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/"))} className="inline-flex items-center gap-1.5 text-sm text-fog-500 hover:text-fog-100">
                <ArrowLeft className="h-4 w-4" /> Back
            </button>

            <div className="mt-6 grid gap-10 md:grid-cols-2">
                <div>
                    <div className="relative aspect-square overflow-hidden rounded-3xl bg-white">
                        <AnimatePresence mode="wait">
                            {images.length ? (
                                <motion.img
                                    key={images[active]}
                                    src={images[active]}
                                    alt={item.title}
                                    referrerPolicy="no-referrer"
                                    initial={{ opacity: 0, scale: 0.97 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.25 }}
                                    className="absolute inset-0 h-full w-full object-contain p-6"
                                />
                            ) : (
                                <div className="grid h-full place-items-center text-ink-600"><ImageOff className="h-12 w-12" /></div>
                            )}
                        </AnimatePresence>
                    </div>
                    {images.length > 1 && (
                        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                            {images.slice(0, 8).map((src, i) => (
                                <button
                                    key={src}
                                    type="button"
                                    onClick={() => setActive(i)}
                                    aria-label={`Photo ${i + 1}`}
                                    className={`h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-white p-1 transition ${active === i ? "ring-2 ring-volt-400" : "opacity-60 hover:opacity-100"}`}
                                >
                                    <img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-contain" />
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                        {item.condition && <span className="rounded-full bg-white/10 px-3 py-1 text-fog-300">{item.condition}</span>}
                        {item.brand && <span className="rounded-full bg-white/10 px-3 py-1 text-fog-300">{item.brand}</span>}
                    </div>
                    <h1 className="mt-4 font-display text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{item.title}</h1>

                    <div className="mt-7">
                        <div className="font-mono text-4xl font-semibold tabular-nums text-volt-400">{formatLKR(item.price_lkr)}</div>
                        <p className="mt-1 text-sm text-fog-500">
                            {formatMoney(item.price, item.currency)} on eBay. The LKR price is an estimate from today&apos;s exchange rate.
                        </p>
                    </div>

                    <div className="mt-7 flex flex-wrap gap-3">
                        {item.item_url && (
                            <a href={item.item_url} target="_blank" rel="noopener noreferrer" className="btn-primary !px-7 !py-3 !text-base">
                                View on eBay <ExternalLink className="h-4 w-4" />
                            </a>
                        )}
                        <button type="button" onClick={() => toggle(item)} aria-pressed={saved} className="btn-ghost !py-3">
                            <Heart className={`h-4 w-4 ${saved ? "text-volt-400" : ""}`} fill={saved ? "currentColor" : "none"} />
                            {saved ? "Saved" : "Save"}
                        </button>
                    </div>

                    <div className="mt-8 grid gap-3 rounded-3xl border border-white/10 bg-ink-800/60 p-5 text-sm">
                        {item.seller && (
                            <div className="flex items-center justify-between">
                                <span className="text-fog-500">Seller</span>
                                <span className="inline-flex items-center gap-1.5">
                                    {item.seller}
                                    {item.seller_rating != null && (
                                        <span className="inline-flex items-center gap-1 text-fog-300"><Star className="h-3 w-3 text-volt-400" fill="currentColor" />{item.seller_rating.toFixed(1)}%</span>
                                    )}
                                </span>
                            </div>
                        )}
                        {item.shipping && (
                            <div className="flex items-center justify-between">
                                <span className="inline-flex items-center gap-1.5 text-fog-500"><Truck className="h-4 w-4" /> Shipping</span>
                                <span>{item.shipping}</span>
                            </div>
                        )}
                        {item.location && (
                            <div className="flex items-center justify-between">
                                <span className="inline-flex items-center gap-1.5 text-fog-500"><MapPin className="h-4 w-4" /> Ships from</span>
                                <span>{item.location}</span>
                            </div>
                        )}
                    </div>
                </motion.div>
            </div>

            {item.specs.length > 0 && (
                <section className="mt-14">
                    <h2 className="font-display text-2xl font-semibold">Details</h2>
                    <dl className="mt-5 grid gap-x-10 sm:grid-cols-2">
                        {item.specs.map((s, i) => (
                            <motion.div
                                key={`${s.name}-${i}`}
                                initial={{ opacity: 0, y: 10 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: Math.min(i, 8) * 0.03 }}
                                className="flex justify-between gap-4 border-b border-white/10 py-3 text-sm"
                            >
                                <dt className="text-fog-500">{s.name}</dt>
                                <dd className="text-right">{s.value}</dd>
                            </motion.div>
                        ))}
                    </dl>
                </section>
            )}

            {desc && (
                <section className="mt-12 max-w-3xl">
                    <h2 className="font-display text-2xl font-semibold">About this item</h2>
                    <p className="mt-4 text-sm leading-relaxed text-fog-300">{more || desc.length < 320 ? desc : `${desc.slice(0, 320)}...`}</p>
                    {desc.length >= 320 && (
                        <button type="button" onClick={() => setMore((m) => !m)} className="mt-2 text-sm font-medium text-volt-400 hover:underline">
                            {more ? "Show less" : "Read more"}
                        </button>
                    )}
                </section>
            )}

            {item.related.length > 0 && (
                <section className="mt-16">
                    <h2 className="font-display text-2xl font-semibold">You might also like</h2>
                    <div className="mt-5">
                        <ProductGrid products={item.related} savedIds={ids} onToggleSave={toggle} />
                    </div>
                </section>
            )}
        </div>
    );
}

export default function Product() {
    const [params] = useSearchParams();
    const id = params.get("id");
    const query = useQuery({
        queryKey: ["item", id],
        queryFn: ({ signal }) => api.item(id, signal),
        enabled: !!id,
    });

    if (!id) return <EmptyState title="No product selected" text="Go back and pick a product." />;
    if (query.isLoading) return <Skeleton />;
    if (query.isError) {
        return (
            <EmptyState
                title="We could not load this item"
                text={query.error.message}
                action={<Link to="/" className="btn-ghost">Back to home</Link>}
            />
        );
    }
    return <ProductView key={id} item={query.data} />;
}