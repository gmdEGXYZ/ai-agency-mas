import urllib.request
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.ignore_tags = {'script', 'style'}
        self.is_ignoring = False

    def handle_starttag(self, tag, attrs):
        if tag in self.ignore_tags:
            self.is_ignoring = True

    def handle_endtag(self, tag):
        if tag in self.ignore_tags:
            self.is_ignoring = False

    def handle_data(self, data):
        if not self.is_ignoring:
            self.text_parts.append(data)

    def get_text(self):
        return " ".join(self.text_parts).strip()

def fetch_webpage_text(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
            
        parser = TextExtractor()
        parser.feed(html_content)

        import re
        text = re.sub(r'\s+', ' ', parser.get_text())

        return text[:30000]
        
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"