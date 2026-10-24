# AWS deployment: EC2 first, then ECS and RDS

This walkthrough explains a deployment you can perform later. No AWS resources, credentials, domain or public site are created by reading these instructions. The repository contains a container layout, not an AWS account provisioning tool. Cloud resources can incur charges; check your account's current estimates and remove resources you no longer need.

## Contents

1. [What the files do](#what-the-files-do)
2. [Prepare an EC2 server](#prepare-an-ec2-server)
3. [Copy source and serving artifacts](#copy-source-and-serving-artifacts)
4. [Configure and start the stack](#configure-and-start-the-stack)
5. [Database creation, migrations and linking](#database-creation-migrations-and-linking)
6. [Put HTTPS in front](#put-https-in-front)
7. [Operate, back up and troubleshoot](#operate-back-up-and-troubleshoot)
8. [Move to ECS/Fargate and RDS](#move-to-ecsfargate-and-rds)

## What the files do

| File/concept | Role |
|---|---|
| `backend/Dockerfile` | Builds Python 3.11 with pinned dependencies, Linux OpenMP and non-root API code |
| `frontend/Dockerfile` | Builds React with Node, then serves compiled files through unprivileged Nginx |
| `docker-compose.yml` | Laptop container workflow, including Vite's development server |
| **`docker-compose.production.yml`** | Server workflow: PostgreSQL, migration job, Python workers and private web gateway |
| `.env.production.example` | Configuration template; replace all password/token placeholders |
| `backend/entrypoint.sh` | Starts Uvicorn API workers; migrations are a separate job |
| `backend/alembic/` | Revisions that create/upgrade tables in an already existing database |
| `frontend/deploy/nginx.conf.template` | Serves the built website and forwards API calls with a server-held token |
| Image | Built package of application code and dependencies |
| Container | A running instance of an image |
| Compose network | Private connection between containers, including service-name DNS |
| Named volume | Storage that survives replacing a container; PostgreSQL uses `postgres_data` |
| Bind mount | Makes an existing host folder visible inside a container; model/report mounts are read-only |

You start the **production Compose file**, not the two Dockerfiles separately. Compose uses those Dockerfiles to build the application images. The official PostgreSQL image initializes the database; Alembic creates the application tables afterward.

## Prepare an EC2 server

Use an Ubuntu 24.04 LTS **x86_64/amd64** instance for this first walkthrough. A starting point is at least two vCPUs and 4 GB RAM, with enough persistent EBS storage for images, models, logs and database growth. This is a starting configuration to measure, not a capacity guarantee. Train models on the laptop first; serving does not need the training dataset or its CPU/RAM budget.

In the AWS console:

1. Choose the region you intend to use, create/select a key pair, and launch the instance with an encrypted EBS volume.
2. Allow inbound SSH TCP 22 only from your own IP address. Alternatively configure Systems Manager access deliberately.
3. Allow TCP 80 and 443 for the HTTPS gateway. Keep 5432, 8000 and 8080 closed to the public.
4. Associate a stable address for DNS, then point a domain's A record at it. Account for address/storage charges in your cost estimate.

[AWS security-group reference](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html). Security groups control allowed network traffic; authentication still controls who may use the website.

From your laptop, substitute the actual key path and public DNS name:

```sh
chmod 400 /path/to/fraud-demo-key.pem
ssh -i /path/to/fraud-demo-key.pem ubuntu@YOUR_EC2_PUBLIC_DNS
```

The remaining installation commands run **on EC2**, not on your Mac. Install Docker Engine and the Compose plugin using [Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). For a fresh compatible Ubuntu installation, the repository-based sequence is:

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
sudo docker run --rm hello-world
```

These commands use `sudo`; adding yourself to the Docker group is not required for this walkthrough. If the server already has container packages, follow Docker's conflict/removal guidance before altering that installation.

## Copy source and serving artifacts

On EC2, create a fixed project directory:

```sh
mkdir -p ~/fraud-system
```

On the **laptop**, from the project root, copy the maintained source and complete serving artifacts. This works for your current uncommitted workspace; a Git clone would not include uncommitted code or ignored models.

```sh
rsync -av \
  --exclude='.git/' --exclude='.idea/' --exclude='.venv/' --exclude='.venv311/' \
  --exclude='.runtime/' --exclude='artifacts/' --exclude='node_modules/' \
  --exclude='dist/' --exclude='__pycache__/' --exclude='.pytest_cache/' \
  --exclude='test-results/' --exclude='playwright-report/' \
  --include='.env.example' --include='.env.production.example' \
  --exclude='.env*' --exclude='backend/data/' \
  -e 'ssh -i /path/to/fraud-demo-key.pem' \
  ./ ubuntu@YOUR_EC2_PUBLIC_DNS:~/fraud-system/
```

The model/report directories are deliberately **not excluded**. Both current pointers and every file referenced by them must arrive, including all candidate artifacts, `router.joblib`, `samples.json`, the BankSim `history.pkl`, and matching reports. Preserve complete version folders rather than copying one chosen `.joblib` in isolation.

Do not transfer the Mac virtual environment or native `.runtime/postgres` directory. Linux installs its own dependencies from requirements. To migrate database records, use logical PostgreSQL backups, not raw native database files from another platform/version.

## Configure and start the stack

Back on **EC2**:

```sh
cd ~/fraud-system
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

Use distinct generated values for `POSTGRES_PASSWORD`, `ANALYST_PASSWORD` and `API_ACCESS_TOKEN`. `openssl rand -hex 32` generates a URL-safe random value suitable for each field; run it separately for each secret. Do not retain example placeholders. Keep `WEB_PORT=8080` for the gateway example below. Keep `DATABASE_URL` unset for the bundled PostgreSQL service.

For convenience, define this shell function **inside the project directory**:

```sh
dc() {
  sudo docker compose --project-name fraud --env-file .env.production -f docker-compose.production.yml "$@"
}
```

`dc` is just a shorter spelling of that command. The fixed project name keeps volume names stable across shell sessions and directory changes. Redefine the function after a fresh SSH login.

Validate configuration without printing resolved secrets, then build and start:

```sh
dc config --quiet
dc up --build -d
dc ps -a
```

The explicit full startup command, if you do not use the function, is:

```sh
sudo docker compose --project-name fraud --env-file .env.production -f docker-compose.production.yml up --build -d
```

`up` submits services according to their dependency conditions. Use `dc ps -a` and readiness checks to confirm useful work is available rather than assuming that a returned command proves readiness.

### The same startup, one stage at a time

Use these stages when learning or troubleshooting a fresh installation. Run the next stage only after the previous command succeeds.

Build the application images and wait for PostgreSQL health:

```sh
dc build
dc up -d --wait --wait-timeout 120 postgres
```

Run migrations once against that ready database:

```sh
dc run --rm --no-deps migrate
```

Start API workers and wait for their readiness. `--no-deps` is appropriate here because the database and migration stages were already completed explicitly:

```sh
dc up -d --no-deps --wait --wait-timeout 180 backend
```

Then start the gateway:

```sh
dc up -d --no-deps web
dc ps -a
```

The normal `up --build -d` command handles the same dependencies automatically through `service_healthy` and `service_completed_successfully`. Migrations can safely be rerun: Alembic checks its revision table and applies only pending revisions. [Compose startup-order documentation](https://docs.docker.com/compose/how-tos/startup-order/).

## Database creation, migrations and linking

There are three different operations:

1. **PostgreSQL starts.** On an empty data volume, its image initializes storage, creates the configured role, and creates `POSTGRES_DB` using the `POSTGRES_*` environment variables.
2. **Alembic upgrades tables.** The `migrate` service runs `alembic upgrade head` using the backend image. It creates/updates sessions, prediction logs, batch retries and review events inside that database.
3. **The API connects.** SQLAlchemy uses `DATABASE_URL` and reuses connections while handling requests.

The generated bundled address looks like:

```text
postgresql+psycopg2://fraud_user:YOUR_PASSWORD@postgres:5432/fraud_db
```

`postgresql+psycopg2` selects the database/driver, `fraud_user` is the role, `postgres` is the **Compose service name**, `5432` is the internal PostgreSQL port, and `fraud_db` is the database.

Inside the backend container, `localhost` refers to the backend container itself. It does not mean the PostgreSQL container or your laptop. Compose DNS resolves `postgres` and `backend` between their services. Nginx forwards to `http://backend:8000` for the same reason.

Changing `POSTGRES_PASSWORD` in an environment file does not reset credentials in an already initialized volume. Existing databases keep their existing role/password until changed deliberately in PostgreSQL. Never remove the volume to “fix” a connection problem without a verified backup.

## Put HTTPS in front

The production gateway deliberately binds to **`127.0.0.1:8080` on EC2**. Opening port 8080 in an AWS security group does not make a loopback listener reachable from outside. An external ALB cannot directly reach that loopback listener either.

For the initial EC2 deployment, run Caddy **on the host** to accept HTTPS and forward locally. Install its official service package as described by [Caddy's Ubuntu instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian):

```sh
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy
```

Edit `/etc/caddy/Caddyfile` using your real domain:

```caddyfile
fraud.your-domain.example {
    reverse_proxy 127.0.0.1:8080
}
```

Then validate/reload:

```sh
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl enable caddy
```

With correct DNS and reachable ports 80/443, Caddy obtains and renews HTTPS certificates. [Automatic HTTPS/reverse-proxy explanation](https://caddyserver.com/docs/quick-starts/reverse-proxy).

Visit the HTTPS domain and enter `ANALYST_USER`/`ANALYST_PASSWORD`. Browser `/api/` calls pass through the gateway, which supplies the server-held API token. `/service/` is for token-authenticated server-to-server callers such as a private Sites proxy; it still requires the Python bearer token. The API token never belongs in the compiled browser bundle.

## Operate, back up and troubleshoot

Useful commands from `~/fraud-system` after defining `dc`:

```sh
dc ps -a
dc logs --tail 100 migrate backend web
curl --fail http://127.0.0.1:8080/health/live
curl --fail --user analyst http://127.0.0.1:8080/health/ready
```

The last command prompts for the analyst password; replace `analyst` if you changed the username. Test a genuine single prediction, Auto/manual identity, labelled CSV upload, persisted log and analyst review through the website. A static homepage or liveness response alone does not establish successful model serving.

### Backups

Create a logical PostgreSQL backup without printing the password:

```sh
mkdir -p ~/fraud-backups
backup_file="$HOME/fraud-backups/fraud-$(date -u +%Y%m%dT%H%M%SZ).dump"
dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file"
test -s "$backup_file"
```

`backup_file` is a task-specific variable; `$HOME` is only read. Protect backups and copy them to storage outside the instance. Test restoration into a separate database before trusting a backup. Keep matching model/report versions alongside your database recovery plan. Docker volumes survive container replacement, but an instance/EBS deletion can still destroy the underlying disk.

### Updating

Transfer the reviewed new source and **complete** new model/report run. Keep old versions for rollback. Back up the database, then run:

```sh
dc build
dc run --rm migrate
dc up -d --force-recreate backend web
dc ps -a
```

Restart workers after switching current model pointers because loaded models are cached. Do not overwrite one live `.joblib` while other files still belong to an earlier version.

`dc stop` stops the containers while preserving storage. Do not use `down -v` as routine shutdown: `-v` removes named volumes and therefore database records. Stopping EC2 does not necessarily stop all AWS charges, such as retained storage, addresses or separately provisioned managed services.

### Common failures

| Symptom | What to inspect |
|---|---|
| Database connection refused | `dc ps`, PostgreSQL health and service hostname; inside containers use `postgres`, not `localhost` |
| Password authentication failure | Existing role password versus configured URL; environment changes do not reinitialize a nonempty volume |
| Migration exits unsuccessfully | `dc logs migrate`; verify target database and migration-role schema permissions |
| Backend not ready | Missing/incompatible models, absent matching reports, incorrect token or database/schema failure |
| Models available but Auto unavailable | Validation policy did not qualify, or required router/candidate files were not copied; read the reason |
| Browser gets 401 | Analyst login for browser gateway; bearer token for `/service/` callers; distinguish the two |
| Gateway gets 502 | Backend health and Nginx upstream; verify both services share the Compose network |
| Domain/HTTPS unavailable | DNS, public address, security group 80/443, Caddy logs and port conflicts |
| Only homepage works | Check real API scoring and persistence; static content can load while the backend is broken |
| Container killed for memory | Inspect resource use; reduce workers or increase capacity after measurement |

## Move to ECS/Fargate and RDS

This is a migration checklist and architecture explanation, not a ready-created ECS stack. The first EC2 deployment works with the existing Compose configuration. ECS requires the additional AWS resources and adaptations below.

| Piece | Managed path |
|---|---|
| Container images | Build reviewed backend/frontend images, push immutable tags/digests to private ECR |
| Running containers | Define Fargate task/service CPU, memory, health checks and desired count |
| Database | Provision private RDS PostgreSQL, database and roles before running Alembic |
| Entry point | Public Application Load Balancer with an ACM certificate and HTTPS listener |
| Secrets | Secrets Manager/SSM values injected into containers, with IAM permissions |
| Models/reports | A complete immutable version delivered through EFS or a deliberately built model-bundle image |
| Logs/monitoring | CloudWatch logs, alarms, latency/error and resource measurements |
| Recovery | RDS backups/restoration, artifact retention and a tested deployment rollback procedure |

An understandable layout uses **one Fargate task with web and backend containers**, private database networking, and an ALB forwarding to the web container's port 8080. Containers in that `awsvpc` task share the task network: adapt the web image's Nginx upstream from Compose's `backend:8000` to `127.0.0.1:8000`. The existing literal Compose hostname is not automatically created by ECS. An alternative with separate services needs explicit service discovery; do not assume Compose DNS exists there.

Use ALB health checks on the gateway's unauthenticated `/health/live` and container readiness checks for actual dependency availability. Preserve the private analyst gateway and server-held API token. The Compose host port binding is not an ECS load-balancer binding; configure task ports and security groups explicitly.

The backend and migration task receive an address such as:

```text
postgresql+psycopg2://fraud_user:PERCENT_ENCODED_PASSWORD@YOUR_RDS_ENDPOINT:5432/fraud_db?sslmode=require
```

Allow RDS TCP 5432 **from the application/migration task security group**, not the internet. Use URL-encoded credentials and TLS. Plan outbound access for ECR, logs and secrets using suitable endpoints or NAT. Provision the database separately; no migration role needs `CREATE DATABASE`.

For EFS, create an access point with ownership/permissions readable by backend UID 10001, configure mount-target networking, and mount completed artifact directories read-only at `/app/models/v2` and `/app/reports/v2`. A Mac bind mount like `./backend/models/v2` cannot be used directly by Fargate. [AWS EFS/ECS documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/efs-volumes.html).

Before starting/updating the API service, run a **one-off migration task** using the same backend image with command `alembic upgrade head`, correct database secret and networking. Wait for successful completion. Then deploy the API/web service with matching artifacts and verify readiness plus real scoring. Each API replica must not race to run schema migrations during its own startup.

RDS replaces the Compose `postgres` service and its named volume. Its backups are separate from model artifact retention. Scaling stateless API workers increases database connections and model memory; measure these before raising task count. The single-analyst/private research application still needs a separate ownership/authorization design before becoming a public multi-user banking service.
