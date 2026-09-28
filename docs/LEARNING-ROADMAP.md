# แผนเรียนรู้ทั้งระบบจากโค้ดที่ทำงานจริง

ทุก module ใช้กระบวนการใน [ข้อตกลงการทำงาน](WORKING-AND-LEARNING-AGREEMENT.md) และบันทึกสถานะใน [PROGRESS](PROGRESS.md) ลำดับนี้เป็นเส้นทางเริ่มต้น ปรับได้ตาม prerequisite และผลการทดลอง ไม่ใช่ตารางเวลารับประกัน

## ภาพรวมระบบที่ต้องอธิบายได้เมื่อจบ

```text
Requirement / Issue / Incident
  → Builder: inspect → propose patch
  → Identity + repository/policy boundary
  → Isolated execution: tests / scans / adversarial cases
  → Evidence bundle + Verifier findings
  → Deterministic decision
  → Human approval (ตาม policy)
  → Deploy approved artifact
  → Runtime observation
  → Detect incident → diagnose → stop/rollback/patch
  → Verify again → postmortem → regression memory
```

## M00 — พื้นฐานเครื่องมือและแผนที่โปรเจกต์

- **หลักการ:** file/folder, process, terminal, dependency, virtual environment, Git diff, environment variable และ secret
- **ลงมือ:** ตรวจเครื่องและสถานะ repository; เตรียมคำสั่งรันมาตรฐานและ project layout ที่เล็กที่สุด ยังไม่สมัคร cloud
- **พาอ่าน:** entry point, configuration และเส้นทาง request โดยระบุอะไรยังไม่ implement
- **ทดลอง:** configuration ที่จำเป็นหายแล้วระบบควรแจ้งอะไร โดยไม่แสดง secrets
- **ตรวจรับ:** documented startup ใช้ได้จริงบนเครื่องนี้ ระบุ prerequisite ที่ยังขาด
- **Teach-back:** code file กับ process ต่างกันอย่างไร? dependency อยู่ตรงไหน? ทำไมไม่ commit secrets?

## M01 — API และข้อมูลหนึ่งรายการ

- **หลักการ:** HTTP method/status, JSON, function, type, validation, exception, input/output
- **ลงมือ:** payment request ด้วย amount/currency และ identifiers; health endpoint; แยก API schema จาก domain logic
- **พาอ่าน:** route → validation → domain function → response พร้อมตัวอย่าง valid/invalid input
- **ทดลอง:** negative amount, missing field, malformed input
- **ตรวจรับ:** contract ชัดเจนและ tests พิสูจน์ invalid input ไม่สร้าง financial effects
- **Teach-back:** อะไรควรตรวจที่ API และอะไรต้องตรวจใน domain? HTTP success พิสูจน์ว่าเงินถูกหรือไม่?

## M02 — Database, transaction และ ledger

- **หลักการ:** table/key/index, constraint, commit/rollback, migration, monetary precision และ debit/credit
- **ลงมือ:** PostgreSQL สำหรับ account/payment/ledger; deterministic fee rule; transaction boundary
- **พาอ่าน:** read/write path และจุดที่ posting ต้องสำเร็จพร้อมกัน
- **ทดลอง:** ล้มก่อน commit แล้วเทียบจำนวน records/balances; จำนวนเงินที่มี rounding edge
- **ตรวจรับ:** actual PostgreSQL integration tests; ledger สมดุลแยก currency; ไม่ทิ้ง partial posting
- **Teach-back:** DB rollback ต่างจาก release rollback อย่างไร? float ทำให้ยอดผิดได้อย่างไร?

## M03 — Idempotency, retries และ concurrency

- **หลักการ:** request identity, payload fingerprint, race condition, isolation และ uniqueness
- **ลงมือ:** ทำ duplicate-fee reproducer ใน test-only fixture ก่อนสร้างทางแก้; scope key ตาม tenant/operation และกำหนด key lifecycle
- **พาอ่าน:** รับ key → ตรวจ payload → จอง/อ่าน operation → financial transaction → เก็บผล → ตอบ client
- **ทดลอง:** timeout หลัง commit, concurrent same-key calls, same-key different amount, restart/retry
- **ตรวจรับ:** ไม่สร้าง financial effect ซ้ำ; payload mismatch ปฏิเสธ; tests รันบน DB จริงและไม่พึ่ง sleep อย่างเดียวเพื่อสร้าง race
- **Teach-back:** ทำไม `if status != completed` ไม่พอ? อะไรรับประกัน uniqueness? key หมดอายุมีผลอย่างไร?

## M04 — Tests, trusted controls และ evidence

- **หลักการ:** unit/integration/regression/property-based tests, test oracle, exit code, raw artifact, evidence provenance
- **ลงมือ:** trusted regression suite, runner output parser และ evidence bundle ผูกกับ revision/configuration
- **พาอ่าน:** test input → execution → assertion → raw output → normalized evidence
- **ทดลอง:** test fail, process timeout, malformed output, missing evidence และ evidence ของคนละ revision
- **ตรวจรับ:** แยก PASS/FAIL/ERROR/INCONCLUSIVE ตาม contract; ไม่มี false pass เมื่อ parser/scanner ล้ม
- **Teach-back:** tests ผ่านยังไม่พิสูจน์อะไร? ใครแก้ trusted test ได้? screenshot เพียงอย่างเดียวพอหรือไม่?

## M05 — Identity และ authorization

- **หลักการ:** authentication vs authorization, user/service identity, RBAC, least privilege, segregation of duties
- **ลงมือ:** role/permission matrix และ enforcement ตั้งแต่เริ่ม control API; ขยาย integration กับ identity provider ตามความจำเป็น
- **พาอ่าน:** identity → resource/action → policy → allow/deny; tenant scope ของ evidence และ approvals
- **ทดลอง:** Builder approve/deploy ตัวเอง, unauthorized evidence read, cross-tenant request, expired credential
- **ตรวจรับ:** negative authorization tests; สิทธิ์ตรวจฝั่ง server ทุก transition ไม่พึ่งซ่อนปุ่ม
- **Teach-back:** token ถูกต้องแต่ไม่มีสิทธิ์ได้หรือไม่? role เดียวกันต่าง tenant อ่านข้อมูลกันได้ไหม?

## M06 — Durable jobs และ state machine

- **หลักการ:** state/transition, queue, lease, heartbeat, retry/backoff, cancellation, at-least-once processing
- **ลงมือ:** persistent changes/jobs/events และ worker; transition rules อยู่ฝั่ง server
- **พาอ่าน:** enqueue → claim → execute → persist → completion; จุดที่ต้อง deduplicate side effects
- **ทดลอง:** worker ตายหลังทำงานแต่ก่อน ack, duplicate webhook/job, expired lease, cancel ระหว่างรัน
- **ตรวจรับ:** restart แล้วเดินต่อได้; ไม่มี deploy ซ้ำ; invalid transition ถูกปฏิเสธ
- **Teach-back:** retry job เท่ากับปลอดภัยเสมอหรือไม่? อะไรต้อง idempotent?

## M07 — Security scans และ isolated execution

- **หลักการ:** untrusted code, filesystem/network boundary, process/container/VM, secrets, dependency risk
- **ลงมือ:** scanner adapters สำหรับ Gitleaks/Semgrep/Trivy ตาม scope; runner แยกจาก credentials/control plane
- **พาอ่าน:** execution specification → limits → raw report → finding normalization → evidence
- **ทดลอง:** scanner unavailable, crafted findings, forbidden network/tool action ใน sandbox
- **ตรวจรับ:** ไม่ปล่อยเมื่อ mandatory scan ไม่ครบ; ไม่มี secrets ใน logs; จำกัด resource/time และตรวจขอบเขต runner
- **Teach-back:** container อย่างเดียวรับประกัน isolation แค่ไหน? scanner ไม่พบอะไรเท่ากับปลอดภัยหรือไม่?

## M08 — Deterministic policy และ risk decision

- **หลักการ:** hard gates, soft findings, policy version, exception expiry, explainability, TOCTOU
- **ลงมือ:** input schema ของ evidence และ deterministic decision engine ก่อนต่อ LLM
- **พาอ่าน:** verify evidence identity/completeness → hard gates → risk/review → approval requirement
- **ทดลอง:** ต่ำคะแนนแต่ invariant fail, policy เปลี่ยน, exception หมดอายุ, stale evidence
- **ตรวจรับ:** same versioned input ให้ decision เดิม; block conditions เอาชนะ score; reason อ้าง evidence จริง
- **Teach-back:** risk score มีหน้าที่อะไร? approval เดิมใช้กับ code ใหม่ได้ไหม?

## M09 — Builder และ Independent Verifier AI

- **หลักการ:** probabilistic model, structured output, tool permissions, context separation, prompt injection, cost budget
- **ลงมือ:** provider adapter; Builder เสนอ patch; Verifier รับ requirement/diff/evidence และเสนอ findings/adversarial tests
- **พาอ่าน:** context assembly → model call → schema validation → constrained tool execution → evidence-linked findings
- **ทดลอง:** hallucinated evidence reference, invalid JSON, injected instruction ใน diff/log, provider timeout, budget exhausted
- **ตรวจรับ:** ไม่มี silent pass; AI ไม่มีอำนาจลบ hard gate; trusted tests แก้โดย Builder ไม่ได้; model usage บันทึกจริง
- **Teach-back:** คนละ model ทำให้อิสระจริงหรือไม่? Verifier เห็นผลทดสอบแต่เชื่ออะไรได้บ้าง?

## M10 — CI/CD, artifacts และ approval

- **หลักการ:** commit vs tag vs digest, reproducible inputs, build provenance, supply chain, release identity
- **ลงมือ:** CI รัน checks จริง; build artifact; approval ผูก digest; restricted deployer
- **พาอ่าน:** PR → build/checks → evidence → approval → artifact verification → staging
- **ทดลอง:** แก้ source หลังอนุมัติ, สลับ artifact, replay approval, untrusted workflow request
- **ตรวจรับ:** deploy ได้เฉพาะ artifact ที่ผ่านและอนุมัติ; identity แต่ละส่วนทำเกินหน้าที่ไม่ได้
- **Teach-back:** ทำไมชื่อ image tag อย่างเดียวไม่พอ? ใครเชื่อถือใครใน build chain?

## M11 — Runtime, canary และ observability

- **หลักการ:** logs/metrics/traces, correlation ID, counter/histogram, SLI/SLO, sampling, baseline, sample size
- **ลงมือ:** instrumentation ของ target/control plane; canary หรือ staged rollout ที่ระบุข้อจำกัด
- **พาอ่าน:** request → span/events → metrics → query → release decision
- **ทดลอง:** error rate/latency regression, telemetry missing, traffic ต่ำและ window ไม่พอ
- **ตรวจรับ:** dashboard อ้าง metric จริง; ไม่มีข้อมูลต้องไม่เป็น healthy โดยอัตโนมัติ; low sample เป็น inconclusive
- **Teach-back:** p95 ต่างจากค่าเฉลี่ยอย่างไร? correlation บอก root cause ได้หรือยัง?

## M12 — Incident, recovery และ backup

- **หลักการ:** symptom vs cause, blast radius, rollback vs compensation, RPO/RTO, recovery verification
- **ลงมือ:** incident timeline/runbook, controlled faults, image rollback, DB restore และ financial reconciliation
- **พาอ่าน:** detect → contain → diagnose → choose recovery → execute → verify → postmortem
- **ทดลอง:** DB lock, process crash, duplicate event และ restore ลง environment ใหม่
- **ตรวจรับ:** evidence ของ detection/recovery; schema compatibility; ไม่อ้าง rollback ว่าย้อน external payment; restore ใช้ได้จริง
- **Teach-back:** อะไรต้องหยุดก่อนแก้? backup ที่ไม่เคย restore เชื่อถือได้แค่ไหน?

## M13 — Datasets, evaluation และ load tests

- **หลักการ:** ground truth, sampling, leakage, benchmark contamination, confusion matrix, cost/performance trade-off
- **ลงมือ:** dataset manifests, PaySim adapter ตามความเหมาะสม, SWE-bench subset แยกจาก finance benchmark; workload ของระบบเรา
- **พาอ่าน:** source → transform → replay → raw evidence → metric computation → report
- **ทดลอง:** compare deterministic-only / plus Verifier / full Builder loop; repeat with pinned configuration
- **ตรวจรับ:** แยก good/bad/unknown; รายงาน false blocks, missed defects, inconclusive, sample size และข้อจำกัด
- **Teach-back:** fraud label ใช้เป็น label ของ code bug ได้ไหม? sample น้อยอ้าง 99% reliability ได้ไหม?

## M14 — Dashboard, pilot และ maintenance

- **หลักการ:** status semantics, evidence drill-down, stale data, operator UX, support/incident ownership, cost controls
- **ลงมือ:** dashboard อ่าน API จริง; pilot สำหรับผู้ใช้/repos ที่อนุญาต; retention, backup schedule และ upgrade procedure
- **พาอ่าน:** UI action → auth → backend transition → event → UI refresh; ทุก metric ย้อนหา source ได้
- **ทดลอง:** stale evidence, unauthorized UI action, service restart, exhausted quota และ dependency upgrade
- **ตรวจรับ:** end-to-end acceptance suite, operating runbook, known limitations และ budget ที่บังคับจริง
- **Teach-back:** ถ้าระบบล่มใครรู้และทำอะไร? metric ไหนเป็นจริง/จำลอง? ขยายระบบเมื่อมีหลักฐานอะไร?

## ความสัมพันธ์และการสอนซ้ำ

M05 identity ต้องเริ่มพร้อม control API ไม่ใช่รอจนระบบสมบูรณ์ M13 เก็บ manifest/evaluation foundations ตั้งแต่เริ่มใช้ข้อมูล M14 ทำ UI ทีละส่วนเมื่อ backend มีข้อมูลจริง ไม่รอท้ายสุด ส่วน M00–M04 เป็นวงจรแรกที่ต้องทำให้รันได้

กลับไปทบทวน module เดิมเมื่อเกิด bug ที่เกี่ยวข้องหรือผู้ใช้ยังอธิบายไม่ได้ โดยใช้ code/evidence ปัจจุบัน ไม่เริ่มหลักสูตรใหม่ทั้งหมด
