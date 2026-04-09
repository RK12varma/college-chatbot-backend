import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def crawl_site(start_url, max_pages=10):

    visited = set()
    to_visit = [start_url]
    pdf_links = []

    base_domain = urlparse(start_url).netloc

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)

        if url in visited:
            continue

        visited.add(url)

        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")

            for link in soup.find_all("a", href=True):
                full_url = urljoin(url, link["href"])

                if full_url.endswith(".pdf"):
                    pdf_links.append(full_url)

                elif urlparse(full_url).netloc == base_domain:
                    if full_url not in visited:
                        to_visit.append(full_url)

        except:
            continue

    return list(set(pdf_links))