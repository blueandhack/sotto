"""Generate the Phase 0 labeled dataset into bench/data/*.jsonl.

Every secret is random text in a provider's format, produced here from a fixed seed. None is a
real credential. Personal data comes from Faker. Hard negatives are hand-written in negatives.py.

    uv run python bench/gen.py [--seed 7] [--out bench/data]
    uv run python bench/gen.py --seed 8 --negatives holdout --out /tmp/holdout     # held-out check
    uv run python bench/gen.py --seed 9 --negatives holdout2 --out /tmp/holdout2   # second check
    uv run python bench/gen.py --seed 10 --negatives holdout3 --out /tmp/holdout3  # after pf-serve and IBANs
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import string
import sys
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).parent))
from negatives import HOLDOUT2_NEGATIVES, HOLDOUT3_NEGATIVES, HOLDOUT_NEGATIVES, NEGATIVES  # noqa: E402

UPPER, LOWER, DIGITS = string.ascii_uppercase, string.ascii_lowercase, string.digits
ALNUM = UPPER + LOWER + DIGITS
B64 = ALNUM + "+/"
B64URL = ALNUM + "-_"
HEX = "0123456789abcdef"
B32 = UPPER + "234567"
PW_SPECIAL = "!@#%^*-_+."


class Doc:
    """Builds a text and its labeled spans from pieces: plain strings or (value, TYPE)."""

    def __init__(self):
        self.parts: list[str] = []
        self.spans: list[dict] = []
        self.n = 0

    def add(self, *pieces) -> Doc:
        for p in pieces:
            if isinstance(p, tuple):
                value, kind = p
                self.spans.append({"start": self.n, "end": self.n + len(value), "type": kind})
                p = value
            self.parts.append(p)
            self.n += len(p)
        return self

    @property
    def text(self) -> str:
        return "".join(self.parts)


def record(rid: str, doc: Doc, tags: list[str]) -> dict:
    text = doc.text
    for s in doc.spans:
        assert 0 <= s["start"] < s["end"] <= len(text)
    return {"id": rid, "text": text, "spans": doc.spans, "tags": tags}


class Secrets:
    def __init__(self, rng: random.Random):
        self.r = rng

    def s(self, chars: str, n: int) -> str:
        return "".join(self.r.choice(chars) for _ in range(n))

    def aws_key(self):
        return "AKIA" + self.s(B32, 16)

    def aws_secret(self):
        return self.s(B64, 40)

    def github(self):
        return self.r.choice(["ghp_", "gho_", "ghs_"]) + self.s(ALNUM, 36)

    def github_fine(self):
        return "github_pat_" + self.s(ALNUM, 22) + "_" + self.s(ALNUM, 59)

    def anthropic(self):
        return "sk-ant-api03-" + self.s(B64URL, 93) + "AA"

    def openai(self):
        return "sk-proj-" + self.s(B64URL, 58) + "T3BlbkFJ" + self.s(B64URL, 58)

    def stripe(self):
        return self.r.choice(["sk_live_", "rk_live_", "sk_test_"]) + self.s(ALNUM, self.r.choice([24, 99]))

    def slack(self):
        return f"xoxb-{self.s(DIGITS, 12)}-{self.s(DIGITS, 13)}-{self.s(ALNUM, 24)}"

    def slack_webhook(self):
        return f"https://hooks.slack.com/services/T{self.s(UPPER + DIGITS, 8)}/B{self.s(UPPER + DIGITS, 10)}/{self.s(ALNUM, 24)}"

    def google(self):
        return "AIza" + self.s(B64URL, 35)

    def huggingface(self):
        return "hf_" + self.s(UPPER + LOWER, 34)

    def npm(self):
        return "npm_" + self.s(ALNUM, 36)

    def sendgrid(self):
        return f"SG.{self.s(B64URL, 22)}.{self.s(B64URL, 43)}"

    def gitlab(self):
        return "glpat-" + self.s(B64URL, 20)

    def jwt(self):
        def b64(obj):
            return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).rstrip(b"=").decode()

        header = b64({"alg": "HS256", "typ": "JWT"})
        payload = b64({"sub": self.s(DIGITS, 10), "role": "service", "iat": 1761000000 + self.r.randint(0, 10**6)})
        sig = base64.urlsafe_b64encode(self.r.randbytes(32)).rstrip(b"=").decode()
        return f"{header}.{payload}.{sig}"

    def pem(self, kind: str):
        body = base64.b64encode(self.r.randbytes(48 * self.r.randint(12, 26))).decode()
        lines = [body[i : i + 64] for i in range(0, len(body), 64)]
        return f"-----BEGIN {kind}-----\n" + "\n".join(lines) + f"\n-----END {kind}-----"

    def password(self):
        n = self.r.randint(12, 20)
        chars = [self.r.choice(UPPER), self.r.choice(LOWER), self.r.choice(DIGITS), self.r.choice(PW_SPECIAL)]
        chars += [self.r.choice(ALNUM + PW_SPECIAL) for _ in range(n - 4)]
        self.r.shuffle(chars)
        return "".join(chars)

    def hex_key(self, n=32):
        return self.s(HEX, n)

    def opaque(self, n=40):
        return self.s(B64URL, n)


# Provider tokens: (tag, generator name, variable names to assign them to).
PROVIDERS = [
    ("aws", "aws_key", ["AWS_ACCESS_KEY_ID", "aws_access_key_id"]),
    ("aws-secret", "aws_secret", ["AWS_SECRET_ACCESS_KEY", "aws_secret_access_key"]),
    ("github", "github", ["GITHUB_TOKEN", "GH_TOKEN"]),
    ("github-fine", "github_fine", ["GITHUB_PAT"]),
    ("anthropic", "anthropic", ["ANTHROPIC_API_KEY", "anthropic_api_key"]),
    ("openai", "openai", ["OPENAI_API_KEY", "openai.api_key"]),
    ("stripe", "stripe", ["STRIPE_SECRET_KEY", "stripe_key"]),
    ("slack", "slack", ["SLACK_BOT_TOKEN"]),
    ("slack-webhook", "slack_webhook", ["SLACK_WEBHOOK_URL"]),
    ("google", "google", ["GOOGLE_API_KEY", "maps_key"]),
    ("huggingface", "huggingface", ["HF_TOKEN"]),
    ("npm", "npm", ["NPM_TOKEN"]),
    ("sendgrid", "sendgrid", ["SENDGRID_API_KEY"]),
    ("gitlab", "gitlab", ["GITLAB_TOKEN"]),
    ("jwt", "jwt", ["SERVICE_JWT", "auth_token"]),
]


def secret_in_context(r: random.Random, var: str, value: str, ctx: str) -> Doc:
    v = (value, "SECRET")
    lower = var.lower().replace(".", "_")
    d = Doc()
    if ctx == "shell":
        d.add(f"# added by setup.sh\nexport {var.upper().replace('.', '_')}=", v, "\nexport NODE_ENV=production\n")
    elif ctx == "python":
        d.add("import requests\n\n", f"{lower} = \"", v, "\"\n", "resp = requests.get(BASE_URL + '/v1/status', timeout=10)\n")
    elif ctx == "js":
        d.add("// config/production.js\nmodule.exports = {\n  region: 'us-east-1',\n  ", f"{lower}: '", v, "',\n  retries: 3,\n};\n")
    elif ctx == "yaml":
        d.add("integrations:\n  enabled: true\n  ", f"{lower}: ", v, "\n  timeout_seconds: 15\n")
    elif ctx == "json":
        d.add("{\n  \"service\": \"billing\",\n  ", f"\"{lower}\": \"", v, "\",\n  \"debug\": false\n}\n")
    elif ctx == "curl":
        d.add("$ curl -s https://api.internal.dev/v2/jobs \\\n    -H \"Authorization: Bearer ", v, "\" \\\n    -H 'Accept: application/json'\n")
    elif ctx == "log":
        d.add("2026-10-22T14:03:11.204Z DEBUG http.client sending headers={'User-Agent': 'svc/2.3', 'X-Api-Key': '", v, "'}\n")
    elif ctx == "terraform":
        d.add('provider "acme" {\n  region = "us-west-2"\n  ', f"{lower} = \"", v, "\"\n}\n")
    elif ctx == "compose":
        d.add("services:\n  worker:\n    image: acme/worker:1.4\n    environment:\n      - ", f"{var.upper().replace('.', '_')}=", v, "\n")
    elif ctx == "diff":
        d.add("diff --git a/.env.production b/.env.production\n@@ -3,2 +3,3 @@\n LOG_LEVEL=info\n+", f"{var.upper().replace('.', '_')}=", v, "\n")
    elif ctx == "call":
        d.add("from acme import Client\n\nclient = Client(\n    ", "api_key=\"", v, "\",\n    max_retries=2,\n)\n")
    elif ctx == "k8s-b64":
        encoded = base64.b64encode(value.encode()).decode()
        d.add("apiVersion: v1\nkind: Secret\nmetadata:\n  name: app-secrets\ntype: Opaque\ndata:\n  ", f"{lower}: ", (encoded, "SECRET"), "\n")
    else:
        raise ValueError(ctx)
    return d


CONTEXTS = ["shell", "python", "js", "yaml", "json", "curl", "log", "terraform", "compose", "diff", "call", "k8s-b64"]


def gen_secrets(r: random.Random, sec: Secrets) -> list[dict]:
    out = []
    # 26 provider tokens across the contexts.
    for i in range(26):
        tag, fn, names = PROVIDERS[i % len(PROVIDERS)]
        ctx = CONTEXTS[i % len(CONTEXTS)]
        doc = secret_in_context(r, r.choice(names), getattr(sec, fn)(), ctx)
        out.append(record(f"secret-{len(out):03d}", doc, ["secrets", tag, f"ctx:{ctx}"]))
    # 4 private keys.
    for kind, ctx in [("RSA PRIVATE KEY", "file"), ("OPENSSH PRIVATE KEY", "file"), ("EC PRIVATE KEY", "yaml"), ("PRIVATE KEY", "json")]:
        pem = sec.pem(kind)
        d = Doc()
        if ctx == "file":
            d.add("$ cat ~/.ssh/deploy_key\n", (pem, "SECRET"), "\n")
        elif ctx == "yaml":
            indented = pem.replace("\n", "\n    ")
            d.add("tls:\n  key: |\n    ", (indented, "SECRET"), "\n  cert_file: /etc/tls/server.crt\n")
        else:
            escaped = pem.replace("\n", "\\n")
            d.add('{\n  "type": "service_account",\n  "project_id": "acme-prod-42",\n  "private_key": "', (escaped, "SECRET"), '",\n  "client_id": "1049231"\n}\n')
        out.append(record(f"secret-{len(out):03d}", d, ["secrets", "private-key", f"ctx:{ctx}"]))
    # 5 .env files with several secrets each.
    for _ in range(5):
        d = Doc().add("# .env.local\nNODE_ENV=development\nPORT=3000\n")
        picks = r.sample(PROVIDERS, 3)
        for tag, fn, names in picks:
            d.add(f"{names[0].upper().replace('.', '_')}=", (getattr(sec, fn)(), "SECRET"), "\n")
        d.add("DB_PASSWORD=", (sec.password(), "SECRET"), "\nLOG_LEVEL=debug\n")
        out.append(record(f"secret-{len(out):03d}", d, ["secrets", "env-file"] + [p[0] for p in picks]))
    # 6 connection strings: only the password is the secret.
    for scheme, user, host in [
        ("postgres", "app", "db.prod.internal:5432/orders"),
        ("postgresql", "analytics_ro", "10.20.0.15:5432/warehouse?sslmode=require"),
        ("mysql", "root", "mysql-primary:3306/shop"),
        ("redis", "", "cache.prod.internal:6379/0"),
        ("mongodb+srv", "svc-api", "cluster0.x7k2p.mongodb.net/prod?retryWrites=true"),
        ("amqp", "worker", "rabbitmq.internal:5672/jobs"),
    ]:
        pw = sec.password().replace("@", "#").replace("/", "-")
        d = Doc().add(f"DATABASE_URL=\"{scheme}://{user}:", (pw, "SECRET"), f"@{host}\"\n")
        out.append(record(f"secret-{len(out):03d}", d, ["secrets", "connection-string", scheme]))
    # 5 password assignments in different formats.
    for fmt in ["yaml", "ini", "xml", "python", "properties"]:
        pw = sec.password()
        d = Doc()
        if fmt == "yaml":
            d.add("database:\n  host: db.internal\n  user: svc_billing\n  password: ", (pw, "SECRET"), "\n")
        elif fmt == "ini":
            d.add("[smtp]\nserver = smtp.mailgun.org\nlogin = postmaster@mg.acme-mail.com\npassword = ", (pw, "SECRET"), "\n")
        elif fmt == "xml":
            d.add('<dataSource>\n  <username>etl</username>\n  <password>', (pw, "SECRET"), "</password>\n</dataSource>\n")
        elif fmt == "python":
            d.add("conn = psycopg.connect(host=\"db\", user=\"etl\", password=\"", (pw, "SECRET"), "\")\n")
        else:
            d.add("spring.datasource.url=jdbc:postgresql://db:5432/app\nspring.datasource.password=", (pw, "SECRET"), "\n")
        out.append(record(f"secret-{len(out):03d}", d, ["secrets", "password", f"ctx:{fmt}"]))
    # 4 secrets that only context reveals: no provider prefix, no assignment keyword.
    d = Doc().add("Hey, the Datadog key for staging is ", (sec.hex_key(32), "SECRET"), " - please rotate it after the demo.\n")
    out.append(record(f"secret-{len(out):03d}", d, ["secrets", "contextual", "hex"]))
    d = Doc().add("> what's the wifi password for the office?\nit's ", (sec.password(), "SECRET"), " (changes every quarter)\n")
    out.append(record(f"secret-{len(out):03d}", d, ["secrets", "contextual", "prose-password"]))
    d = Doc().add("Run the migration with:\n\n    ./migrate --url https://ops.acme.dev --auth ", (sec.opaque(40), "SECRET"), "\n")
    out.append(record(f"secret-{len(out):03d}", d, ["secrets", "contextual", "cli-flag"]))
    d = Doc().add("user: can you check why this fails?\nTraceback: AuthError: invalid credentials for key '", (sec.opaque(32), "SECRET"), "'\n")
    out.append(record(f"secret-{len(out):03d}", d, ["secrets", "contextual", "traceback"]))
    assert len(out) == 50, len(out)
    return out


class People:
    def __init__(self, fake: Faker, rng: random.Random):
        self.f = fake
        self.r = rng

    def name(self):
        return f"{self.f.first_name()} {self.f.last_name()}"

    def email(self, name=None):
        name = name or self.name()
        user = name.lower().replace(" ", self.r.choice([".", "_", ""]))
        return f"{user}@{self.r.choice(['gmail.com', 'outlook.com', 'fastmail.com', 'icloud.com', 'protonmail.com'])}"

    def phone(self):
        return self.r.choice([
            f"+1 {self.r.randint(201, 989)} {self.r.randint(200, 999)} {self.r.randint(1000, 9999)}",
            f"({self.r.randint(201, 989)}) {self.r.randint(200, 999)}-{self.r.randint(1000, 9999)}",
            f"{self.r.randint(201, 989)}-{self.r.randint(200, 999)}-{self.r.randint(1000, 9999)}",
            f"+44 7{self.r.randint(100, 999)} {self.r.randint(100000, 999999)}",
        ])

    def address(self):
        return f"{self.f.street_address()}, {self.f.city()}, {self.f.state_abbr()} {self.f.zipcode()}"

    def dob(self):
        d = self.f.date_of_birth(minimum_age=18, maximum_age=80)
        return self.r.choice([d.isoformat(), d.strftime("%m/%d/%Y"), d.strftime("%B %-d, %Y")])

    def iban(self):
        return self.f.iban()

    def card(self):
        return self.f.credit_card_number(card_type=self.r.choice(["visa", "mastercard", "amex"]))

    def url(self, name):
        slug = name.lower().replace(" ", "-")
        return f"https://www.linkedin.com/in/{slug}-{self.r.randint(100, 999)}"


def gen_pii(r: random.Random, fake: Faker) -> list[dict]:
    p = People(fake, r)
    out = []

    def add(doc, kind):
        out.append(record(f"pii-{len(out):03d}", doc, ["pii", f"ctx:{kind}"]))

    for i in range(40):
        kind = i % 10
        n = p.name()
        if kind == 0:
            add(Doc().add("# -*- coding: utf-8 -*-\n# Author: ", (n, "PERSON"), " <", (p.email(n), "EMAIL"), ">\n# Created: 2024-03-02\n\nimport logging\n"), "comment")
        elif kind == 1:
            add(Doc().add("fix(auth): refresh tokens before expiry\n\nReported-by: ", (n, "PERSON"), " <", (p.email(n), "EMAIL"), ">\nCloses #4471\n"), "commit")
        elif kind == 2:
            add(Doc().add("2026-10-12T08:14:22Z INFO signup.completed user_id=88213 email=", (p.email(), "EMAIL"), " phone=", (p.phone(), "PHONE"), " plan=pro\n"), "log")
        elif kind == 3:
            add(Doc().add('{\n  "id": 1042,\n  "full_name": "', (n, "PERSON"), '",\n  "email": "', (p.email(n), "EMAIL"), '",\n  "date_of_birth": "', (p.dob(), "DATE"), '",\n  "shipping_address": "', (p.address(), "ADDRESS"), '"\n}\n'), "json")
        elif kind == 4:
            add(Doc().add("INSERT INTO customers (name, email, card_number) VALUES ('", (n, "PERSON"), "', '", (p.email(n), "EMAIL"), "', '", (p.card(), "ACCOUNT"), "');\n"), "sql")
        elif kind == 5:
            n2 = p.name()
            add(Doc().add("name,email,phone\n", (n, "PERSON"), ",", (p.email(n), "EMAIL"), ",", (p.phone(), "PHONE"), "\n", (n2, "PERSON"), ",", (p.email(n2), "EMAIL"), ",", (p.phone(), "PHONE"), "\n"), "csv")
        elif kind == 6:
            add(Doc().add("Ticket #88123: Customer ", (n, "PERSON"), " called from ", (p.phone(), "PHONE"), " asking for the refund to go to ", (p.iban(), "ACCOUNT"), " instead of the card on file.\n"), "ticket")
        elif kind == 7:
            add(Doc().add("users:\n  - username: ops-admin\n    display_name: ", (n, "PERSON"), "\n    profile: ", (p.url(n), "URL"), "\n    home: ", (p.address(), "ADDRESS"), "\n"), "yaml")
        elif kind == 8:
            add(Doc().add("From: ", (n, "PERSON"), " <", (p.email(n), "EMAIL"), ">\nTo: support@acme-shop.com\nSubject: Order 55120 never arrived\n\nHi, I was born ", (p.dob(), "DATE"), " in case you need it for verification.\n"), "email")
        else:
            add(Doc().add("Traceback (most recent call last):\n  File \"/app/billing/charge.py\", line 88, in charge\n    raise PaymentDeclined(customer=\"", (p.email(), "EMAIL"), "\", card=\"", (p.card(), "ACCOUNT"), "\")\nbilling.errors.PaymentDeclined\n"), "traceback")
    return out


# --- Long, realistic records ----------------------------------------------------------

WORDS = ["order", "invoice", "user", "cart", "payment", "shipment", "token", "session", "report", "account", "item", "queue", "job", "event", "cache"]
VERBS = ["get", "load", "build", "sync", "parse", "render", "update", "validate", "resolve", "flush", "fetch", "compute"]


def filler_block(r: random.Random, fake: Faker) -> str:
    kind = r.randrange(5)
    w, v = r.choice(WORDS), r.choice(VERBS)
    if kind == 0:
        arg = r.choice(WORDS)
        return (
            f"def {v}_{w}(self, {arg}_id: int, *, force: bool = False) -> dict:\n"
            f'    """{fake.sentence(nb_words=10)}"""\n'
            f"    cached = self._cache.get(({arg}_id, force))\n"
            f"    if cached is not None and not force:\n"
            f"        return cached\n"
            f"    rows = self.db.execute(\"SELECT * FROM {w}s WHERE {arg}_id = %s LIMIT %s\", ({arg}_id, {r.randint(10, 500)}))\n"
            f"    result = {{row['id']: self._{v}_row(row) for row in rows}}\n"
            f"    log.debug(\"{v}_{w} {arg}_id=%s n=%d\", {arg}_id, len(result))\n"
            f"    self._cache[({arg}_id, force)] = result\n"
            f"    return result\n\n"
        )
    if kind == 1:
        lines = []
        for _ in range(r.randint(4, 9)):
            uid = fake.uuid4()
            lines.append(
                f"2026-10-{r.randint(10, 28):02d}T{r.randint(0, 23):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}.{r.randint(0, 999):03d}Z "
                f"{r.choice(['INFO', 'INFO', 'DEBUG', 'WARN'])} [{w}-svc] {r.choice(['GET', 'POST', 'PUT'])} /api/v1/{w}s/{uid} "
                f"status={r.choice([200, 200, 201, 204, 404, 409])} duration_ms={r.randint(2, 900)} request_id={fake.hexify('^' * 16)}"
            )
        return "\n".join(lines) + "\n"
    if kind == 2:
        items = ", ".join(f'{{"sku": "{w.upper()}-{r.randint(100, 999)}", "qty": {r.randint(1, 5)}}}' for _ in range(r.randint(1, 4)))
        return (
            "{\n"
            f'  "id": "{fake.uuid4()}",\n  "status": "{r.choice(["pending", "paid", "shipped"])}",\n'
            f'  "created_at": "2026-10-{r.randint(10, 28):02d}T{r.randint(0, 23):02d}:00:00Z",\n'
            f'  "items": [{items}],\n  "commit": "{fake.sha1()}"\n'
            "}\n"
        )
    if kind == 3:
        return f"## {v.title()} {w}s\n\n{fake.paragraph(nb_sentences=4)}\n\n"
    return (
        "Traceback (most recent call last):\n"
        f'  File "/app/src/{w}/{v}.py", line {r.randint(10, 400)}, in {v}_{w}\n'
        f"    return self._backend.{v}({w}_id)\n"
        f'  File "/app/src/{w}/backend.py", line {r.randint(10, 400)}, in {v}\n'
        f"    raise {w.title()}Error(\"{fake.sentence(nb_words=6)}\")\n\n"
    )


def gen_long(r: random.Random, fake: Faker, sec: Secrets, count_tokens) -> list[dict]:
    out = []
    people = People(fake, r)
    plan = [("1k", 1000)] * 7 + [("4k", 4000)] * 7 + [("8k", 8000)] * 6
    for i, (size, target) in enumerate(plan):
        n_secrets = i % 4
        n_pii = r.randint(0, 2)
        blocks = []
        while count_tokens("".join(blocks)) < target * 0.92:
            blocks.extend(filler_block(r, fake) for _ in range(5))
        # Trim to the target, then bury secrets and personal data at random block boundaries.
        while count_tokens("".join(blocks)) > target * 0.97 and len(blocks) > 1:
            blocks.pop()
        inserts = []
        for _ in range(n_secrets):
            tag, fn, names = r.choice(PROVIDERS)
            inserts.append(secret_in_context(r, r.choice(names), getattr(sec, fn)(), r.choice(CONTEXTS[:11])))
        for _ in range(n_pii):
            n = people.name()
            inserts.append(Doc().add("# Maintainer: ", (n, "PERSON"), " <", (people.email(n), "EMAIL"), ">\n"))
        positions = sorted(r.choices(range(len(blocks)), k=len(inserts)))
        d = Doc()
        k = 0
        for j, block in enumerate(blocks):
            while k < len(inserts) and positions[k] == j:
                ins = inserts[k]
                base = d.n
                d.parts.append(ins.text)
                d.spans.extend({**s, "start": s["start"] + base, "end": s["end"] + base} for s in ins.spans)
                d.n += len(ins.text)
                k += 1
            d.add(block)
        out.append(record(f"long-{len(out):03d}", d, ["long", f"size:{size}", f"secrets:{n_secrets}"]))
    return out


def token_counter():
    try:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        path = hf_hub_download("mlx-community/openai-privacy-filter-bf16", "tokenizer.json", local_files_only=True)
        tok = Tokenizer.from_file(path)
        return lambda text: len(tok.encode(text, add_special_tokens=False).ids)
    except Exception:
        print("warning: Privacy Filter tokenizer not cached; estimating 4 characters per token", file=sys.stderr)
        return lambda text: len(text) // 4


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--negatives", choices=["main", "holdout", "holdout2", "holdout3"], default="main",
                    help="Which hand-written hard negatives to write (holdout sets were never used for tuning).")
    args = ap.parse_args()
    r = random.Random(args.seed)
    fake = Faker("en_US")
    Faker.seed(args.seed)
    sec = Secrets(r)
    groups = {
        "secrets": gen_secrets(r, sec),
        "pii": gen_pii(r, fake),
        "negatives": [
            {"id": f"neg-{i:03d}", "text": text, "spans": [], "tags": ["negatives", name]}
            for i, (name, text) in enumerate({"main": NEGATIVES, "holdout": HOLDOUT_NEGATIVES, "holdout2": HOLDOUT2_NEGATIVES,
                                              "holdout3": HOLDOUT3_NEGATIVES}[args.negatives])
        ],
        "long": gen_long(r, fake, sec, token_counter()),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for name, records in groups.items():
        with open(args.out / f"{name}.jsonl", "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        print(f"{name}: {len(records)} records -> {args.out / f'{name}.jsonl'}")


if __name__ == "__main__":
    main()
