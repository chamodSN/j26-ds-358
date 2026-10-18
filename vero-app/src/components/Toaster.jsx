import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { subscribe } from "../utils/toast";

export default function Toaster() {
    const [items, setItems] = useState([]);

    useEffect(() => {
        return subscribe((t) => {
            setItems((prev) => [...prev.slice(-2), t]);
            setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== t.id)), 2600);
        });
    }, []);

    return (
        <div className="pointer-events-none fixed inset-x-0 bottom-6 z-[100] flex flex-col items-center gap-2 px-4">
            <AnimatePresence>
                {items.map((t) => (
                    <motion.div
                        key={t.id}
                        layout
                        initial={{ opacity: 0, y: 24, scale: 0.92 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 12, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 420, damping: 30 }}
                        className={`glass pointer-events-auto rounded-full px-4 py-2 text-sm shadow-xl ${t.tone === "error" ? "text-red-300" : "text-fog-100"
                            }`}
                    >
                        {t.message}
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );
}