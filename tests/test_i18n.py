from __future__ import annotations

from app.i18n import SUPPORTED, TRANSLATIONS, resolve_lang


def _request(cookie: str | None = None, accept: str | None = None):
    class _Req:
        cookies = {"lang": cookie} if cookie else {}
        headers = {"accept-language": accept} if accept else {}
    return _Req()


def test_cookie_sets_the_language():
    assert resolve_lang(_request(cookie="fr", accept="en-US,en")) == "fr"
    assert resolve_lang(_request(cookie="en", accept="fr-FR")) == "en"


def test_invalid_cookie_falls_back_to_english():
    assert resolve_lang(_request(cookie="de", accept="fr-FR,fr;q=0.9")) == "en"


def test_browser_language_is_ignored():
    assert resolve_lang(_request(accept="fr-FR,fr;q=0.9,en;q=0.8")) == "en"
    assert resolve_lang(_request(accept="de-DE,de;q=0.9")) == "en"


def test_default_is_english():
    assert resolve_lang(_request()) == "en"


def test_translation_key_parity():
    assert set(TRANSLATIONS) == set(SUPPORTED)
    en, fr = TRANSLATIONS["en"], TRANSLATIONS["fr"]
    assert set(en.keys()) == set(fr.keys())
    for nested in ("groups", "methods", "states", "serving_modes"):
        assert set(en[nested].keys()) == set(fr[nested].keys())
