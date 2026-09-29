// Real, working search-results URLs on the actual platform sites.
// These aren't links to a specific (fictional) listing — they're a live
// search for the product name on the real store, so nothing 404s even
// though the underlying catalog here is dummy data.
export function originalListingUrl(platform, title) {
    const q = encodeURIComponent(title);
    switch (platform) {
        case "Daraz":
            return `https://www.daraz.lk/catalog/?q=${q}`;
        case "AliExpress":
            return `https://www.aliexpress.com/wholesale?SearchText=${q}`;
        case "Alibaba":
            return `https://www.alibaba.com/trade/search?SearchText=${q}`;
        case "Amazon":
            return `https://www.amazon.in/s?k=${q}`;
        default:
            return "#";
    }
}