import { motion } from "motion/react";
import { CATEGORIES } from "../utils/format";

const CONDITIONS = [
    { key: "", label: "Any" },
    { key: "new", label: "New" },
    { key: "used", label: "Used" },
];

// Price inputs keep their own text until you leave the field or press Enter.
// The parent gives this a `key`, so it resets when the URL changes.
function PriceRange({ min, max, onChange }) {
    function commit(e) {
        const form = e.currentTarget.form;
        onChange({ min: form.min.value.trim(), max: form.max.value.trim() });
    }
    return (
        <form
            onSubmit={(e) => {
                e.preventDefault();
                commit({ currentTarget: e.currentTarget.elements.min });
            }}
            className="flex items-center gap-2 text-sm"
        >
            <span className="text-fog-500">LKR</span>
            <input name="min" defaultValue={min} inputMode="numeric" placeholder="Min" onBlur={commit} className="input !w-24 !py-1.5" />
            <span className="text-fog-700">to</span>
            <input name="max" defaultValue={max} inputMode="numeric" placeholder="Max" onBlur={commit} className="input !w-24 !py-1.5" />
        </form>
    );
}

export default function FiltersBar({ filters, onChange }) {
    return (
        <div className="space-y-4">
            <div className="-mx-5 flex gap-1 overflow-x-auto px-5 pb-1">
                {CATEGORIES.map((c) => (
                    <button
                        key={c.key}
                        type="button"
                        onClick={() => onChange({ category: c.key })}
                        className={`relative shrink-0 rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${filters.category === c.key ? "text-ink-950" : "text-fog-300 hover:text-fog-100"
                            }`}
                    >
                        {filters.category === c.key && (
                            <motion.span layoutId="category-pill" className="absolute inset-0 rounded-full bg-volt-400" transition={{ type: "spring", stiffness: 420, damping: 34 }} />
                        )}
                        <span className="relative">{c.label}</span>
                    </button>
                ))}
            </div>

            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div className="inline-flex rounded-full border border-white/10 p-1">
                    {CONDITIONS.map((c) => (
                        <button
                            key={c.key}
                            type="button"
                            onClick={() => onChange({ condition: c.key })}
                            className={`relative rounded-full px-3.5 py-1 text-sm transition-colors ${filters.condition === c.key ? "text-fog-100" : "text-fog-500 hover:text-fog-100"
                                }`}
                        >
                            {filters.condition === c.key && (
                                <motion.span layoutId="condition-pill" className="absolute inset-0 rounded-full bg-white/15" transition={{ type: "spring", stiffness: 420, damping: 34 }} />
                            )}
                            <span className="relative">{c.label}</span>
                        </button>
                    ))}
                </div>

                <PriceRange key={`${filters.min}|${filters.max}`} min={filters.min} max={filters.max} onChange={onChange} />

                <select
                    value={filters.sort}
                    onChange={(e) => onChange({ sort: e.target.value })}
                    aria-label="Sort results"
                    className="input !w-auto !rounded-full !py-1.5"
                >
                    <option value="best">Best match</option>
                    <option value="price_asc">Price: low to high</option>
                    <option value="price_desc">Price: high to low</option>
                </select>
            </div>
        </div>
    );
}