import { motion } from "motion/react";

export default function EmptyState({ icon, title, text, action }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto flex max-w-md flex-col items-center gap-3 py-20 text-center"
        >
            {icon && <div className="grid h-14 w-14 place-items-center rounded-2xl bg-white/5 text-volt-400">{icon}</div>}
            <h3 className="font-display text-2xl font-semibold">{title}</h3>
            {text && <p className="text-sm leading-relaxed text-fog-500">{text}</p>}
            {action}
        </motion.div>
    );
}