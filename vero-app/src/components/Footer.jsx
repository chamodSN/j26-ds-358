import Logo from "./Logo";

export default function Footer() {
    return (
        <footer className="mt-24 border-t border-white/10">
            <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-5 py-10 sm:flex-row sm:items-center">
                <div>
                    <Logo size={24} />
                    <p className="mt-3 max-w-md text-xs leading-relaxed text-fog-500">
                        Listings and photos come live from eBay. Prices in LKR are converted with today&apos;s
                        exchange rate and are for reference. The final price is always the one on the store page.
                    </p>
                </div>
                <p className="text-xs text-fog-700">J26-DS-358 | SLIIT research project</p>
            </div>
        </footer>
    );
}