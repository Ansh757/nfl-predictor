package com.nflpredict.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import jakarta.servlet.FilterChain;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

/**
 * The hole this closes: POST /api/gateway/predictions/{id}/settle accepted an
 * arbitrary actualWinner with no authentication, and settlement never revisits
 * a settled row - so a single unauthenticated request could permanently corrupt
 * the accuracy figure. The gateway has to be publicly reachable for the
 * scheduled workflows, so "nobody knows the URL" was never the answer.
 */
class GatewayAuthFilterTest {

    private static final String SECRET = "s3cr3t-token-value";
    private static final String SETTLE = "/api/gateway/predictions/1/settle";

    private MockHttpServletRequest request(String path, String token) {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", path);
        request.setRequestURI(path);
        if (token != null) {
            request.addHeader(GatewayAuthFilter.HEADER, token);
        }
        return request;
    }

    private MockHttpServletResponse runFilter(GatewayAuthFilter filter,
                                              MockHttpServletRequest request,
                                              FilterChain chain) throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, chain);
        return response;
    }

    @Test
    @DisplayName("settling without a token is refused")
    void settleWithoutTokenIsRefused() throws Exception {
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletResponse response =
                runFilter(new GatewayAuthFilter(SECRET), request(SETTLE, null), chain);

        assertEquals(HttpServletResponse.SC_UNAUTHORIZED, response.getStatus());
        verify(chain, never()).doFilter(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("settling with the wrong token is refused")
    void settleWithWrongTokenIsRefused() throws Exception {
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletResponse response =
                runFilter(new GatewayAuthFilter(SECRET), request(SETTLE, "not-the-token"), chain);

        assertEquals(HttpServletResponse.SC_UNAUTHORIZED, response.getStatus());
        verify(chain, never()).doFilter(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("settling with the right token is allowed through")
    void settleWithCorrectTokenPasses() throws Exception {
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletResponse response =
                runFilter(new GatewayAuthFilter(SECRET), request(SETTLE, SECRET), chain);

        assertEquals(HttpServletResponse.SC_OK, response.getStatus());
        verify(chain).doFilter(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("an unconfigured secret fails closed, not open")
    void missingSecretRefusesRatherThanAllows() throws Exception {
        // The dangerous default would be to skip the check when no token is
        // set: a deploy that forgot the variable would silently serve the same
        // hole. 503 breaks the workflow loudly instead.
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletResponse response =
                runFilter(new GatewayAuthFilter(""), request(SETTLE, "anything"), chain);

        assertEquals(HttpServletResponse.SC_SERVICE_UNAVAILABLE, response.getStatus());
        verify(chain, never()).doFilter(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("health and accuracy stay public")
    void readOnlyEndpointsAreNotGuarded() {
        GatewayAuthFilter filter = new GatewayAuthFilter(SECRET);
        // The dashboard polls accuracy, and the health check has to answer
        // before anything is configured.
        assertTrue(filter.shouldNotFilter(request("/api/health", null)));
        assertTrue(filter.shouldNotFilter(request("/api/gateway/accuracy", null)));
        assertTrue(filter.shouldNotFilter(request("/api/gateway/weights", null)));
        assertTrue(filter.shouldNotFilter(request("/static/js/main.js", null)));
    }

    @Test
    @DisplayName("every state-changing and expensive route is guarded")
    void mutatingAndExpensiveEndpointsAreGuarded() {
        GatewayAuthFilter filter = new GatewayAuthFilter(SECRET);
        for (String path : new String[]{
                "/api/gateway/predictions/1/settle",
                "/api/gateway/settle/run",
                "/api/gateway/weights/refresh",
                "/api/gateway/predictions/week/1",   // fans out 16 agent calls
                "/api/gateway/predictions/game/1",
                "/predict"                            // runs the agents too
        }) {
            assertFalse(filter.shouldNotFilter(request(path, null)),
                    path + " must require the token");
        }
    }

    @Test
    @DisplayName("the comparison does not leak the secret through timing")
    void comparisonIsConstantTime() throws Exception {
        // A token sharing a long prefix with the real one must be refused the
        // same way as one sharing nothing, with no early return on first
        // mismatch. MessageDigest.isEqual is what provides this; the test pins
        // the behaviour so a later "simplification" to equals() is caught.
        FilterChain chain = mock(FilterChain.class);
        String almost = SECRET.substring(0, SECRET.length() - 1) + "X";
        assertEquals(HttpServletResponse.SC_UNAUTHORIZED,
                runFilter(new GatewayAuthFilter(SECRET), request(SETTLE, almost), chain).getStatus());
        assertEquals(HttpServletResponse.SC_UNAUTHORIZED,
                runFilter(new GatewayAuthFilter(SECRET), request(SETTLE, "z"), chain).getStatus());
    }
}
