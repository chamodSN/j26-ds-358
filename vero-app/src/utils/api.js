export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

async function request(path, { method = "GET", body, signal } = {}) {
    let res;
    try {
        res = await fetch(`/api${path}`, {
            method,
            credentials: "include",
            headers: body ? { "Content-Type": "application/json" } : undefined,
            body: body ? JSON.stringify(body) : undefined,
            signal,
        });
    } catch (err) {
        if (err.name === "AbortError") throw err;
        throw new ApiError("Cannot reach the server. Is the backend running?", 0);
    }

    if (!res.ok) {
        let message = "Something went wrong. Please try again.";
        try {
            const data = await res.json();
            if (typeof data.detail === "string") message = data.detail;
            else if (Array.isArray(data.detail) && data.detail[0]?.msg) message = data.detail[0].msg;
        } catch {
            /* body was not JSON */
        }
        throw new ApiError(message, res.status);
    }
    return res.status === 204 ? null : res.json();
}

function qs(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
        if (v !== "" && v != null) sp.set(k, String(v));
    });
    return sp.toString();
}

export const api = {
    // 401 here just means "not signed in", so we return null
    me: async () => {
        try {
            return await request("/auth/me");
        } catch (err) {
            if (err.status === 401) return null;
            throw err;
        }
    },
    register: (body) => request("/auth/register", { method: "POST", body }),
    login: (body) => request("/auth/login", { method: "POST", body }),
    google: (credential) => request("/auth/google", { method: "POST", body: { credential } }),
    logout: () => request("/auth/logout", { method: "POST" }),

    search: (p, signal) =>
        request(
            `/search?${qs({
                q: p.q,
                limit: p.limit,
                min_price: p.min,
                max_price: p.max,
                condition: p.condition,
                category: p.category,
                sort: p.sort,
            })}`,
            { signal },
        ),
    item: (id, signal) => request(`/item?${qs({ id })}`, { signal }),
    featured: (signal) => request("/featured", { signal }),

    saved: {
        list: () => request("/saved"),
        add: (body) => request("/saved", { method: "POST", body }),
        remove: (itemId) => request(`/saved?${qs({ item_id: itemId })}`, { method: "DELETE" }),
    },
    history: {
        list: () => request("/history"),
        clear: () => request("/history", { method: "DELETE" }),
    },
};