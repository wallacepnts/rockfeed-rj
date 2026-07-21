from app.scrapers.base import is_rock


def test_detects_rock_keyword():
    assert is_rock("Show de Rock Nacional", "Circo Voador")


def test_detects_accentless_variant():
    assert is_rock("Tributo ao Metallica")


def test_rejects_unrelated_genre():
    assert not is_rock("Roda de Samba no Rio", "Lapa")


def test_blocklist_overrides_keyword_match():
    # "forró" não deve colar mesmo se aparecer junto de um termo de rock
    assert not is_rock("Rock in Forró Especial")


def test_empty_fields_are_not_rock():
    assert not is_rock("", "", "")


def test_word_boundary_avoids_false_positive():
    # "emo" não deve casar como prefixo de outra palavra (ex: "emocionante")
    assert not is_rock("Show emocionante hoje")
    assert not is_rock("Promoção de ingressos")
