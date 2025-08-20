# crawler.py
import os, time, re, json, hashlib, urllib.robotparser
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm

SITE_ROOT = os.environ.get("SITE_ROOT", "https://harrissces.com/")
OUTPUT_DIR = os.path.join(os.environ.get("KB_DIR", "kb"))
CRAWL_DEPTH = int(os.environ.get("CRAWL_DEPTH", "3"))
RATE_LIMIT = float(os.environ.get("RATE_LIMIT_RPS", "1.0"))
ALLOW_DOMAINS = {urlparse(SITE_ROOT).netloc}

def now_iso(): return time.strftime("%Y-%m-%d")

def polite_get(session, url):
    time.sleep(1.0 / RATE_LIMIT)
    return session.get(url, timeout=20, headers={"User-Agent":"harriss-autobot/1.0"})

def allowed_by_robots(url):
    root = f"{urlparse(SITE_ROOT).scheme}://{urlparse(SITE_ROOT).netloc}"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(urljoin(root, "/robots.txt"))
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True

def is_in_scope(url):
    p = urlparse(url)
    return p.scheme in ("http","https") and p.netloc in ALLOW_DOMAINS

def extract_title(soup):
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""

def clean_html(html):
    return md(html, strip=["script","style"])

def hash_text(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def discover_from_sitemap(session):
    urls = set()
    for path in ["/sitemap.xml", "/sitemap_index.xml"]:
        sm = urljoin(SITE_ROOT, path)
        try:
            r = session.get(sm, timeout=15)
            if r.status_code == 200:
                for loc in re.findall(r"<loc>(.*?)</loc>", r.text, flags=re.I):
                    if is_in_scope(loc): urls.add(loc.strip())
        except Exception:
            pass
    return urls

def crawl():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = requests.Session()
    queue = [SITE_ROOT.rstrip("/")]
    seen = set(queue)
    # seed from sitemap
    for u in discover_from_sitemap(session):
        if u not in seen:
            queue.append(u); seen.add(u)
    depth_map = {u:0 for u in queue}
    pages = []
    pbar = tqdm(total=len(queue), desc="Crawling")
    while queue:
        url = queue.pop(0)
        pbar.update(1)
        if not allowed_by_robots(url):
            continue
        try:
            r = polite_get(session, url)
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type",""):
                continue
            soup = BeautifulSoup(r.text, "lxml")
            title = extract_title(soup)
            main = soup.body or soup
            text = clean_html(str(main))
            chash = hash_text(text)
            outlinks = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"].split("#")[0])
                if is_in_scope(href):
                    outlinks.append(href)
                    if href not in seen and depth_map[url] + 1 <= CRAWL_DEPTH:
                        queue.append(href); seen.add(href); depth_map[href]=depth_map[url]+1; pbar.total+=1
            pages.append({
                "url": url,
                "status": r.status_code,
                "title": title,
                "last_modified": r.headers.get("Last-Modified"),
                "discovered_at": now_iso(),
                "content_hash": chash,
                "outlinks": sorted(set(outlinks))
            })
        except Exception:
            continue
    pbar.close()
    with open(os.path.join(OUTPUT_DIR, "crawl_report.json"), "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    print("Crawl finished. pages:", len(pages))

if __name__ == "__main__":
    crawl()

