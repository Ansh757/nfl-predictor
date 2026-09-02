"""
Security regressions.

Each case here corresponds to something that was actually wrong, not a
hypothetical. The traversal guard in particular was written once, deleted by an
unrelated refactor while its call site stayed, and shipped broken for weeks -
these exist so that deletion fails the build instead.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402
from main import _resolve_within_build, app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestPathTraversal:
    """
    The SPA catch-all joins a user-controlled path onto the build directory.
    Two escapes are easy to miss: percent-encoded '../' arrives as literal path
    segments, and os.path.join() throws the base away entirely when the second
    argument is absolute.
    """

    # These are what the function actually receives: Starlette percent-decodes
    # the path before it reaches the route, so the encoded variants are tested
    # over HTTP below rather than here.
    @pytest.mark.parametrize("attack", [
        "../../../etc/passwd",
        "../../.env",
        "/etc/passwd",              # absolute: join() discards the base
        "static/../../../../etc/hosts",
        "../" * 12 + "etc/passwd",
    ])
    def test_escape_attempts_are_refused(self, attack):
        assert _resolve_within_build(attack) is None, f"{attack!r} escaped the build directory"

    def test_literal_dots_are_not_traversal(self, attack=None):
        # '....//' defeats filters that strip '../' by rewriting. This one does
        # not strip anything - realpath treats '....' as an ordinary directory
        # name, so the path stays inside the build root and simply does not
        # exist. Pinned so nobody "fixes" it into a rejection and assumes the
        # stripping approach is what keeps this safe.
        resolved = _resolve_within_build("....//....//etc/passwd")
        assert resolved is not None
        assert resolved.startswith(os.path.realpath(main.demo_build))
        assert not os.path.isfile(resolved)

    @pytest.mark.parametrize("legitimate", [
        "index.html",
        "static/js/main.js",
        "",
    ])
    def test_real_assets_still_resolve(self, legitimate):
        resolved = _resolve_within_build(legitimate)
        assert resolved is not None
        assert resolved.startswith(os.path.realpath(main.demo_build))

    def test_the_function_the_route_calls_actually_exists(self):
        # The precise failure that shipped: the call site referenced a function
        # an unrelated commit had deleted, so every unknown path raised
        # NameError and returned 500 instead of the SPA.
        assert callable(getattr(main, "_resolve_within_build", None))

    @pytest.mark.skipif(not os.path.exists(os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "..", "demo", "build", "index.html")),
        reason="frontend build not present")
    def test_unknown_route_serves_the_spa_not_an_error(self, client):
        response = client.get("/some-unknown-route")
        assert response.status_code == 200, "the catch-all must fall back to index.html"

    @pytest.mark.parametrize("attack", [
        "/../../../../etc/passwd",
        "/..%2f..%2f..%2fetc%2fpasswd",
        "/%2e%2e/%2e%2e/.env",
        "/static/../../../.env",
    ])
    def test_traversal_over_http_does_not_return_a_secret(self, client, attack):
        # End to end, after Starlette has decoded the path. Whatever comes back
        # must not be a file from outside the build directory.
        response = client.get(attack)
        assert response.status_code in (200, 404)
        assert "root:" not in response.text
        assert "ODDS_API_KEY" not in response.text


class TestSecurityHeaders:
    def test_hardening_headers_are_present(self, client):
        headers = client.get("/health").headers
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "max-age=" in headers["Strict-Transport-Security"]
        assert headers["Referrer-Policy"]

    def test_csp_locks_scripts_to_this_origin(self, client):
        csp = client.get("/health").headers["Content-Security-Policy"]
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp
        # The dashboard loads team logos from ESPN and nothing else third-party
        assert "https://a.espncdn.com" in csp

    def test_csp_does_not_allow_unsafe_scripts(self, client):
        csp = client.get("/health").headers["Content-Security-Policy"]
        script_directive = [d for d in csp.split(";") if d.strip().startswith("script-src")][0]
        assert "unsafe-inline" not in script_directive
        assert "unsafe-eval" not in script_directive


class TestErrorDisclosure:
    def test_internal_detail_is_logged_not_returned(self):
        # str(e) used to go straight to the client, which for a sqlite or httpx
        # failure means leaking file paths and SQL fragments.
        error = main._server_error("Prediction", RuntimeError("/srv/app/secret.db is locked"))
        assert "secret.db" not in error.detail
        assert error.status_code == 500
        assert "Prediction" in error.detail


class TestRateLimiting:
    def test_expensive_endpoints_are_limited(self):
        limit, window = main._RATE_LIMITS["/predict"]
        assert limit > 0 and window > 0
        prefix, found = main._rate_limit_for("/predict")
        assert prefix == "/predict" and found == (limit, window)

    def test_cheap_endpoints_are_not_limited(self):
        assert main._rate_limit_for("/health") == (None, None)
        assert main._rate_limit_for("/games/week/1") == (None, None)

    def test_refresh_is_limited_hardest(self):
        # Each call re-pulls eighteen weeks from ESPN, an upstream we do not own
        predict_calls, predict_window = main._RATE_LIMITS["/predict"]
        refresh_calls, refresh_window = main._RATE_LIMITS["/games/refresh"]
        assert refresh_calls / refresh_window < predict_calls / predict_window

    def test_a_flood_is_refused_with_retry_after(self, client):
        limit, _ = main._RATE_LIMITS["/agents/status"] if "/agents/status" in main._RATE_LIMITS \
            else main._RATE_LIMITS["/predict"]
        main._rate_state.clear()
        payload = {"game_data": {"game_id": 1, "home_team_name": "A", "away_team_name": "B"}}

        statuses = [client.post("/predict", json=payload).status_code for _ in range(limit + 3)]
        assert 429 in statuses, "the limiter never engaged"
        first_429 = statuses.index(429)
        assert first_429 >= limit, "refused before the limit was reached"

        blocked = client.post("/predict", json=payload)
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        main._rate_state.clear()
