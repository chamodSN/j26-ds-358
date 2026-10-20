import ProductCard from "./ProductCard";

export default function ProductGrid({ products, showRank = false, savedIds, onToggleSave }) {
    return (
        <div className="grid grid-cols-2 gap-3 sm:gap-5 md:grid-cols-3 lg:grid-cols-4">
            {products.map((p, i) => (
                <ProductCard
                    key={p.id}
                    product={p}
                    index={i}
                    showRank={showRank}
                    saved={savedIds?.has(p.id)}
                    onToggleSave={onToggleSave}
                />
            ))}
        </div>
    );
}