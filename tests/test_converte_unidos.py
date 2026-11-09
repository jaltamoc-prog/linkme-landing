from app import app


def test_home_mentions_product_family():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"CONVERTE UNIDOS" in response.data
    assert b"/converte-unidos/" in response.data
    assert b'href="/converte-unidos/" target="_blank" rel="noopener noreferrer"' in response.data


def test_converte_unidos_landing():
    client = app.test_client()
    response = client.get("/converte-unidos/")
    assert response.status_code == 200
    assert b"$5,500" in response.data
    assert b"Renovaci\xc3\xb3n autom\xc3\xa1tica cada 12 meses" in response.data
    assert b"Primer pago de contado o a meses" in response.data
    assert b"$2,797" not in response.data
    assert b"$997" not in response.data
    assert b"$297" not in response.data
    assert b"meses sin intereses" not in response.data.lower()


def test_sitemap_contains_converte_unidos():
    client = app.test_client()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert b"https://converte.uno/converte-unidos/" in response.data
