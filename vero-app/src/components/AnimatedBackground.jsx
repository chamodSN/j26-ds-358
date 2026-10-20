// Slow drifting colour blobs and a fading grid. Pure CSS, no JS cost.
export default function AnimatedBackground() {
    return (
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
            <div className="absolute -left-32 -top-40 h-[34rem] w-[34rem] animate-aurora rounded-full bg-volt-400/20 blur-[120px]" />
            <div className="absolute -right-24 top-10 h-[30rem] w-[30rem] animate-aurora-slow rounded-full bg-aqua-400/15 blur-[120px]" />
            <div className="absolute bottom-0 left-1/3 h-[22rem] w-[22rem] animate-aurora rounded-full bg-emerald-400/10 blur-[110px]" />
            <div className="grid-fade absolute inset-0" />
        </div>
    );
}