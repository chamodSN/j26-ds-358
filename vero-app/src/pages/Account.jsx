import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Clock, LogOut } from "lucide-react";
import EmptyState from "../components/EmptyState";
import { useAuth } from "../hooks/useAuth";
import { api } from "../utils/api";
import { toast } from "../utils/toast";

export default function Account() {
    const { user, loading, openAuth, logout } = useAuth();
    const navigate = useNavigate();
    const qc = useQueryClient();

    const history = useQuery({ queryKey: ["history"], queryFn: api.history.list, enabled: !!user });
    const clear = useMutation({
        mutationFn: api.history.clear,
        onSuccess: () => {
            qc.setQueryData(["history"], []);
            toast("Search history cleared");
        },
    });

    if (!loading && !user) {
        return (
            <EmptyState
                title="Sign in to see your account"
                action={<button type="button" onClick={() => openAuth("login")} className="btn-primary">Sign in</button>}
            />
        );
    }
    if (!user) return null;

    return (
        <div className="mx-auto max-w-3xl px-5 py-10">
            <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-5 rounded-3xl border border-white/10 bg-ink-800/60 p-6">
                {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" referrerPolicy="no-referrer" className="h-16 w-16 rounded-full" />
                ) : (
                    <span className="grid h-16 w-16 place-items-center rounded-full bg-volt-400 font-display text-2xl font-bold text-ink-950">
                        {(user.name || user.email)[0].toUpperCase()}
                    </span>
                )}
                <div className="min-w-0 flex-1">
                    <h1 className="truncate font-display text-2xl font-semibold">{user.name || "Your account"}</h1>
                    <p className="truncate text-sm text-fog-500">{user.email}</p>
                    <p className="mt-1 text-xs text-fog-700">
                        Sign-in methods: {[user.has_password && "email", user.google_linked && "Google"].filter(Boolean).join(", ")}
                    </p>
                </div>
                <button type="button" onClick={async () => { await logout(); navigate("/"); }} className="btn-ghost">
                    <LogOut className="h-4 w-4" /> Sign out
                </button>
            </motion.div>

            <section className="mt-10">
                <div className="flex items-center justify-between">
                    <h2 className="font-display text-xl font-semibold">Recent searches</h2>
                    {history.data?.length > 0 && (
                        <button type="button" onClick={() => clear.mutate()} className="text-sm text-fog-500 hover:text-fog-100">Clear all</button>
                    )}
                </div>
                <ul className="mt-4 divide-y divide-white/10 rounded-3xl border border-white/10 bg-ink-800/60">
                    {history.data?.length === 0 && <li className="p-6 text-sm text-fog-500">No searches yet.</li>}
                    {history.data?.map((h, i) => (
                        <motion.li key={h.query} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
                            <Link to={`/search?q=${encodeURIComponent(h.query)}`} className="flex items-center gap-3 px-5 py-3.5 text-sm hover:bg-white/5">
                                <Clock className="h-4 w-4 text-fog-700" />
                                <span className="flex-1 truncate">{h.query}</span>
                                <span className="text-xs text-fog-700">{new Date(h.searched_at).toLocaleDateString()}</span>
                            </Link>
                        </motion.li>
                    ))}
                </ul>
            </section>
        </div>
    );
}