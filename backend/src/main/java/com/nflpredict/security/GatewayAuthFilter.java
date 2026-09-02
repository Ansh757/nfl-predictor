package com.nflpredict.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.logging.Logger;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * A shared secret in front of everything that changes state or costs real work.
 *
 * <p>Before this, {@code POST /api/gateway/predictions/{id}/settle} took an
 * arbitrary {@code actualWinner} from a query parameter with no authentication
 * and no check against the real result. One request could mark a prediction
 * settled with a fabricated winner - and because settlement only revisits
 * unsettled rows, the weekly job would then skip it forever. The number the
 * whole gateway exists to produce could be quietly and permanently corrupted by
 * anyone who knew the URL, and the URL has to be public for the scheduled
 * workflows to reach it.
 *
 * <p>Deliberately not Spring Security. The requirement is one constant-time
 * string comparison on a handful of routes; a full security starter would be
 * more configuration to get wrong, and its defaults (CSRF, session management,
 * a login page) mean nothing for a machine-to-machine endpoint.
 *
 * <p><strong>Fails closed.</strong> With no secret configured the protected
 * routes return 503 rather than running unauthenticated. A deployment that
 * forgets the variable therefore breaks loudly in the workflow logs instead of
 * silently serving the same hole this was written to close.
 */
@Component
public class GatewayAuthFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Gateway-Token";

    private static final Logger logger = Logger.getLogger(GatewayAuthFilter.class.getName());

    /**
     * Read-only and cheap: the dashboard reads accuracy, and the health check
     * has to answer before anything is configured. Everything else is either a
     * write or a fan-out of agent calls that costs upstream quota and CPU.
     */
    private static final List<String> PUBLIC_PATHS = List.of(
            "/api/health",
            "/api/gateway/accuracy",
            "/api/gateway/weights"
    );

    private final String secret;

    public GatewayAuthFilter(@Value("${gateway.auth.token:}") String secret) {
        this.secret = secret == null ? "" : secret.trim();
    }

    /** Only guard the gateway's own surface; static assets and health are open. */
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (PUBLIC_PATHS.contains(path)) {
            return true;
        }
        // Everything under /api/gateway is protected, plus the proxy endpoints,
        // which run the agents and so cost the same as a direct call.
        return !(path.startsWith("/api/gateway") || path.equals("/predict"));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        if (secret.isEmpty()) {
            logger.severe("gateway.auth.token is not set - refusing " + request.getRequestURI()
                    + ". Set GATEWAY_AUTH_TOKEN on the service.");
            deny(response, HttpServletResponse.SC_SERVICE_UNAVAILABLE,
                    "Gateway auth is not configured.");
            return;
        }

        String presented = request.getHeader(HEADER);
        if (presented == null || !constantTimeEquals(presented, secret)) {
            // No detail about why. A caller that knows the header name and a
            // caller guessing look identical from out here.
            deny(response, HttpServletResponse.SC_UNAUTHORIZED, "Unauthorized.");
            return;
        }

        chain.doFilter(request, response);
    }

    /**
     * Compares in time independent of how far the strings match, so a caller
     * cannot narrow the secret a character at a time by measuring responses.
     */
    private static boolean constantTimeEquals(String presented, String expected) {
        return MessageDigest.isEqual(
                presented.getBytes(StandardCharsets.UTF_8),
                expected.getBytes(StandardCharsets.UTF_8));
    }

    private static void deny(HttpServletResponse response, int status, String message)
            throws IOException {
        response.setStatus(status);
        response.setContentType("application/json");
        response.getWriter().write("{\"error\":\"" + message + "\"}");
    }
}
