import requests
from bs4 import BeautifulSoup

def is_valid_url(url):
    import validators
    from urllib.parse import urlparse
    if not validators.url(url):
        return False
    parsed_url = urlparse(url)
    allowed_domains = ["example.com", "allowed-domain.com"]
    if parsed_url.netloc not in allowed_domains:
        return False
    return True

def get_html_content(url):
    if not is_valid_url(url):
        raise ValueError("Invalid or unauthorized URL provided.")
    response = requests.get(url)
    return response.content

def get_plain_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for script in soup(["script"]):
        script.extract()
    return soup.get_text()


def split_text_into_chunks(plain_text, max_chars=2000):
    text_chunks = []
    current_chunk = ""
    for line in plain_text.split("\n"):
        if len(current_chunk) + len(line) + 1 <= max_chars:
            current_chunk += line + " "
        else:
            text_chunks.append(current_chunk.strip())
            current_chunk = line + " "
    if current_chunk:
        text_chunks.append(current_chunk.strip())
    return text_chunks

    if not is_valid_url(url):
        raise ValueError("Invalid or unauthorized URL provided.")
def scrape_text_from_url(url, max_chars=2000):
    html_content = get_html_content(url)
    plain_text = get_plain_text(html_content)
    text_chunks = split_text_into_chunks(plain_text, max_chars)
    return text_chunks