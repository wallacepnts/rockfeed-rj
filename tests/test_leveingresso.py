from unittest.mock import MagicMock, patch

from app.scrapers.leveingresso import LeveIngressoScraper

PAGE_HTML = """
<html><head>
<meta property="og:title" content="12/09 - RODOX - SÃO GONÇALO/RJ"/>
<meta property="og:image" content="https://leveingresso.com/images/img.png"/>
</head><body>
<div class="prs_es_left_map_section_wrapper dado-event">
  <h3>12 de setembro de 2026</h3>
  <div class="smalltext">
    <ul>
      <li>Endereço: Rua Coronel Serrado 926, Zé Garoto. São Gonçalo RJ - SÃO GONÇALO - RJ</li>
      <li>Local: ROXX MUSIC</li>
      <li>Abertura das Portas:  19h00</li>
      <li>Início do Evento:  20h00</li>
      <li>Classificação: +18</li>
    </ul>
  </div>
</div>
<div id="menu1" class="tab-pane fade">
  <div class="prs_es_tabs_event_sche_main_box_wrapper">
    <div class="prs_es_tabs_event_sche_img_cont_wrapper">
      <strong>RODOX: UM RETORNO HIST&Oacute;RICO AOS PALCOS</strong><br/>
      O Rodox retorna aos palcos.
    </div>
  </div>
</div>
<div id="menu2" class="tab-pane fade">
  <div class="prs_es_tabs_event_sche_main_box_wrapper">
    <div class="prs_es_tabs_event_sche_img_cont_wrapper">
      Texto de outra aba que não é a descrição.
    </div>
  </div>
</div>
<input type="hidden" value="200" name="valor4491" id="valor4491">
<input type="hidden" value="230" name="valorTot4491" id="valorTot4491">
<input type="hidden" value="100" name="valor4498" id="valor4498">
</body></html>
"""


def make_client(html_text):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.text = html_text

    client = MagicMock()
    client.get.return_value = resp
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_event_page():
    client = make_client(PAGE_HTML)
    url = "https://leveingresso.com/comprar/518/12-09-rodox-sao-goncalo-rj"

    with patch("app.scrapers.leveingresso.get_client") as gc, \
         patch("app.scrapers.leveingresso.EVENTS", [(url, None)]):
        gc.return_value = client
        events = LeveIngressoScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "12/09 - RODOX - SÃO GONÇALO/RJ"
    assert e.url == url
    assert e.venue == "ROXX MUSIC"
    assert e.address == "Rua Coronel Serrado 926, Zé Garoto. São Gonçalo RJ - SÃO GONÇALO - RJ"
    assert e.city == "SÃO GONÇALO"
    assert e.date.isoformat() == "2026-09-12T20:00:00-03:00"
    assert e.price == "R$ 100.00"
    assert e.image == "https://leveingresso.com/images/img.png"
    assert e.organizer == ""
    assert "RODOX: UM RETORNO" in e.description
    assert "outra aba" not in e.description


def test_organizer_override_is_used():
    client = make_client(PAGE_HTML)
    url = "https://leveingresso.com/comprar/518/12-09-rodox-sao-goncalo-rj"

    with patch("app.scrapers.leveingresso.get_client") as gc, \
         patch("app.scrapers.leveingresso.EVENTS", [(url, "Produtora X")]):
        gc.return_value = client
        events = LeveIngressoScraper().fetch()

    assert events[0].organizer == "Produtora X"


def test_fetch_failure_is_skipped_not_fatal():
    client = MagicMock()
    client.get.side_effect = __import__("httpx").HTTPError("boom")
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("app.scrapers.leveingresso.get_client") as gc, \
         patch("app.scrapers.leveingresso.EVENTS", [("https://leveingresso.com/comprar/1/x", None)]):
        gc.return_value = client
        events = LeveIngressoScraper().fetch()

    assert events == []
