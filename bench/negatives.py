"""Hand-written hard negatives: text that looks sensitive but is not. No spans are labeled.

Every value here is either a publicly documented example, a placeholder, a reference to a
value stored elsewhere, a hash or identifier, or a public key. None is a real credential.
"""

NEGATIVES = [
    ("uuid-log", """2026-10-21T09:14:03.112Z INFO  order.created id=3f2b8c4e-9a1d-4e5f-8b7c-2d1e0f9a8b7c customer_id=a6c1e2d3-4b5a-4c6d-9e8f-7a6b5c4d3e2f items=3
2026-10-21T09:14:03.540Z INFO  payment.authorized order=3f2b8c4e-9a1d-4e5f-8b7c-2d1e0f9a8b7c amount_cents=4599 currency=usd
2026-10-21T09:14:04.007Z WARN  inventory.low sku=WID-0042 remaining=3 warehouse=us-east-2b"""),
    ("git-log", """commit 9fceb02d0ae598e95dc970b74767f19372d61af8
Merge: 1a2b3c4 5d6e7f8
Date:   Tue Oct 21 10:02:11 2026 +0000

    Merge pull request #1287 from acme/dependabot/npm_and_yarn/lodash-4.17.21

commit e83c5163316f89bfbde7d9ab23ca2e25604af290
Date:   Mon Oct 20 18:44:52 2026 +0000

    fix(parser): handle trailing commas in arrays"""),
    ("package-lock", """    "node_modules/lodash": {
      "version": "4.17.21",
      "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz",
      "integrity": "sha512-v2kDEe57lecTulaDIuNTPy3Ry4gLGJ6Z1O3vE1krgXZNrsQ+LFTGHVxVjcXPs17LhbZVGedAJv8XZ1tvj5FvSg==",
      "dev": true
    },"""),
    ("yarn-lock", """"@babel/code-frame@^7.22.13":
  version "7.22.13"
  resolved "https://registry.yarnpkg.com/@babel/code-frame/-/code-frame-7.22.13.tgz#e3c1c099402598483b7a8c46a721d1038803755e"
  integrity sha512-XktuhWlJ5g+3TJXc5upd9Ks1HutSArik6jf2eAjYFyIOf4ej3RN+184cZbzDvbPnuTJIUhPKKJE3cIsYTiAT3w=="""),
    ("go-sum", """golang.org/x/net v0.31.0 h1:68CPQngjLL0r2AlUKiSxtQFKvzRVbnzLwMUn5SzcLHo=
golang.org/x/net v0.31.0/go.mod h1:P4fl1q7dY2hnZFxEk4pPSkDHF+QqjitcnDjUQyMM+pM=
golang.org/x/sys v0.27.0 h1:wBqf8DvsY9Y/2P8gAfPDEYNuS30J4lPHJxXSb/nJZ+s="""),
    ("cargo-lock", """[[package]]
name = "serde"
version = "1.0.214"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f55c3193aca71c12ad7890f1785d2b73e1b9f63a0bbc353c08ef26fe03fc56b5"
dependencies = [
 "serde_derive",
]"""),
    ("docker-digest", """services:
  web:
    image: nginx@sha256:2d194184b067db3598771b4cf326cfe6ad5051937ba1132b8b7d4b0184e0d0a6
    ports:
      - "8080:80"
  cache:
    image: redis:7.4-alpine"""),
    ("aws-docs-example", """# Example from the AWS CLI docs
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
region = us-west-2"""),
    ("env-references", """DATABASE_URL=${DATABASE_URL}
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
REDIS_PASSWORD=$REDIS_PASSWORD
SENTRY_DSN=${SENTRY_DSN:-}"""),
    ("python-env-lookup", """import os

api_key = os.environ["OPENAI_API_KEY"]
token = os.getenv("GITHUB_TOKEN")
db_password = settings.DATABASE_PASSWORD
client = Client(api_key=api_key, timeout=30)"""),
    ("placeholders", """# Copy this file to .env and fill in your own values
ANTHROPIC_API_KEY=your-api-key-here
OPENAI_API_KEY=<your-openai-key>
STRIPE_SECRET_KEY=sk_live_your-stripe-secret-key
SLACK_BOT_TOKEN=xoxb-your-token
DB_PASSWORD=changeme"""),
    ("curl-docs", """curl https://api.example.com/v1/items \\
  -H "Authorization: Bearer $API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "widget", "quantity": 2}'"""),
    ("k8s-service", """apiVersion: v1
kind: Service
metadata:
  name: checkout
spec:
  type: NodePort
  ports:
    - port: 443
      targetPort: 8443
      nodePort: 30080
      protocol: TCP"""),
    ("k8s-secret-ref", """env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: password
  - name: API_TOKEN
    valueFrom:
      secretKeyRef:
        name: checkout-secrets
        key: api-token"""),
    ("example-emails", """def test_send_welcome_email(mailer):
    mailer.send(to="user@example.com", template="welcome")
    assert mailer.outbox[0].to == ["user@example.com"]
    assert mailer.outbox[0].from_ == "noreply@example.org\""""),
    ("placeholder-person", """# Fixture used by the docs screenshots
DEMO_USER = {
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "555-0100",
}"""),
    ("public-key-pem", """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u
+qKhbwKfBstIs+bMY2Zkp18gnTxKLxoS2tFczGkPLPgizskuemMghRniWaoLcyeh
kd3qqGElvW/VDL5AaWTg0nLVkjRo9z+40RQzuVaE8AkAFmxZzow3x+VJYKdjykkJ
0iT9wCS0DRTXu269V264Vf/3jvredZiKRkgwlL9xNAwxXFg0x/XFw005UWVRIkdg
cKWTjpBP2dPwVZ4WWC+9aGVd+Gyn1o0CLelf4rEjGoXbAAEgAqeGUxrcIlbjXfbc
mwIDAQAB
-----END PUBLIC KEY-----"""),
    ("certificate-pem", """ca.crt: |
  -----BEGIN CERTIFICATE-----
  MIIDdzCCAl+gAwIBAgIEAgAAuTANBgkqhkiG9w0BAQUFADBaMQswCQYDVQQGEwJJ
  RTESMBAGA1UEChMJQmFsdGltb3JlMRMwEQYDVQQLEwpDeWJlclRydXN0MSIwIAYD
  VQQDExlCYWx0aW1vcmUgQ3liZXJUcnVzdCBSb290MB4XDTAwMDUxMjE4NDYwMFoX
  -----END CERTIFICATE-----"""),
    ("ssh-public-key", """# ~/.ssh/authorized_keys on the build box
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl deploy@ci-runner-07
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC7vbqajDhA9OlOd1Gc4X8qWLuEGn2kV2ZGcBJ3lE4Dm5Lj0Q8o1rT2s3u4v5w6x7y8z9A0B1C2D3E4F5G6H7I8J9K0 build@ci-runner-07"""),
    ("data-uri", """<img alt="spacer" width="1" height="1"
     src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" />"""),
    ("sha256sum", """e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  empty.txt
9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08  test.txt
2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae  foo.bin"""),
    ("git-lfs-pointer", """version https://git-lfs.github.com/spec/v1
oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
size 12345"""),
    ("tailwind-classes", """<button class="inline-flex items-center rounded-md bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:from-indigo-600 focus-visible:outline-2">
  Save changes
</button>"""),
    ("long-identifiers", """public class AbstractSingletonProxyFactoryBeanConfigurationRegistry2 {
    private final UserAccountSettingsByOrganizationIdRepository userAccountSettingsByOrganizationIdRepository;
    public static final String DEFAULT_CONNECTION_POOL_IDLE_TIMEOUT_MILLISECONDS = "30000";
}"""),
    ("password-helpers", """PASSWORD_MIN_LENGTH = 12
MAX_TOKENS = 4096

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def count_tokens(text: str) -> int:
    token_count = len(tokenizer.encode(text))
    return token_count"""),
    ("ts-interface", """export interface Credentials {
  username: string;
  password: string;
  apiKey?: string;
  token: string | null;
}"""),
    ("stripe-publishable", """// Publishable keys are safe to ship in the browser.
const stripe = Stripe('pk_test_TYooMQauvdEDq54NiTphI7jx');"""),
    ("placeholder-anthropic", """export ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
claude --version"""),
    ("redacted-output", """{
  "api_key": "********",
  "token": "[REDACTED]",
  "password": "<hidden>",
  "client_secret": "***"
}"""),
    ("md5-test", """def test_md5():
    assert md5(b"hello").hexdigest() == "5d41402abc4b2a76b9719d911017c592"
    assert sha1(b"hello").hexdigest() == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d\""""),
    ("access-log", """10.0.12.34 - - [21/Oct/2026:10:00:01 +0000] "GET /healthz HTTP/1.1" 200 2 "-" "kube-probe/1.31"
10.0.12.35 - - [21/Oct/2026:10:00:02 +0000] "GET /api/v1/orders?page=2&per_page=50 HTTP/1.1" 200 18234 "-" "Mozilla/5.0"
172.16.4.9 - - [21/Oct/2026:10:00:02 +0000] "POST /api/v1/carts/8f14e45f/items HTTP/1.1" 201 512 "-" "okhttp/4.12.0\""""),
    ("aws-arn", """{
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::123456789012:role/deploy-role"},
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::my-app-artifacts/*"
}"""),
    ("jwt-io-example", """# The example token from jwt.io, decoded in the README
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c\""""),
    ("docker-login", """- name: Log in to GHCR
  run: echo "$CR_PAT" | docker login ghcr.io -u USERNAME --password-stdin
- name: Publish
  run: npm publish
  env:
    NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}"""),
    ("terraform-variable", """variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}"""),
    ("tracing-ids", """span finished name=GET /checkout trace_id=4bf92f3577b34da6a3ce929d0e0e4736 span_id=00f067aa0ba902b7 parent_id=b7ad6b7169203331 duration=41.2ms
span finished name=SELECT orders trace_id=4bf92f3577b34da6a3ce929d0e0e4736 span_id=53995c3f42cd8ad8 duration=6.9ms"""),
    ("db-url-placeholder", """# docker-compose.override.yml for local dev
DATABASE_URL: postgres://user:password@localhost:5432/mydb
REDIS_URL: redis://localhost:6379/0"""),
    ("openapi-security", """components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key"""),
    ("semver-build", """version: 1.27.3+build.20261021.a1b2c3d
image_tag: checkout-1.27.3-a1b2c3d
helm_chart: checkout-0.14.2.tgz
node: v22.11.0"""),
    ("base64-fixture", """def test_decode_payload():
    # base64 of a small JSON document used across the parser tests
    raw = "eyJvcmRlcl9pZCI6IDQyLCAic3RhdHVzIjogInNoaXBwZWQiLCAiaXRlbXMiOiBbMSwgMiwgM119"
    assert decode(raw)["status"] == "shipped\""""),
]

# Written after the first benchmark run and never used to tune rules: a held-out check on the
# false-positive rate. `gen.py --holdout` writes these instead of NEGATIVES.
HOLDOUT_NEGATIVES = [
    ("gradle-wrapper", """distributionBase=GRADLE_USER_HOME
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.10.2-bin.zip
distributionSha256Sum=31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26
zipStorePath=wrapper/dists"""),
    ("pip-hashes", """requests==2.32.3 \\
    --hash=sha256:70761cfe03c773ceb22aa2f671b4757976145175cdfca038c02654d061d6dcc6 \\
    --hash=sha256:55365417734eb18255590a9ff9eb97e9e1da868d4ccd6402399eaf68af20a760
urllib3==2.2.3 --hash=sha256:ca899ca043dcb1bafa3e262d73aa25c465bfb49e0bd9dd5d59f1d0acba2f8fac"""),
    ("graphql-persisted", """{"operationName":"ProductPage","variables":{"slug":"blue-mug"},
 "extensions":{"persistedQuery":{"version":1,"sha256Hash":"ecf4edb46db40b5132295c0291d62fb65d6759a9eedfa4d5d612dd5ec54a6b38"}}}"""),
    ("go-test-fixture", """func TestClient(t *testing.T) {
	const testToken = "test-token"
	fakeAPIKey := "fake-api-key-for-tests"
	c := NewClient(WithToken(testToken), WithAPIKey(fakeAPIKey))
	require.NotNil(t, c)
}"""),
    ("bearer-placeholders", """### Get the current user
GET https://api.example.com/v2/me
Authorization: Bearer <token>

### Same call with curl
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" https://api.example.com/v2/me"""),
    ("css-data-uri", """.icon-check {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+PHBhdGggZD0iTTIgOGw0IDQgOC04Ii8+PC9zdmc+");
}"""),
    ("rails-credentials", """Aws.config.update(
  access_key_id: Rails.application.credentials.dig(:aws, :access_key_id),
  secret_access_key: Rails.application.credentials.dig(:aws, :secret_access_key),
  region: "eu-central-1"
)"""),
    ("public-cdn", """<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>"""),
    ("eth-address", """// Public contract address from the deployment log
export const TOKEN_CONTRACT = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e";
export const CHAIN_ID = 11155111;"""),
    ("discord-ids", """{
  "guild_id": "1029384756102938475",
  "channel_id": "1188776655443322110",
  "message_id": "1299887766554433221"
}"""),
    ("env-sample-comments", """# Required
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# Optional
# LOG_LEVEL=info"""),
    ("webpack-assets", """assets by path static/js/ 412 KiB
  asset static/js/main.3f9a2c1b.js 288 KiB [emitted] [immutable] [minimized] (name: main)
  asset static/js/vendors.8e1f40d2.chunk.js 124 KiB [emitted] [immutable] [minimized]
webpack 5.95.0 compiled successfully in 8123 ms"""),
    ("oidc-discovery", """{
  "issuer": "https://login.example.com",
  "token_endpoint": "https://login.example.com/oauth2/token",
  "jwks_uri": "https://login.example.com/.well-known/jwks.json",
  "id_token_signing_alg_values_supported": ["RS256"]
}"""),
    ("helm-values", """image:
  repository: ghcr.io/acme/checkout
  tag: "1.27.3"
  pullPolicy: IfNotPresent
existingSecret: checkout-credentials
passwordKey: db-password"""),
    ("youtube-embeds", """<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=42" title="Demo"></iframe>
<a href="https://youtu.be/M7lc1UVf-VE">Player API demo</a>"""),
]

# A second held-out set, written after the PII and identifier refinements, for the final check.
# `gen.py --negatives holdout2` writes these.
HOLDOUT2_NEGATIVES = [
    ("docker-ps", """CONTAINER ID   IMAGE                  COMMAND                  STATUS          PORTS                    NAMES
3f9c1a7b2e44   postgres:16-alpine     "docker-entrypoint.s…"   Up 2 hours      0.0.0.0:5432->5432/tcp   db-1
a81d0c55f9e3   redis:7                "redis-server"           Up 2 hours      6379/tcp                 cache-1"""),
    ("python-repr", """<sqlalchemy.engine.base.Connection object at 0x7f8b2c3d4e50>
<function handler at 0x10a3f2b80>
RuntimeWarning: coroutine 'fetch' was never awaited (task 0x7f8b2c1a9d30)"""),
    ("azure-resource-id", """{
  "id": "/subscriptions/8f3e2a1b-4c5d-4e6f-9a8b-7c6d5e4f3a2b/resourceGroups/rg-prod/providers/Microsoft.Web/sites/checkout-api",
  "location": "westeurope",
  "tenantId": "72f988bf-86f1-41af-91ab-2d7cd011db47"
}"""),
    ("stripe-object-ids", """{
  "id": "ch_3PqR8sT2uVwXyZ1a0bCdEfGh",
  "object": "charge",
  "customer": "cus_QxR4tY7uI9oP2a",
  "payment_intent": "pi_3PqR8sT2uVwXyZ1a0kLmNoPq",
  "livemode": false
}"""),
    ("npmrc-reference", """registry=https://registry.npmjs.org/
//registry.npmjs.org/:_authToken=${NPM_TOKEN}
always-auth=true"""),
    ("postman-variables", """{
  "key": "Authorization",
  "value": "Bearer {{access_token}}",
  "type": "text"
},
{ "key": "baseUrl", "value": "{{base_url}}/v1" }"""),
    ("csp-header", """Content-Security-Policy: default-src 'self'; script-src 'self' 'sha256-B2yPHKaXnvFWtRChIbabYmUBFZdVfKKXHbWtWidDVF8='; style-src 'self' 'unsafe-inline'"""),
    ("git-rebase-todo", """pick 3e2f1a9 feat: add retry budget to webhook sender
fixup 8c0d4b7 fixup! feat: add retry budget
reword 5a6b7c8 chore: bump golangci-lint to 1.61
# Rebase 1f2e3d4..5a6b7c8 onto 1f2e3d4 (3 commands)"""),
    ("k8s-events", """LAST SEEN   TYPE      REASON      OBJECT                                   MESSAGE
2m          Normal    Scheduled   pod/checkout-7d9f8b6c5d-x2k4p           Successfully assigned prod/checkout-7d9f8b6c5d-x2k4p to ip-10-0-3-17
1m          Warning   BackOff     pod/worker-5c8d7e6f4b-q9w8e             Back-off restarting failed container"""),
    ("pytest-cache", """{
  "tests/test_api.py::test_create_order[payload0]": true,
  "tests/test_api.py::test_refund": true
}
cache key: v1-deps-3b7f2a91c0d4e5f6a7b8c9d0e1f2a3b4"""),
    ("cloudflare-headers", """HTTP/2 403
cf-ray: 8d2f4a1b9c3e7f60-FRA
cf-cache-status: DYNAMIC
x-request-id: 01JB7Z4K9Q2W3E5R6T7Y8U9I0P"""),
    ("slack-ids", """channel: C04B7KQ2X9M
thread_ts: "1729845123.004500"
bot_id: B05N8P3R6T1
team: T01A2B3C4D5"""),
    ("ga-config", """gtag('config', 'G-7XK2M9Q4LP');
window.SENTRY_RELEASE = "checkout@1.27.3+a1b2c3d";
const MAPBOX_STYLE = "mapbox://styles/mapbox/streets-v12";"""),
    ("public-oauth-client", """# Public OAuth client for the CLI (PKCE, no secret)
OAUTH_CLIENT_ID=9d1c250a-e61b-44d9-88ed-5944d1962f5e
OAUTH_REDIRECT_URI=http://127.0.0.1:8976/callback"""),
    ("checksum-manifest", """SHA256 (checkout-1.27.3-darwin-arm64.tar.gz) = 6c8f9a2d4e1b3c5a7f9e0d2c4b6a8f1e3d5c7b9a0f2e4d6c8b0a2f4e6d8c0b2a
SHA256 (checkout-1.27.3-linux-amd64.tar.gz) = 1a3c5e7f9b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2a"""),
]


# Held-out set 3, written Oct 26, 2026 after IBANs became a rule and before any run on it:
# identifier shapes none of the other sets has. `gen.py --negatives holdout3` writes these.
HOLDOUT3_NEGATIVES = [
    ("gha-pinned-actions", """steps:
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  - uses: actions/setup-node@b39b52d1213e96004bfcb1c61a8a6fa8ab84f3e8 # v5.1.0
  - run: npm ci && npm test"""),
    ("aws-arn-request-id", """An error occurred (AccessDenied) when calling the AssumeRole operation:
User: arn:aws:sts::418295730164:assumed-role/ci-runner/i-0c7f3e9a2b1d4f6e8 is not authorized
RequestId: 7b2e4f1a-9c3d-4e8b-a6f5-2d1c0b9e8f7a"""),
    ("terraform-plan-ids", """  # aws_security_group_rule.ingress will be updated in-place
  ~ resource "aws_security_group_rule" "ingress" {
        id                = "sgrule-2846193057"
        security_group_id = "sg-0a7c3e5f9b1d2e4c6"
      ~ cidr_blocks       = ["10.0.0.0/16"] -> ["10.0.0.0/8"]
        vpc_id            = "vpc-05f2b8d1c4e7a9036"
    }"""),
    ("cargo-lock-checksums", """[[package]]
name = "serde_json"
version = "1.0.140"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "20068b6e96dc6c9bd23e01df8827e6c7e1f2fddd43c21810382803c136b99373"
dependencies = ["itoa", "memchr", "ryu", "serde"]"""),
    ("vite-build-assets", """dist/index.html                   0.46 kB │ gzip:  0.30 kB
dist/assets/index-BqX7vN2k.css    8.12 kB │ gzip:  2.41 kB
dist/assets/vendor-Dk3pL9wQ.js  142.87 kB │ gzip: 45.93 kB
dist/assets/index-C8mT4rYz.js    23.05 kB │ gzip:  7.88 kB"""),
    ("helm-secret-refs", """postgresql:
  auth:
    existingSecret: checkout-db-credentials
    secretKeys:
      adminPasswordKey: postgres-password
      userPasswordKey: password
env:
  - name: STRIPE_KEY
    valueFrom:
      secretKeyRef: { name: payments, key: stripe-secret-key }"""),
    ("w3c-traceparent", """traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
tracestate: congo=t61rcWkgMzE,rojo=00f067aa0ba902b7
2026-10-26T08:12:44Z checkout span_id=b7ad6b7169203331 parent=00f067aa0ba902b7 dur=41ms"""),
    ("docker-digests", """REPOSITORY        TAG       DIGEST                                                                    IMAGE ID       SIZE
node              22-slim   sha256:3f1c8e9a7b2d4f6e0a5c9b8d7e6f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f   a91c2d3e4f5b   219MB
python            3.12      sha256:9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d   0b7f3c2a9e1d   1.02GB"""),
    ("pip-hashes", """certifi==2026.8.14 \\
    --hash=sha256:5a1e7c9d2b4f6a8c0e3d5f7b9a1c3e5d7f9b2a4c6e8d0f1b3a5c7e9d2f4b6a8c \\
    --hash=sha256:c2e4a6b8d0f1c3e5a7b9d2f4c6e8a0b1d3f5c7e9a2b4d6f8c0e1a3b5d7f9c2e4
idna==3.11 \\
    --hash=sha256:7d9b1f3a5c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d"""),
    ("ssh-fingerprint", """The authenticity of host 'github.com (140.82.121.4)' can't be established.
ED25519 key fingerprint is SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU.
This key is not known by any other names."""),
    ("eth-tx-hash", """Transaction submitted: 0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060
Block 21483907 · gas used 51,234 · status: success"""),
    ("mongo-objectids", """db.orders.find({ _id: ObjectId("6716f2c3a9e4b1d8c7f05e21") })
{ _id: ObjectId("6716f2c3a9e4b1d8c7f05e21"), customer: ObjectId("66f0a1b2c3d4e5f6a7b8c9d0"), total: 4599 }"""),
    ("xcode-deriveddata", """Build input file cannot be found:
'/Users/dev/Library/Developer/Xcode/DerivedData/Checkout-bxkqzjwmpvnfytcxbfdqhtrkgnli/Build/Products/Debug-iphonesimulator/Checkout.app/Info.plist'"""),
    ("nginx-access-log", """2001:db8:3c4d:15::1a2f - - [26/Oct/2026:08:14:03 +0000] "GET /api/v1/orders/ord_8Kq2Xz7Lm4Np?expand=items HTTP/2.0" 200 1843 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_6) AppleWebKit/605.1.15" rid=9f2c6a1e8b3d47f0a5c2e9d1b7f4a6c3"""),
    ("openapi-password-field", """components:
  schemas:
    Login:
      type: object
      properties:
        username: { type: string, example: jdoe }
        password: { type: string, format: password, example: "********", minLength: 12 }"""),
]
