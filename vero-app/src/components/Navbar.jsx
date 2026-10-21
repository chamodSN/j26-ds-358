import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import { Clock, Heart, LogOut } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useSaved } from "../hooks/useSaved";
import Logo from "./Logo";

function linkClass({ isActive }) {
    return `relative rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${isActive ? "bg-white/10 text-fog-100" : "text-fog-500 hover:text-fog-100"
        }`;
}

export default function Navbar() {
    const { user, loading, openAuth, logout } = useAuth();
    const { items } = useSaved();
    const navigate = useNavigate();
    const [scrolled, setScrolled] = useState(false);
    const [menu, setMenu] = useState(false);
    const { scrollY } = useScroll();
    useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > 12));

    return (
        <motion.header
            initial={{ y: -40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className={`sticky top-0 z-50 transition-colors duration-300 ${scrolled ? "glass border-x-0 border-t-0" : "border-b border-transparent"
                }`}
        >
            <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
                <Link to="/" aria-label="Vero home">
                    <Logo />
                </Link>

                <nav className="hidden items-center gap-1 sm:flex">
                    <NavLink to="/" end className={linkClass}>Discover</NavLink>
                    <NavLink to="/saved" className={linkClass}>
                        <span className="inline-flex items-center gap-1.5">
                            Saved
                            {items.length > 0 && (
                                <motion.span key={items.length} initial={{ scale: 1.6 }} animate={{ scale: 1 }} className="rounded-full bg-volt-400 px-1.5 text-[11px] font-bold text-ink-950">
                                    {items.length}
                                </motion.span>
                            )}
                        </span>
                    </NavLink>
                </nav>

                <div className="relative flex items-center gap-2">
                    <Link to="/saved" className="btn-ghost !px-3 sm:hidden" aria-label="Saved items">
                        <Heart className="h-4 w-4" />
                    </Link>
                    {loading ? (
                        <div className="skeleton h-9 w-24 rounded-full" />
                    ) : user ? (
                        <>
                            <button type="button" onClick={() => setMenu((m) => !m)} className="flex items-center gap-2 rounded-full border border-white/10 py-1 pl-1 pr-3 hover:border-white/30" aria-haspopup="menu" aria-expanded={menu}>
                                {user.avatar_url ? (
                                    <img src={user.avatar_url} alt="" referrerPolicy="no-referrer" className="h-7 w-7 rounded-full" />
                                ) : (
                                    <span className="grid h-7 w-7 place-items-center rounded-full bg-volt-400 text-xs font-bold text-ink-950">
                                        {(user.name || user.email)[0].toUpperCase()}
                                    </span>
                                )}
                                <span className="hidden max-w-[7rem] truncate text-sm sm:block">{user.name || user.email}</span>
                            </button>
                            <AnimatePresence>
                                {menu && (
                                    <motion.div
                                        initial={{ opacity: 0, y: -8, scale: 0.96 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: -8, scale: 0.96 }}
                                        transition={{ duration: 0.15 }}
                                        className="glass absolute right-0 top-12 w-52 rounded-2xl p-1.5 shadow-2xl"
                                        onMouseLeave={() => setMenu(false)}
                                    >
                                        <button type="button" onClick={() => { setMenu(false); navigate("/account"); }} className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-white/10">
                                            <Clock className="h-4 w-4 text-fog-500" /> Account and history
                                        </button>
                                        <button type="button" onClick={() => { setMenu(false); logout(); }} className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-white/10">
                                            <LogOut className="h-4 w-4 text-fog-500" /> Sign out
                                        </button>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </>
                    ) : (
                        <>
                            <button type="button" onClick={() => openAuth("login")} className="btn-ghost">Sign in</button>
                            <button type="button" onClick={() => openAuth("register")} className="btn-primary hidden sm:inline-flex">Get started</button>
                        </>
                    )}
                </div>
            </div>
        </motion.header>
    );
}