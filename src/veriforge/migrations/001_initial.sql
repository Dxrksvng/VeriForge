CREATE TABLE IF NOT EXISTS schema_migrations(version integer PRIMARY KEY, applied_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS accounts(
 tenant text NOT NULL, id text NOT NULL, currency text NOT NULL CHECK(currency IN ('THB','USD')),
 balance bigint NOT NULL CHECK(balance >= 0), PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS payments(
 id uuid PRIMARY KEY, tenant text NOT NULL, idem_key text NOT NULL, fingerprint text NOT NULL,
 source text NOT NULL, destination text NOT NULL, amount bigint NOT NULL CHECK(amount>0),
 fee bigint NOT NULL CHECK(fee>=0), currency text NOT NULL, pricing_version text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant,idem_key),
 FOREIGN KEY(tenant,source) REFERENCES accounts(tenant,id),
 FOREIGN KEY(tenant,destination) REFERENCES accounts(tenant,id));
CREATE TABLE IF NOT EXISTS postings(
 payment_id uuid NOT NULL REFERENCES payments(id), account_id text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('debit','credit','fee')), delta bigint NOT NULL,
 PRIMARY KEY(payment_id,kind));
CREATE OR REPLACE FUNCTION check_balanced_payment() RETURNS trigger AS $$
BEGIN
 IF (SELECT count(*) FROM postings WHERE payment_id=NEW.id) <> 3
 OR (SELECT coalesce(sum(delta),0) FROM postings WHERE payment_id=NEW.id) <> 0 THEN
 RAISE EXCEPTION 'Ledger must contain three balanced postings'; END IF;
 RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS balanced_payment ON payments;
CREATE CONSTRAINT TRIGGER balanced_payment AFTER INSERT ON payments
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_balanced_payment();
CREATE TABLE IF NOT EXISTS changes(
 id uuid PRIMARY KEY, title text NOT NULL, requirement text NOT NULL, source text NOT NULL,
 digest text NOT NULL, builder text NOT NULL, provenance text NOT NULL,
 status text NOT NULL DEFAULT 'PROPOSED', policy_version text NOT NULL DEFAULT 'local-v1',
 evidence jsonb, evidence_mac text, review jsonb, approved_by text, approved_at timestamptz,
 image_id text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS jobs(
 id uuid PRIMARY KEY, change_id uuid NOT NULL REFERENCES changes(id), kind text NOT NULL,
 status text NOT NULL DEFAULT 'QUEUED', attempts integer NOT NULL DEFAULT 0,
 lease_until timestamptz, claim_token uuid, error text, created_at timestamptz DEFAULT now());
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(change_id,kind) WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS deployments(
 id uuid PRIMARY KEY, change_id uuid REFERENCES changes(id), image_id text NOT NULL,
 container_id text NOT NULL, port integer NOT NULL, status text NOT NULL,
 metrics jsonb, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS incidents(
 id uuid PRIMARY KEY, deployment_id uuid REFERENCES deployments(id), kind text NOT NULL,
 status text NOT NULL, evidence jsonb NOT NULL, diagnosis jsonb,
 detected_at timestamptz DEFAULT now(), recovered_at timestamptz);
CREATE TABLE IF NOT EXISTS audit(
 id bigserial PRIMARY KEY, actor text NOT NULL, action text NOT NULL, resource text NOT NULL,
 details jsonb NOT NULL DEFAULT '{}', created_at timestamptz DEFAULT now());
ALTER TABLE audit ADD COLUMN IF NOT EXISTS prev_hash text;
ALTER TABLE audit ADD COLUMN IF NOT EXISTS event_hash text;
CREATE TABLE IF NOT EXISTS model_usage(
 id uuid PRIMARY KEY, role text NOT NULL, model text NOT NULL, status text NOT NULL,
 tokens integer NOT NULL DEFAULT 0, duration_ms integer NOT NULL DEFAULT 0,
 created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS http_events(
 id bigserial PRIMARY KEY, path text NOT NULL, status integer NOT NULL, duration_ms double precision NOT NULL,
 trace_id text NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS sessions(
 jti_hash text PRIMARY KEY, subject text NOT NULL, role text NOT NULL, tenant text NOT NULL,
 issued_at timestamptz NOT NULL, expires_at timestamptz NOT NULL, revoked_at timestamptz,
 created_at timestamptz DEFAULT now());
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
INSERT INTO schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION reject_ledger_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'Posted financial records are append-only; use compensating entries'; END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS immutable_postings ON postings;
CREATE TRIGGER immutable_postings BEFORE UPDATE OR DELETE ON postings FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
DROP TRIGGER IF EXISTS immutable_payments ON payments;
CREATE TRIGGER immutable_payments BEFORE UPDATE OR DELETE ON payments FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
