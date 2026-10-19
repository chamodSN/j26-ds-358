import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Heart } from "lucide-react";
import ProductGrid from "../components/ProductGrid";
import EmptyState from "../components/EmptyState";
import ProductSkeleton from "../components/ProductSkeleton";
import { useAuth } from "../hooks/useAuth";
import { useSaved } from "../hooks/useSaved";

export default function Saved() {
    const { user, loading, openAuth } = useAuth();
    const { items, ids, toggle, isLoading } = useSaved();

    if (!loading && !user) {
        return (
            <EmptyState
                icon={<Heart className="h-6 w-6" />}
                title="Sign in to see your saved items"
                text="Your shortlist is kept in your account, so it follows you on any device."
                action={<button type="button" onClick={() => openAuth("login")} className="btn-primary">Sign in</button>}
            />
        );
    }

    // Saved rows have fewer fields than search results. This gives them the same shape.
    const products = items.map((s, i) => ({
        id: s.item_id,
        rank: i + 1,
        title: s.title,
        image_url: s.image_url,
        item_url: s.item_url,
        price: s.price,
        currency: s.currency,
        price_lkr: s.price_lkr,
        attributes: {},
    }));

    return (
        <div className="mx-auto max-w-6xl px-5 py-10">
            <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="font-display text-4xl font-semibold tracking-tight">
                Saved items
            </motion.h1>
            <p className="mt-2 text-sm text-fog-500">Prices were saved when you hearted the item. Open the item to see the latest.</p>

            <div className="mt-8">
                {(isLoading || loading) && (
                    <div className="grid grid-cols-2 gap-5 md:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <ProductSkeleton key={i} />)}</div>
                )}
                {!isLoading && !loading && products.length === 0 && (
                    <EmptyState
                        icon={<Heart className="h-6 w-6" />}
                        title="Nothing saved yet"
                        text="Tap the heart on any product to keep it here."
                        action={<Link to="/" className="btn-ghost">Find something</Link>}
                    />
                )}
                {products.length > 0 && <ProductGrid products={products} savedIds={ids} onToggleSave={toggle} />}
            </div>
        </div>
    );
}