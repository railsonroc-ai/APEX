from flask import Flask

import backend.security as security


def create_test_app():
    return Flask(
        __name__
    )


def test_development_without_access_key_allows_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "development",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "",
    )

    app = create_test_app()

    with app.test_request_context(
        "/"
    ):
        assert (
            security.verify_auth()
            is True
        )


def test_production_without_access_key_blocks_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "production",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "",
    )

    app = create_test_app()

    with app.test_request_context(
        "/"
    ):
        assert (
            security.verify_auth()
            is False
        )


def test_correct_access_key_allows_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "production",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "chave-correta",
    )

    app = create_test_app()

    with app.test_request_context(
        "/",
        headers={
            "X-Apex-Key":
                "chave-correta",
        },
    ):
        assert (
            security.verify_auth()
            is True
        )


def test_wrong_access_key_blocks_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "production",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "chave-correta",
    )

    app = create_test_app()

    with app.test_request_context(
        "/",
        headers={
            "X-Apex-Key":
                "chave-errada",
        },
    ):
        assert (
            security.verify_auth()
            is False
        )