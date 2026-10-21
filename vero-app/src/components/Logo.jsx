export default function Logo({ size = 28 }) {
    return (
        <span className="inline-flex items-center gap-2.5">
            <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
                <rect width="32" height="32" rx="9" fill="#C8FF4D" />
                <path d="M8 10l8 13 8-13" fill="none" stroke="#07090D" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="font-display text-xl font-semibold tracking-tight">Vero</span>
        </span>
    );
}