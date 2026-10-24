/**
 * Private Sites gateway. Copy into the supported Worker ESM starter at deployment.
 * Bind built frontend/dist as ASSETS. Configure backend URL and token as secrets.
 * No Python or database drivers run inside the Worker.
 */
export default {
  /** Serve static assets or forward a private API call with a server-side secret. */
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (!path.startsWith("/api/") && !path.startsWith("/health/"))
      return env.ASSETS.fetch(request);
    if (!request.headers.get("oai-authenticated-user-id"))
      return Response.json(
        { detail: "Sign in to this private Site." },
        { status: 401 },
      );
    if (!env.BACKEND_URL || !env.API_ACCESS_TOKEN)
      return Response.json(
        { detail: "Python service is not configured." },
        { status: 503 },
      );
    const backend = new URL(env.BACKEND_URL);
    if (backend.protocol !== "https:" || backend.username || backend.password)
      return Response.json(
        { detail: "Backend requires a credential-free HTTPS URL." },
        { status: 503 },
      );
    const incoming = new URL(request.url);
    const target = new URL(
      backend.toString().replace(/\/$/, "") +
        incoming.pathname +
        incoming.search,
    );
    const headers = new Headers();
    // Copy body/content metadata only; visitor cookies and credentials stay out.
    for (const name of ["content-type", "accept"])
      if (request.headers.has(name))
        headers.set(name, request.headers.get(name));
    headers.set("Authorization", `Bearer ${env.API_ACCESS_TOKEN}`);
    try {
      const response = await fetch(target, {
        method: request.method,
        headers,
        body: ["GET", "HEAD"].includes(request.method)
          ? undefined
          : request.body,
        redirect: "manual",
        duplex: "half",
      });
      if (response.status >= 300 && response.status < 400)
        return Response.json(
          { detail: "Unexpected backend redirect." },
          { status: 502 },
        );
      const output = new Headers();
      // Preserve download/timing metadata without forwarding arbitrary backend headers.
      for (const name of [
        "content-type",
        "content-disposition",
        "x-request-id",
        "server-timing",
      ])
        if (response.headers.has(name))
          output.set(name, response.headers.get(name));
      output.set("Cache-Control", "no-store");
      return new Response(response.body, {
        status: response.status,
        headers: output,
      });
    } catch {
      // Keep a readable outage visible instead of pretending a static page can score.
      return Response.json(
        { detail: "Python service is unavailable." },
        { status: 502 },
      );
    }
  },
};
