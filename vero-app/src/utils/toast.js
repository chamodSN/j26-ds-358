// A tiny event bus so any file can call toast("...") without a provider.
const listeners = new Set();

export function toast(message, tone = "default") {
    listeners.forEach((fn) => fn({ id: `${Date.now()}-${Math.random()}`, message, tone }));
}

export function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
}