from app import app


def test_home_mentions_product_family():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"CONVERTE UNIDOS" in response.data
    assert b"/converte-unidos/" in response.data


def test_converte_unidos_landing():
    client = app.test_client()
    response = client.get("/converte-unidos/")
    assert response.status_code == 200
    assert b"3 \xc3\x97 $997" in response.data
    assert b"12 \xc3\x97 $297" in response.data
    assert b"pago diferido con costo" in response.data.lower()
    assert b"meses sin intereses" not in response.data.lower()


def test_sitemap_contains_converte_unidos():
    client = app.test_client()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert b"https://converte.uno/converte-unidos/" in response.data
