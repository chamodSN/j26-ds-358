from huggingface_hub import hf_hub_download
import pyarrow.parquet as pq

print("Accessing Amazon Electronics metadata...")

file_path = hf_hub_download(
    repo_id="McAuley-Lab/Amazon-Reviews-2023",
    repo_type="dataset",
    filename="raw_meta_Electronics/full-00000-of-00010.parquet",
)

table = pq.read_table(file_path).slice(0, 5)

for index, product in enumerate(table.to_pylist(), start=1):
    print(f"\nProduct {index}")
    print("Title:", product.get("title"))
    print("Main category:", product.get("main_category"))
    print("Categories:", product.get("categories"))
    print("Parent ASIN:", product.get("parent_asin"))
