import Reveal from "./Reveal";
import ProductCard from "./ProductCard";

// A row of products that scrolls sideways.
export default function Rail({ title, products, onSearchAll, savedIds, onToggleSave }) {
    return (
        <section className="mt-16">
            <Reveal className="mb-5 flex items-end justify-between gap-4">
                <h2 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h2>
                {onSearchAll && (
                    <button type="button" onClick={onSearchAll} className="text-sm font-medium text-volt-400 hover:underline">
                        See all
                    </button>
                )}
            </Reveal>
            <div className="-mx-5 flex snap-x gap-4 overflow-x-auto px-5 pb-4">
                {products.map((p, i) => (
                    <div key={p.id} className="w-[210px] shrink-0 snap-start sm:w-[240px]">
                        <ProductCard product={p} index={i} saved={savedIds?.has(p.id)} onToggleSave={onToggleSave} />
                    </div>
                ))}
            </div>
        </section>
    );
}