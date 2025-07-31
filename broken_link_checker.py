import argparse
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import concurrent.futures
import sys

TIMEOUT = 5
MAX_WORKERS = 10
USER_AGENT = "BrokenLinkChecker/1.0 (+https://example.com)"

def fetch_page(url):
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[!] Failed to fetch base page {url}: {e}", file=sys.stderr)
        return ""

def extract_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        links.add(full.split("#")[0])
    return sorted(links)

def check_link(url):
    try:
        resp = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
        status = resp.status_code
        if status >= 400:
            return (url, False, status)
        return (url, True, status)
    except requests.RequestException as e:
        return (url, False, str(e))

def main():
    parser = argparse.ArgumentParser(description="Broken Link Checker CLI Tool")
    parser.add_argument("url", help="URL of the page to scan, e.g., https://example.com")
    args = parser.parse_args()

    base = args.url
    if not base.startswith(("http://", "https://")):
        base = "http://" + base

    print(f"Scanning {base} ...")
    html = fetch_page(base)
    if not html:
        print("Cannot proceed without fetching the base page.", file=sys.stderr)
        sys.exit(1)

    links = extract_links(base, html)
    print(f"Found {len(links)} links. Checking...")

    broken = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_link, url): url for url in links}
        for fut in concurrent.futures.as_completed(future_to_url):
            url, ok, status = fut.result()
            if not ok:
                broken.append((url, status))
                print(f"[BROKEN] {url} -> {status}")
            else:
                print(f"[OK] {url} -> {status}")

    print("\nSummary:")
    print(f"Total links checked: {len(links)}")
    print(f"Broken links: {len(broken)}")
    if broken:
        print("\nList of broken links:")
        for url, reason in broken:
            print(f" - {url} ({reason})")

if __name__ == "__main__":
    main()
