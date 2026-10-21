import { useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { Heart, ImageOff, Star } from "lucide-react";
import { formatLKR, formatMoney, specChips } from "../utils/format";

export default function ProductCard({ product, index = 0, showRank = false, saved = false, onToggleSave }) {
    const [imgFailed, setImgFailed] = useState(false);
    const chips = specChips(product.title);
    const tier = product.attributes?.budget_tier; // filled by Member 4 later
    const isTop = showRank && product.rank === 1;

    // Moves the spotlight light under the mouse
    function trackMouse(e) {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
    }

    return (
        <motion.article
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            whileHover={{ y: -5 }}
            transition={{ duration: 0.5, delay: Math.min(index, 11) * 0.045, ease: [0.22, 1, 0.36, 1] }}
            onMouseMove={trackMouse}
            className={`group spotlight relative flex h-full flex-col rounded-3xl border bg-ink-800/80 p-3 transition-colors ${isTop ? "border-volt-400/60" : "border-white/10 hover:border-white/25"
                }`}
        >
            <Link to={`/product?id=${encodeURIComponent(product.id)}`} className="absolute inset-0 z-10 rounded-3xl" aria-label={product.title} />

            <div className="relative aspect-square overflow-hidden rounded-2xl bg-white">
                {product.image_url && !imgFailed ? (
                    <img
                        src={product.image_url}
                        alt=""
                        loading="lazy"
                        referrerPolicy="no-referrer"
                        onError={() => setImgFailed(true)}
                        className="h-full w-full object-contain p-3 transition-transform duration-500 group-hover:scale-105"
                    />
                ) : (
                    <div className="grid h-full place-items-center text-ink-600">
                        <ImageOff className="h-8 w-8" />
                    </div>
                )}

                {isTop && (
                    <span className="absolute left-2.5 top-2.5 rounded-full bg-volt-400 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-ink-950">
                        Top match
                    </span>
                )}
                {product.condition && (
                    <span className="absolute bottom-2.5 left-2.5 rounded-full bg-ink-950/80 px-2.5 py-1 text-[11px] font-medium text-fog-100 backdrop-blur">
                        {product.condition}
                    </span>
                )}

                <button
                    type="button"
                    onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onToggleSave?.(product);
                    }}
                    aria-pressed={saved}
                    aria-label={saved ? "Remove from saved" : "Save for later"}
                    className="absolute right-2.5 top-2.5 z-20 grid h-9 w-9 place-items-center rounded-full bg-ink-950/70 backdrop-blur transition hover:bg-ink-950"
                >
                    <AnimatePresence mode="wait" initial={false}>
                        <motion.span
                            key={saved ? "on" : "off"}
                            initial={{ scale: 0.4, rotate: -20 }}
                            animate={{ scale: 1, rotate: 0 }}
                            exit={{ scale: 0.4 }}
                            transition={{ type: "spring", stiffness: 520, damping: 18 }}
                        >
                            <Heart className={`h-4 w-4 ${saved ? "text-volt-400" : "text-fog-100"}`} fill={saved ? "currentColor" : "none"} />
                        </motion.span>
                    </AnimatePresence>
                </button>
            </div>

            <div className="flex flex-1 flex-col px-1.5 pb-1.5 pt-3.5">
                <h3 className="line-clamp-2 text-[15px] font-medium leading-snug text-fog-100">{product.title}</h3>

                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {tier && <span className="rounded-md bg-aqua-400/15 px-2 py-0.5 text-[11px] font-semibold text-aqua-400">{tier}</span>}
                    {chips.map((c) => (
                        <span key={c} className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-fog-300">{c}</span>
                    ))}
                </div>

                <div className="mt-auto pt-4">
                    <div className="font-mono text-xl font-semibold tabular-nums text-fog-100">{formatLKR(product.price_lkr)}</div>
                    <div className="mt-0.5 flex items-center justify-between text-xs text-fog-500">
                        <span>{formatMoney(product.price, product.currency)} on eBay</span>
                        {product.seller_rating != null && (
                            <span className="inline-flex items-center gap-1">
                                <Star className="h-3 w-3 text-volt-400" fill="currentColor" />
                                {product.seller_rating.toFixed(0)}%
                            </span>
                        )}
                    </div>
                    {product.ppp_adjusted_price_usd != null && (
                        <div className="mt-1 text-xs text-aqua-400">PPP-adjusted: {formatMoney(product.ppp_adjusted_price_usd, "USD")}</div>
                    )}
                    {product.relevance_score != null && (
                        <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10" title={`Relevance ${Math.round(product.relevance_score * 100)}%`}>
                            <motion.div className="h-full rounded-full bg-volt-400" initial={{ width: 0 }} animate={{ width: `${product.relevance_score * 100}%` }} transition={{ duration: 0.8, delay: 0.2 }} />
                        </div>
                    )}
                </div>
            </div>
        </motion.article>
    );
}