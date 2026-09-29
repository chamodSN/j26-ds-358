import { useState } from "react";
import { ChevronDown, ChevronUp, Smartphone, Laptop, Heart } from "lucide-react";

const CATEGORY_ICON = {
  Phones: Smartphone,
  Laptops: Laptop,
};

function money(amount, currency) {
  return `${currency} ${amount.toLocaleString("en-LK")}`;
}

export default function ProductCard({ product, showFairPrice, isSaved, onToggleSave, onOpen }) {
  const [open, setOpen] = useState(false);
  const isTopPick = product.rank === 1;
  const Icon = CATEGORY_ICON[product.category] ?? Smartphone;

  const displayAmount = showFairPrice
    ? product.bestPrice.amount
    : product.listings[0].price;

  return (
    <article
      onClick={() => onOpen(product)}
      className={`cursor-pointer rounded-lg border bg-surface p-5 transition-colors hover:border-amber-400 sm:p-6 ${isTopPick ? "border-amber-400" : "border-line"
        }`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-display text-[15px] ${isTopPick ? "bg-amber-500 text-white" : "bg-paper text-ink-soft"
            }`}
        >
          {product.rank}
        </div>

        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-md border border-line bg-gradient-to-br from-amber-50 to-paper">
          <Icon className="h-7 w-7 text-amber-600" strokeWidth={1.5} aria-hidden="true" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <h3 className="font-display text-lg text-ink">{product.title}</h3>
            <span className="text-sm text-ink-faint">{product.variant}</span>
          </div>

          {isTopPick && (
            <span className="mt-1 inline-block rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-600">
              {product.matchQuality} · best of this search
            </span>
          )}
          {!isTopPick && (
            <span className="mt-1 inline-block text-xs text-ink-faint">
              {product.matchQuality}
            </span>
          )}

          <div className="mt-3 flex flex-wrap gap-1.5">
            {product.specs.map((s) => (
              <span
                key={s.label}
                className="rounded-sm bg-paper px-2 py-1 text-xs text-ink-soft"
              >
                {s.label} {s.value}
              </span>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="font-display text-2xl text-ink">
                {money(displayAmount, product.bestPrice.currency)}
              </div>
              <div className="mt-0.5 text-sm text-moss-500">
                Save {money(product.savings, product.bestPrice.currency)} vs{" "}
                {product.localReference.label}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleSave(product.id);
                }}
                aria-pressed={isSaved}
                aria-label={isSaved ? "Remove from saved" : "Save for later"}
                className={`flex h-8 w-8 items-center justify-center rounded-full border transition-colors ${isSaved
                    ? "border-amber-500 bg-amber-50 text-amber-600"
                    : "border-line text-ink-faint hover:text-ink"
                  }`}
              >
                <Heart className="h-4 w-4" fill={isSaved ? "currentColor" : "none"} />
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpen(!open);
                }}
                className="flex items-center gap-1 text-sm font-medium text-ink-soft transition-colors hover:text-ink"
              >
                {product.listings.length} stores match this
                {open ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="mt-4 divide-y divide-line border-t border-line"
        >
          {product.listings.map((l) => (
            <div
              key={l.platform}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <div>
                <span className="font-medium text-ink">{l.platform}</span>
                <span className="ml-2 text-ink-faint">{l.note}</span>
              </div>
              <div className="flex items-center gap-4 text-ink-soft">
                <span>{l.delivery}</span>
                <span className="font-medium text-ink">
                  {money(l.price, l.currency)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}