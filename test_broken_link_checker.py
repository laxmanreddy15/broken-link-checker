from broken_link_checker import extract_links

def test_extract_links_basic():
    html = '<a href="http://example.com">Link</a>'
    base_url = "http://test.com"
    links = extract_links(base_url, html)
    assert "http://example.com" in links
