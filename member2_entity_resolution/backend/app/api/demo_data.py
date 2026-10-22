"""Small hand-made demo batch (invented listings, three shops, mixed attribute names / units)."""
DEMO_LISTINGS = [
    dict(id="a1", source="shopA", title="Samsung 970 EVO Plus 500GB NVMe M.2 SSD",
         attributes={"Brand": "Samsung", "Capacity": "500 GB", "Interface": "NVMe", "Weight": "8 g"}),
    dict(id="b1", source="shopB", title="Samsung SSD 970 EVO Plus 500 GB M.2 NVMe",
         attributes={"Merk": "Samsung", "Capacity": "500GB", "Weight": "0.008 kg", "Warranty": "5 years"}),
    dict(id="a2", source="shopA", title="Samsung 970 EVO Plus 1TB NVMe M.2 SSD",
         attributes={"Brand": "Samsung", "Capacity": "1 TB", "Interface": "NVMe"}),
    dict(id="b2", source="shopB", title="Samsung SSD 970 EVO Plus 1 TB M.2 NVMe",
         attributes={"Merk": "Samsung", "Capacity": "1000 GB"}),
    dict(id="a3", source="shopA", title="Seagate IronWolf Pro 10TB 3.5 inch NAS HDD ST10000NE0004",
         attributes={"Brand": "Seagate", "Capacity": "10 TB", "Spindle Speed": "7200RPM"}),
    dict(id="b3", source="shopB", title="Seagate ST10000NE0004 IronWolf Pro 10 TB NAS harde schijf",
         attributes={"Merk": "Seagate", "Capacity": "10TB", "Rotational Speed": "7200 RPM"}),
    dict(id="c1", source="shopC", title="Corsair Vengeance LPX 16GB (2x8GB) DDR4 3200MHz",
         attributes={"Brand": "Corsair", "Capacity": "2 x 8 GB", "Speed": "3200 MHz", "Max Resolution DP": "[email\u00a0protected]"}),
]