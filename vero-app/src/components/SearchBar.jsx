import { Search } from "lucide-react";

export default function SearchBar({ query, setQuery, onSearch, examples }) {
    return (
        <section className="border-b border-line bg-surface">
            <div className="mx-auto max-w-5xl px-6 py-14 sm:py-20">
                <h1 className="font-display text-4xl leading-[1.15] text-ink sm:text-5xl">
                    Search once. Compare what it really costs.
                </h1>
                <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-soft">
                    One search across Daraz, AliExpress, Alibaba and Amazon, with
                    prices adjusted so a good deal actually looks like one.
                </p>

                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        onSearch();
                    }}
                    className="mt-8 flex flex-col gap-3 sm:flex-row"
                >
                    <div className="flex flex-1 items-center gap-3 rounded-md border border-line bg-paper px-4 py-3 focus-within:border-amber-500">
                        <Search className="h-4 w-4 shrink-0 text-ink-faint" aria-hidden="true" />
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="gaming phone good battery under 60000"
                            className="w-full bg-transparent text-[15px] text-ink placeholder:text-ink-faint focus:outline-none"
                        />
                    </div>
                    <button
                        type="submit"
                        className="rounded-md bg-ink px-6 py-3 text-[15px] font-medium text-paper transition-colors hover:bg-amber-600"
                    >
                        Find
                    </button>
                </form>

                <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
                    <span className="text-ink-faint">Try:</span>
                    {examples.map((ex) => (
                        <button
                            key={ex}
                            type="button"
                            onClick={() => setQuery(ex)}
                            className="rounded-full border border-line px-3 py-1 text-ink-soft transition-colors hover:border-amber-400 hover:text-ink"
                        >
                            {ex}
                        </button>
                    ))}
                </div>
            </div>
        </section>
    );
}