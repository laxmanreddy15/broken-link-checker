import argparse
import requests
import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import concurrent.futures
import json
import csv

# === Global defaults ===
TIMEOUT = 10         # default request timeout
MAX_WORKERS = 10     # default thread pool size

def fetch_page(url):
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Warning: {url} returned {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for tag in soup.find_all("a", href=True):
        href = tag.get("href")
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme in ["http", "https"]:
            links.add(full_url)
    return list(links)

def check_link(url):
    try:
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code >= 400:
            return (url, False, response.status_code)
        return (url, True, response.status_code)
    except Exception as e:
        return (url, False, str(e))

def crawl(base_url, depth, same_domain_only=True):
    visited = set()
    to_visit = [(base_url, 0)]
    all_links = set()
    base_domain = urlparse(base_url).netloc

    while to_visit:
        current_url, current_depth = to_visit.pop()
        if current_url in visited or current_depth > depth:
            continue
        visited.add(current_url)

        html = fetch_page(current_url)
        if not html:
            continue

        links = extract_links(current_url, html)
        for link in links:
            if same_domain_only and urlparse(link).netloc != base_domain:
                continue
            all_links.add(link)
            if current_depth < depth:
                to_visit.append((link, current_depth + 1))

    return list(all_links)

def output_broken(broken, fmt):
    filename = f"broken_links.{fmt}"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        if fmt == "json":
            json.dump(broken, f, indent=2)
        elif fmt == "csv":
            writer = csv.writer(f)
            writer.writerow(["URL", "Error"])
            writer.writerows(broken)
    print(f"Saved report to {filename}")

def main():
    global TIMEOUT, MAX_WORKERS

    parser = argparse.ArgumentParser(description="Broken Link Checker CLI Tool")
    parser.add_argument("url", help="URL of the page to scan, e.g., https://example.com")
    parser.add_argument("--same-domain", action="store_true",
                        help="Only check links on the same domain as the base URL")
    parser.add_argument("--depth", "-d", type=int, default=0,
                        help="Crawl link graph up to this depth (0 = only initial page)")
    parser.add_argument("--output", "-o", choices=["json", "csv"],
                        help="Save broken links report to file (json or csv)")
    parser.add_argument("--workers", "-w", type=int, default=MAX_WORKERS,
                        help="Concurrency level")
    parser.add_argument("--timeout", "-t", type=int, default=TIMEOUT,
                        help="Per-request timeout in seconds")
    args = parser.parse_args()

    TIMEOUT = args.timeout
    MAX_WORKERS = args.workers

    base = args.url
    if not base.startswith(("http://", "https://")):
        base = "http://" + base

    print(f"Scanning {base} ... (depth={args.depth}, same-domain={args.same_domain})")
    if args.depth > 0:
        links = crawl(base, args.depth, same_domain_only=args.same_domain)
    else:
        html = fetch_page(base)
        if not html:
            print("Cannot proceed without fetching the base page.", file=sys.stderr)
            sys.exit(1)
        links = extract_links(base, html)
        if args.same_domain:
            base_parsed = urlparse(base)
            links = [l for l in links if urlparse(l).netloc == base_parsed.netloc]

    if not links:
        print("No links found.")
        return

    print(f"Found {len(links)} unique links. Checking...")

    broken = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_link, url): url for url in links}
        for fut in concurrent.futures.as_completed(future_to_url):
            url, ok, status = fut.result()
            if not ok:
                broken.append((url, status))
                print(f"[BROKEN] {url} -> {status}")
            else:
                print(f"[OK]     {url} -> {status}")

    print("\nSummary:")
    print(f"Total links checked: {len(links)}")
    print(f"Broken links: {len(broken)}")
    if broken:
        print("\nList of broken links:")
        for url, reason in broken:
            print(f" - {url} ({reason})")
        if args.output:
            output_broken(broken, args.output)
        sys.exit(2)
    else:
        print("All links are healthy.")
        sys.exit(0)

if __name__ == "__main__":
    main()
