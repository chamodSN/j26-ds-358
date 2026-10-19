import { motion } from "motion/react";
import { Sparkles } from "lucide-react";
import AnimatedBackground from "./AnimatedBackground";
import SearchBar from "./SearchBar";
import { POPULAR_SEARCHES } from "../utils/format";

const WORDS = ["Search", "once.", "Compare", "everything."];

// A strip of real product photos that scrolls forever.
function Marquee({ images }) {
    if (images.length < 4) return null;
    const loop = [...images, ...images];
    return (
        <div className="relative mt-16 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
            <div className="flex w-max animate-marquee gap-4">
                {loop.map((src, i) => (
                    <div key={`${src}-${i}`} className="h-28 w-28 shrink-0 rounded-2xl bg-white p-2 sm:h-32 sm:w-32">
                        <img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-contain" />
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function Hero({ images = [], onSearch }) {
    return (
        <section className="relative">
            <AnimatedBackground />
            <div className="mx-auto max-w-6xl px-5 pb-10 pt-16 sm:pt-24">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-fog-300"
                >
                    <Sparkles className="h-3.5 w-3.5 text-volt-400" /> Live listings. Prices in LKR.
                </motion.div>

                <h1 className="mt-6 max-w-4xl font-display text-5xl font-semibold leading-[1.02] tracking-tight sm:text-7xl">
                    {WORDS.map((w, i) => (
                        <span key={w} className="mr-3 inline-block overflow-hidden pb-2 align-bottom">
                            <motion.span
                                className={`inline-block ${i === WORDS.length - 1 ? "bg-gradient-to-r from-volt-400 to-aqua-400 bg-clip-text text-transparent" : ""}`}
                                initial={{ y: "115%" }}
                                animate={{ y: 0 }}
                                transition={{ duration: 0.8, delay: 0.15 + i * 0.09, ease: [0.22, 1, 0.36, 1] }}
                            >
                                {w}
                            </motion.span>
                        </span>
                    ))}
                </h1>

                <motion.p
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.6, duration: 0.6 }}
                    className="mt-6 max-w-xl text-lg leading-relaxed text-fog-300"
                >
                    Describe what you want in your own words. Vero finds real listings and shows what they
                    cost in rupees, so a good deal looks like one.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.75, duration: 0.6 }}
                    className="relative z-20 mt-10 max-w-3xl"
                >
                    <SearchBar large onSubmit={onSearch} />
                    <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
                        <span className="text-fog-700">Popular:</span>
                        {POPULAR_SEARCHES.map((q) => (
                            <button key={q} type="button" onClick={() => onSearch(q)} className="rounded-full border border-white/10 px-3 py-1 text-fog-300 transition hover:border-volt-400/60 hover:text-fog-100">
                                {q}
                            </button>
                        ))}
                    </div>
                </motion.div>

                <Marquee images={images} />
            </div>
        </section>
    );
}