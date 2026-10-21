import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../utils/api";
import { toast } from "../utils/toast";
import AuthModal from "../components/AuthModal";
import { AuthContext } from "./auth-context";

export function AuthProvider({ children }) {
    const qc = useQueryClient();
    const [modal, setModal] = useState({ open: false, mode: "login" });

    const { data: user = null, isLoading } = useQuery({
        queryKey: ["me"],
        queryFn: api.me,
        staleTime: Infinity,
        retry: false,
    });

    const openAuth = useCallback((mode = "login") => setModal({ open: true, mode }), []);
    const closeAuth = useCallback(() => setModal((m) => ({ ...m, open: false })), []);

    const handleAuthed = useCallback(
        (u) => {
            qc.setQueryData(["me"], u);
            qc.invalidateQueries({ queryKey: ["saved"] });
            qc.invalidateQueries({ queryKey: ["history"] });
            setModal((m) => ({ ...m, open: false }));
            toast(`Welcome, ${u.name || u.email}`);
        },
        [qc],
    );

    const logout = useCallback(async () => {
        await api.logout();
        qc.setQueryData(["me"], null);
        qc.removeQueries({ queryKey: ["saved"] });
        qc.removeQueries({ queryKey: ["history"] });
        toast("Signed out");
    }, [qc]);

    const value = useMemo(
        () => ({ user, loading: isLoading, openAuth, logout }),
        [user, isLoading, openAuth, logout],
    );

    return (
        <AuthContext.Provider value={value}>
            {children}
            <AuthModal
                open={modal.open}
                mode={modal.mode}
                onModeChange={(mode) => setModal({ open: true, mode })}
                onClose={closeAuth}
                onAuthed={handleAuthed}
            />
        </AuthContext.Provider>
    );
}