import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { GoogleLogin } from "@react-oauth/google";
import { X } from "lucide-react";
import { api } from "../utils/api";
import { GOOGLE_CLIENT_ID } from "../utils/config";
import Logo from "./Logo";

function AuthForm({ mode, onModeChange, onAuthed }) {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const isLogin = mode === "login";

    async function submit(e) {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const user = isLogin
                ? await api.login({ email, password })
                : await api.register({ email, password, name });
            onAuthed(user);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    async function onGoogle(credential) {
        setError("");
        try {
            onAuthed(await api.google(credential));
        } catch (err) {
            setError(err.message);
        }
    }

    return (
        <>
            <h2 className="mt-5 font-display text-3xl font-semibold tracking-tight">
                {isLogin ? "Welcome back" : "Create your account"}
            </h2>
            <p className="mt-1 text-sm text-fog-500">
                {isLogin ? "Sign in to see your saved items." : "Save items and keep your search history."}
            </p>

            {GOOGLE_CLIENT_ID && (
                <div className="mt-6 flex justify-center">
                    <GoogleLogin
                        onSuccess={(res) => onGoogle(res.credential)}
                        onError={() => setError("Google sign-in failed. Please try again.")}
                        theme="filled_black"
                        shape="pill"
                        text="continue_with"
                        width="300"
                    />
                </div>
            )}
            {GOOGLE_CLIENT_ID && (
                <div className="my-5 flex items-center gap-3 text-xs text-fog-700">
                    <span className="h-px flex-1 bg-white/10" /> or with email <span className="h-px flex-1 bg-white/10" />
                </div>
            )}

            <form onSubmit={submit} className={`space-y-3 ${GOOGLE_CLIENT_ID ? "" : "mt-6"}`}>
                {!isLogin && (
                    <input className="input" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
                )}
                <input className="input" type="email" required placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus />
                <input
                    className="input"
                    type="password"
                    required
                    minLength={isLogin ? 1 : 8}
                    placeholder={isLogin ? "Password" : "Password (8+ characters)"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={isLogin ? "current-password" : "new-password"}
                />
                <AnimatePresence>
                    {error && (
                        <motion.p
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300"
                        >
                            {error}
                        </motion.p>
                    )}
                </AnimatePresence>
                <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-60">
                    {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-950/30 border-t-ink-950" /> : isLogin ? "Sign in" : "Create account"}
                </button>
            </form>

            <p className="mt-5 text-center text-sm text-fog-500">
                {isLogin ? "New to Vero?" : "Already have an account?"}{" "}
                <button type="button" onClick={() => onModeChange(isLogin ? "register" : "login")} className="font-semibold text-volt-400 hover:underline">
                    {isLogin ? "Create an account" : "Sign in"}
                </button>
            </p>
        </>
    );
}

export default function AuthModal({ open, mode, onModeChange, onClose, onAuthed }) {
    useEffect(() => {
        if (!open) return;
        const onKey = (e) => e.key === "Escape" && onClose();
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    return (
        <AnimatePresence>
            {open && (
                <motion.div
                    className="fixed inset-0 z-[90] grid place-items-center bg-black/70 px-4 backdrop-blur-sm"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onMouseDown={(e) => e.target === e.currentTarget && onClose()}
                >
                    <motion.div
                        role="dialog"
                        aria-modal="true"
                        className="relative w-full max-w-sm rounded-3xl border border-white/10 bg-ink-800 p-7 shadow-2xl"
                        initial={{ opacity: 0, y: 40, scale: 0.94 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 24, scale: 0.96 }}
                        transition={{ type: "spring", stiffness: 340, damping: 28 }}
                    >
                        <button type="button" onClick={onClose} aria-label="Close" className="absolute right-4 top-4 rounded-full p-1.5 text-fog-500 hover:bg-white/10 hover:text-fog-100">
                            <X className="h-4 w-4" />
                        </button>
                        <Logo />
                        <AuthForm key={mode} mode={mode} onModeChange={onModeChange} onAuthed={onAuthed} />
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}