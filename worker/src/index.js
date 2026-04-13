/**
 * Apple OAuth Callback Relay Worker
 *
 * Apple Sign In sends a POST to https://dlopro.com/callback with form data
 * containing `code` and `state`. This worker extracts them and redirects
 * the browser to the CLI's local server on 127.0.0.1.
 *
 * The local port is encoded in the state parameter as: {random_hex}:{port}
 */

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/") {
      return new Response("Account Hub OAuth Relay", { status: 200 });
    }

    // Only handle /callback
    if (url.pathname !== "/callback") {
      return new Response("Not found", { status: 404 });
    }

    // Apple sends a POST with form data (response_mode=form_post)
    if (request.method === "POST") {
      const formData = await request.formData();
      const code = formData.get("code");
      const state = formData.get("state");
      const idToken = formData.get("id_token");

      if (!code || !state) {
        return new Response("Missing code or state", { status: 400 });
      }

      // Extract port from state: format is {random_hex}:{port}
      const parts = state.split(":");
      const port = parts.length >= 2 ? parts[parts.length - 1] : null;

      if (!port || isNaN(parseInt(port))) {
        // Can't determine port — show the code to the user
        return new Response(
          `<html><body>
            <h2>Authorization received</h2>
            <p>Copy this code back to your terminal:</p>
            <pre>Code: ${code}\nState: ${state}</pre>
          </body></html>`,
          { status: 200, headers: { "Content-Type": "text/html" } }
        );
      }

      // Redirect to CLI's local server
      const params = new URLSearchParams({ code, state });
      if (idToken) params.set("id_token", idToken);
      const redirectUrl = `http://127.0.0.1:${port}/callback?${params.toString()}`;

      return Response.redirect(redirectUrl, 302);
    }

    // GET requests (fallback — some providers use GET)
    if (request.method === "GET") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");

      if (!code || !state) {
        return new Response("Missing code or state", { status: 400 });
      }

      const parts = state.split(":");
      const port = parts.length >= 2 ? parts[parts.length - 1] : null;

      if (!port || isNaN(parseInt(port))) {
        return new Response(
          `<html><body>
            <h2>Authorization received</h2>
            <p>Copy this code back to your terminal:</p>
            <pre>Code: ${code}\nState: ${state}</pre>
          </body></html>`,
          { status: 200, headers: { "Content-Type": "text/html" } }
        );
      }

      const params = new URLSearchParams({ code, state });
      const redirectUrl = `http://127.0.0.1:${port}/callback?${params.toString()}`;
      return Response.redirect(redirectUrl, 302);
    }

    return new Response("Method not allowed", { status: 405 });
  },
};
