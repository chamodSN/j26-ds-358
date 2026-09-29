import { Smartphone, Laptop, ArrowLeft, Heart, ExternalLink } from "lucide-react";
import { originalListingUrl } from "../utils/links";

const CATEGORY_ICON = { Phones: Smartphone, Laptops: Laptop };

function money(amount, currency) {
    return `${currency} ${amount.toLocaleString("en-LK")}`;
}

export default function ProductDetail({ product, related, isSaved, onToggleSave, onBack, onOpenRelated }) {
    const Icon = CATEGORY_ICON[product.category] ?? Smartphone;

    return (
        <div className="mx-auto max-w-3xl px-6 py-8">
            <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-1 text-sm text-ink-soft transition-colors hover:text-ink"
            >
                <ArrowLeft className="h-4 w-4" /> Back to results
            </button>

            <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-[220px_1fr]">
                <div>
                    <div className="flex h-52 w-full items-center justify-center rounded-lg border border-line bg-gradient-to-br from-amber-50 via-paper to-moss-50">
                        <Icon className="h-20 w-20 text-amber-600" strokeWidth={1.2} aria-hidden="true" />
                    </div>
                    <div className="mt-2 flex gap-2">
                        {[0, 1, 2].map((i) => (
                            <div
                                key={i}
                                className="flex h-14 flex-1 items-center justify-center rounded-md border border-line bg-paper"
                            >
                                <Icon className="h-6 w-6 text-ink-faint" strokeWidth={1.2} aria-hidden="true" />
                            </div>
                        ))}
                    </div>
                </div>

                <div>
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <h1 className="font-display text-2xl text-ink">{product.title}</h1>
                            <p className="text-sm text-ink-faint">{product.variant}</p>
                        </div>
                        <button
                            type="button"
                            onClick={() => onToggleSave(product.id)}
                            aria-pressed={isSaved}
                            aria-label={isSaved ? "Remove from saved" : "Save for later"}
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors ${isSaved
                                    ? "border-amber-500 bg-amber-50 text-amber-600"
                                    : "border-line text-ink-faint hover:text-ink"
                                }`}
                        >
                            <Heart className="h-4 w-4" fill={isSaved ? "currentColor" : "none"} />
                        </button>
                    </div>

                    <span className="mt-2 inline-block rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-600">
                        {product.matchQuality}
                    </span>

                    <p className="mt-3 text-sm leading-relaxed text-ink-soft">{product.description}</p>

                    <ul className="mt-3 space-y-1">
                        {product.highlights.map((h) => (
                            <li key={h} className="flex gap-2 text-sm text-ink-soft">
                                <span className="text-moss-500">•</span> {h}
                            </li>
                        ))}
                    </ul>

                    <div className="mt-4 flex flex-wrap gap-1.5">
                        {product.specs.map((s) => (
                            <span key={s.label} className="rounded-sm bg-paper px-2 py-1 text-xs text-ink-soft">
                                {s.label} {s.value}
                            </span>
                        ))}
                    </div>

                    <div className="mt-5">
                        <div className="font-display text-3xl text-ink">
                            {money(product.bestPrice.amount, product.bestPrice.currency)}
                        </div>
                        <div className="mt-0.5 text-sm text-moss-500">
                            Save {money(product.savings, product.bestPrice.currency)} vs {product.localReference.label}
                        </div>
                    </div>
                </div>
            </div>

            <div className="mt-8">
                <h2 className="font-display text-lg text-ink">Available from</h2>
                <div className="mt-3 divide-y divide-line rounded-lg border border-line bg-surface">
                    {product.listings.map((l) => (
                        <div key={l.platform} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
                            <div>
                                <span className="font-medium text-ink">{l.platform}</span>
                                <span className="ml-2 text-ink-faint">
                                    {l.note} · {l.delivery}
                                </span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className="font-medium text-ink">{money(l.price, l.currency)}</span>
                                <a
                                    href={originalListingUrl(l.platform, product.title)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1 text-amber-600 transition-colors hover:text-amber-500"
                                >
                                    Visit store <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {related.length > 0 && (
                <div className="mt-10">
                    <h2 className="font-display text-lg text-ink">You might also like</h2>
                    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                        {related.map((p) => {
                            const RIcon = CATEGORY_ICON[p.category] ?? Smartphone;
                            return (
                                <button
                                    key={p.id}
                                    type="button"
                                    onClick={() => onOpenRelated(p)}
                                    className="rounded-lg border border-line bg-surface p-3 text-left transition-colors hover:border-amber-400"
                                >
                                    <div className="flex h-16 w-full items-center justify-center rounded-md bg-paper">
                                        <RIcon className="h-6 w-6 text-amber-600" strokeWidth={1.5} aria-hidden="true" />
                                    </div>
                                    <p className="mt-2 truncate text-sm font-medium text-ink">{p.title}</p>
                                    <p className="text-xs text-moss-500">
                                        {p.bestPrice.currency} {p.bestPrice.amount.toLocaleString("en-LK")}
                                    </p>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}