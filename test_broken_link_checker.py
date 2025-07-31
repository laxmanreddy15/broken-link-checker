from broken_link_checker import extract_links

def test_extract_links_basic():
    html = '''
    <html><body>
      <a href="https://example.com/page1">Page1</a>
      <a href="/about">About</a>
      <a href="#fragment">Fragment</a>
    </body></html>
    '''
    links = extract_links("https://example.com", html)
    assert "https://example.com/page1" in links
    assert "https://example.com/about" in links
    assert all("#" not in link for link in links)
