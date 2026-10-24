# Deployment paths

For a step-by-step beginner EC2 deployment and the extra ECS/RDS migration work, read [the AWS walkthrough](../docs/AWS_DEPLOYMENT.md).

Local verification comes first. Both paths run exactly the same Python artifacts and evaluation reports; neither converts the model to JavaScript.

## Complete container deployment

1. Train both profiles on the laptop using the root README. Keep the complete version directories and current-pointer files under backend/models/v2 and backend/reports/v2.
2. Copy .env.production.example to .env.production. Generate unique passwords and a URL-safe API token (at least 32 characters). Never put credentials in VITE_ variables.
3. Run:
   ```sh
   docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
   docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
   ```
4. The private gateway binds to 127.0.0.1:8080. Authenticate using ANALYST_USER / ANALYST_PASSWORD. For a cloud VM, terminate HTTPS at your AWS/GCP ingress and forward only to this gateway. Never expose the PostgreSQL container.
5. The /service/ prefix is token-authenticated API ingress for Sites or another trusted server. It strips /service before forwarding to Python. Browser /api/ requests instead use the private gateway's Basic authentication and its server-held API token.
6. Back up the PostgreSQL volume. Model directories are read-only at serving time. Deploy a complete new model/report version and restart API workers; do not replace a live model in place.
7. For managed PostgreSQL, supply a percent-encoded DATABASE_URL with sslmode=require. In a cloud orchestrator, omit the bundled postgres service, run the migrate command once against that database, then start backend workers and the web gateway. Grant the migration role schema access; no role needs CREATE DATABASE.

The included production Compose is an operational container layout, not AWS/GCP account provisioning. Secrets, domain, certificates, backups and resource sizes must be configured in the selected account.

## Sites website + Python server

Sites supports a different runtime from this Python ML stack. Keep Python on the container host above. The Python service still owns PostgreSQL persistence and all scoring.

1. Run the frontend build, then `node deploy/sites/build.mjs` from the project root.
2. This stages a self-contained Worker entry at artifacts/sites/worker/index.js, embedding the built React assets. It respects the Sites Worker ESM starter's single-file packaging contract; it needs no ASSETS binding.
3. In the later Sites workflow, create/select an owner-private Site using its supported Worker ESM starter. Copy the staged entry into worker/index.js in that checkout. Preserve the starter build scripts and its hosting manifest/identity.
4. Configure BACKEND_URL and API_ACCESS_TOKEN through Sites runtime secrets. For the full container gateway, use BACKEND_URL=https://your-domain.example/service. The same API token must be configured in the Python service.
5. Publish using the Sites plugin workflow after local acceptance. No Site, domain, credential or cloud account is created by the build script.
6. The Worker requires the platform's authenticated-user header for API access, strips visitor credentials, adds only its server-held backend token, and refuses backend redirects. Keep the Site private; changing to a public multi-user service requires a separate data-ownership design.

Validate the proxy with `node --test deploy/sites/worker.test.mjs`. After a deployment, verify actual scoring, persisted logs, CSV upload, report version matching and unavailable-backend feedback. A static page alone is insufficient.
