export default function ProductSkeleton() {
    return (
        <div className="rounded-3xl border border-white/10 bg-ink-800/60 p-3">
            <div className="skeleton aspect-square rounded-2xl" />
            <div className="space-y-2.5 p-2 pt-4">
                <div className="skeleton h-4 w-11/12 rounded" />
                <div className="skeleton h-4 w-2/3 rounded" />
                <div className="skeleton mt-4 h-6 w-1/2 rounded" />
            </div>
        </div>
    );
}