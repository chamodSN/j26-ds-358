import { useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../utils/api";
import { toast } from "../utils/toast";
import { useAuth } from "./useAuth";

// Saved items with instant (optimistic) updates.
// `product` only needs: id, title, image_url, item_url, price, currency, price_lkr
export function useSaved() {
    const { user, openAuth } = useAuth();
    const qc = useQueryClient();

    const query = useQuery({ queryKey: ["saved"], queryFn: api.saved.list, enabled: !!user });
    const items = useMemo(() => query.data ?? [], [query.data]);
    const ids = useMemo(() => new Set(items.map((i) => i.item_id)), [items]);

    const mutation = useMutation({
        mutationFn: ({ product, saved }) =>
            saved
                ? api.saved.remove(product.id)
                : api.saved.add({
                    item_id: product.id,
                    title: product.title,
                    image_url: product.image_url ?? null,
                    item_url: product.item_url ?? null,
                    price: product.price,
                    currency: product.currency,
                    price_lkr: product.price_lkr ?? null,
                }),
        onMutate: async ({ product, saved }) => {
            await qc.cancelQueries({ queryKey: ["saved"] });
            const previous = qc.getQueryData(["saved"]) ?? [];
            qc.setQueryData(
                ["saved"],
                saved
                    ? previous.filter((i) => i.item_id !== product.id)
                    : [
                        {
                            item_id: product.id,
                            title: product.title,
                            image_url: product.image_url ?? null,
                            item_url: product.item_url ?? null,
                            price: product.price,
                            currency: product.currency,
                            price_lkr: product.price_lkr ?? null,
                            created_at: new Date().toISOString(),
                        },
                        ...previous,
                    ],
            );
            return { previous };
        },
        onError: (_err, _vars, ctx) => {
            qc.setQueryData(["saved"], ctx?.previous ?? []);
            toast("Could not update saved items", "error");
        },
        onSettled: () => qc.invalidateQueries({ queryKey: ["saved"] }),
    });

    const toggle = useCallback(
        (product) => {
            if (!user) {
                toast("Sign in to save items");
                openAuth("login");
                return;
            }
            const saved = ids.has(product.id);
            mutation.mutate({ product, saved });
            toast(saved ? "Removed from saved" : "Saved for later");
        },
        [user, ids, mutation, openAuth],
    );

    return { items, ids, toggle, isLoading: query.isLoading };
}