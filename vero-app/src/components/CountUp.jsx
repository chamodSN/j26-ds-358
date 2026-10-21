import { useEffect } from "react";
import { animate, motion, useMotionValue, useTransform } from "motion/react";

// A number that counts up smoothly when it changes.
export default function CountUp({ value, duration = 0.9 }) {
    const mv = useMotionValue(0);
    const text = useTransform(mv, (v) => Math.round(v).toLocaleString());

    useEffect(() => {
        const controls = animate(mv, value, { duration, ease: "easeOut" });
        return () => controls.stop();
    }, [value, duration, mv]);

    return <motion.span>{text}</motion.span>;
}