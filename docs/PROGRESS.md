# สถานะและจุดต่อของ VeriForge

## อัปเดตเอกสาร repository — 28 กันยายน 2026

ปรับ README เพื่ออธิบาย local simulation, วิธีรัน, ขอบเขตหลักฐาน และข้อจำกัดสำหรับผู้อ่าน GitHub การเปลี่ยนแปลงรอบนี้เป็นเอกสาร/การคัดไฟล์ขึ้น repo; รัน `.venv/bin/pytest -q` ได้ 33 passed, 2 dependency warnings และ GitHub workflow ผ่าน แต่ยังไม่ได้รัน lifecycle ใหม่และไม่เปลี่ยนสถานะ Engineering หรือ Learning ด้านล่าง

อัปเดต: 27 กันยายน 2026 — local production-simulation v2 accepted

## Engineering

Local production-simulation v2 ทำงานครบเส้นทางหลักและตรวจจริงแล้ว: signed/revocable session → PostgreSQL ledger → proposal → isolated tests/scanners → independent-context AI review → deterministic gate → approval → actual Docker release → injected fault → rollback/recovery → HMAC-chained audit verification

ไม่ใช่การรับรองว่า enterprise roadmap ทุก phase หรือ production พร้อมเงินจริงเสร็จแล้ว ขอบเขตคือหนึ่ง local tenant, financial-policy สองฟังก์ชัน และ target Docker ในเครื่อง อ่าน docs/VALIDATION.md และ docs/RUNBOOK.md ก่อนขยาย

## หลักฐานล่าสุด

- Backend: 33 passed, 2 dependency deprecation warnings; รวม expiry/tamper/revocation/role negative tests และ append-only audit test
- Lint และ TypeScript/Vite production build ผ่าน
- Browser Chrome: login, payment/replay/conflict, fixture/verification queue, viewer restriction และ mobile ไม่มี page overflow ผ่าน; artifacts/*.png
- Real Gitleaks + Semgrep + Trivy และ 12 trusted financial cases ผ่านใน baseline/AI repair ที่ปล่อยจริง
- Model repair: first patch ผิด validation; repair เดิมเรียก isinstance ที่นโยบายห้าม; แก้ context ให้ส่งทุก failed check แล้วโมเดลสร้าง patch ผ่านเอง ไม่ได้ลด gate
- Successful repair change: 11354088-f18c-406e-b9bc-5c345d6a5b9c
- AI deployment: b465075f-4860-5153-95cc-96a2507e62df; injected process stop ทำให้ error_rate 1.0 จากนั้น rollback ไป baseline แล้ว error_rate 0.0, duplicates 0; artifacts/lifecycle.json completed PASS
- Active baseline หลัง recovery: 6742e3dd-3e2c-5e2c-90d3-0a421740cfbb
- UCI Online Retail: 500 transformed amounts, two requests each, 500 payments, 0 failures, 0 ledger imbalances; ดูค่ารอบล่าสุดใน artifacts/dataset-evaluation.json; ไม่ใช่ bank traffic หรือ FX conversion
- Signed-identity concurrency: 100 identities/100 requests สำเร็จ 100, failures 0, p95 1,475.59 ms, wall 2,093.39 ms; เป็น local read workload ไม่ใช่ 100 LLM agents; artifacts/control-plane-load.json
- Bootstrap secret ใช้ได้เฉพาะ `POST /api/session`; session มี HMAC signature, issuer, audience, role, tenant, exp, jti และ server-side registry; logout revoke แล้วใช้ซ้ำไม่ได้
- Audit เก่าและใหม่ถูกเชื่อมด้วย HMAC chain, ตารางปฏิเสธ UPDATE/DELETE และ `/api/audit/integrity` รายงาน VALID/INVALID
- Backup restore: .local/backups/20260921T133115Z.dump restored ลง DB ใหม่, counts 220 payments / 32 changes / 299 audit ณ snapshot, ledger imbalances 0; temporary restore DB ถูกลบหลังตรวจ ไม่แตะ live DB
- หลัง restart macOS: Docker รัน fsck และ mount VM filesystem กลับเป็น read/write; volume เดิมอยู่ครบ ไม่ได้ factory reset; `veriforge-db-1` healthy และ startup recovery เปิด ACTIVE release เดิมสำเร็จ
- Acceptance ล่าสุด: `/health` ผ่าน, Ruff ผ่าน, pytest 33 passed (2 dependency warnings), Vite production build ผ่าน และ Chrome desktop/mobile journey ผ่านหลังทดสอบ session exchange/revocation

## Running services ณเวลาบันทึก

- Runtime ปัจจุบัน: API `http://127.0.0.1:8123` PID 18012; worker/monitor เริ่มจาก run-local session 42241
- PostgreSQL 127.0.0.1:55432 — veriforge-db-1; volume veriforge_veriforge-db
- Ollama localhost:11434; qwen3.5:9b, unload หลัง call เพื่อลด memory pressure
- Exec startup session 55524 อาจสิ้นสุดเมื่อ session/tool host ปิด ให้ตรวจ process ก่อนเริ่มใหม่ อย่าอ้างว่าจะทำงานถาวรหลัง reboot

## ข้อจำกัดและสิ่งที่ยังต้องทำสำหรับ production จริง

- พื้นที่เครื่องเหลือประมาณ 13 GB หลัง restart; ควรรักษาพื้นที่เผื่อ Docker/scanners/model
- Local bootstrap secrets + expiring/revocable signed sessions แล้ว แต่ API/worker/deployer ยังเป็น OS user เดียวกันและไม่ใช่ external OIDC/workload identity
- Same local model, different contexts; ไม่มี statistical independence claim
- GitHub read-only adapter และ CI workflow มีแล้ว แต่ยังไม่เชื่อม repo ที่ได้รับอนุญาต/รัน hosted CI
- ไม่มี real-money provider, cloud HA, OIDC, external immutable audit/off-machine backup, distributed load หรือ live canary traffic
- ไม่มี verifier-generated executable adversarial tests หรือ incident-memory semantic retrieval; trusted test suite/incident records มีจริง
- รายละเอียด boundary และการทำต่ออยู่ใน ARCHITECTURE, RUNBOOK, VALIDATION
- Test-only changes มี [TEST] และ INJECTED_FAULT; อย่านำ mock evidence ใน test fixture ไปอ้างผล scanner จริง

## Learning

ยังไม่สอน/ยังไม่มี teach-back ตามคำสั่งให้ทำระบบก่อน มี SYSTEM-GUIDE-TH.md อธิบาย functions, input/output, side effects, permissions, failure และ tests; roadmap M00–M14 เป็นหลักสูตรและเป้าหมาย ไม่ใช่ checklist ว่าทำ enterprise features ครบแล้ว

เมื่อผู้ใช้พร้อม ให้เริ่มจาก financial request หนึ่งรายการ → retry → DB transaction → evidence → release ไม่ต้องให้พิมพ์ตามทุกบรรทัด

## Next action

ระบบ local production-simulation v2 พร้อมใช้งานแล้ว ขั้นต่อไปตามคำสั่งผู้ใช้คือเริ่มสอนจาก `docs/SYSTEM-GUIDE-TH.md` โดยเดิน session → payment → transaction/idempotency → evidence → release/recovery → audit integrity; ยังไม่ถือว่าผู้ใช้เข้าใจจนกว่าจะได้ทดลองหรือ teach-back
