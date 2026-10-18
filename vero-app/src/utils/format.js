const lkr = new Intl.NumberFormat("en-LK", { maximumFractionDigits: 0 });

export const formatLKR = (n) => (n == null ? "n/a" : `LKR ${lkr.format(Math.round(n))}`);

export function formatMoney(amount, currency = "USD") {
    try {
        return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
    } catch {
        return `${currency} ${amount}`;
    }
}

// Pulls short facts out of a listing title, like "256GB" or "5G".
export function specChips(title = "") {
    const chips = [];
    const storage = title.match(/\b(\d{2,4})\s?(GB|TB)\b/i);
    if (storage) chips.push(`${storage[1]}${storage[2].toUpperCase()}`);
    if (/\b5G\b/i.test(title)) chips.push("5G");
    if (/\bunlocked\b/i.test(title)) chips.push("Unlocked");
    if (/\boled\b/i.test(title)) chips.push("OLED");
    return chips.slice(0, 3);
}

export const CATEGORIES = [
    { key: "", label: "All" },
    { key: "phones", label: "Phones" },
    { key: "laptops", label: "Laptops" },
    { key: "tablets", label: "Tablets" },
    { key: "watches", label: "Watches" },
    { key: "audio", label: "Audio" },
    { key: "cameras", label: "Cameras" },
];

export const POPULAR_SEARCHES = [
    "iphone 13 128gb",
    "gaming laptop rtx",
    "noise cancelling headphones",
    "samsung galaxy s23",
    "mirrorless camera",
];