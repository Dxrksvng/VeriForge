# คู่มือเรียนจากระบบ VeriForge ที่สร้างจริง

เอกสารนี้เก็บไว้สอนหลังงานพัฒนาเสร็จตามคำสั่งล่าสุด ผู้ใช้ยังไม่ถูกถือว่าเรียนหรือเข้าใจหัวข้อใดแล้วเพียงเพราะมีโค้ดหรือ tests ผ่าน

## เริ่มอ่านจากภาพรวม

เปิด dashboard แล้วดู Changes, Releases, Financial lab และ Audit trail สี่หน้าตอบคนละคำถาม: เปลี่ยนอะไร / ปล่อยอะไร / เงินบันทึกถูกหรือไม่ / ใครทำอะไร จากนั้นเปิด [Architecture](ARCHITECTURE.md) เพื่อดูขอบเขตความเชื่อถือ

## ลำดับบทเรียนเมื่อพร้อม

1. **หนึ่ง payment:** `api/app.py` → `finance.transfer()` → PostgreSQL → HTTP response
2. **retry และ race:** ใช้ key เดิมใน Financial lab และอ่าน `test_concurrent_retry_posts_once`
3. **transactions:** ทดลอง fault ก่อน commit และดู payment/postings/balances ว่าถูกยกเลิกพร้อมกัน
4. **change proposal:** ดู source, digest, identity และ provenance ของ change
5. **tests/scanners:** อ่าน `assurance.verify()` และผลจริงของ 5 mandatory checks
6. **AI boundaries:** ดูข้อเสนอที่ถูก block แล้วเทียบกับข้อเสนอที่แก้ผ่าน ห้ามใช้คำตอบของ AI แทนผลทดสอบ
7. **approval/deploy:** เปลี่ยนเป็น deployer identity และติดตาม image ID เดียวกันจาก evidence ถึง runtime
8. **incident/recovery:** ฉีด process stop แล้วอ่าน metrics, timeline และการกู้คืน
9. **data/evaluation:** อ่าน UCI manifest และแยกข้อมูลต้นทางจริงกับ workload ที่แปลงแล้ว
10. **operations:** ทดลอง restore ลง DB ใหม่ ดูคำสั่งใน runbook และอธิบายข้อจำกัดของ same-machine backup

## ฟังก์ชันหลักและเหตุผล

### `finance.minor_units(amount)`

แปลงจำนวนเงินเป็นหน่วยย่อยจำนวนเต็ม รับ string/decimal คืน integer ตรวจ finite, positive, maximum และทศนิยมไม่เกินสองหลักก่อนแปลง ไม่มี I/O จึงไม่มี partial effects หาก validation ล้ม ทดสอบด้วย negative, zero, NaN, infinity และ fraction เล็กเกิน precision

### `finance.transfer(tenant, source, destination, amount, currency, key)`

Caller คือ payment API ที่ตรวจ operator role แล้ว Tenant มาจาก identity ไม่รับจาก body ผลลัพธ์คือ payment record และ replay flag มี side effects ที่ accounts/payments/postings/audit ภายใน transaction เดียว

ลำดับ: normalize amount → fingerprint → lock tenant/key → คืนผลเก่าหรือ reject conflict → lock accounts ตามลำดับคงที่ → ขอ quote จาก active release ถ้ามี → ตรวจ quote ด้วย trusted invariant → เขียน payment/3 postings/balances → commit

เหตุผลที่ตรวจซ้ำใน kernel: AI-generated fee code อาจผิด แม้ผ่านชุดทดสอบบางส่วน เงินจึงต้องมี rule ที่เชื่อถือได้อีกชั้น Unique constraint เป็นแนวรับสุดท้ายของ duplicate key การ retry ก่อน commit จะรอ lock; หลัง commit จะได้ผลเดิม ก่อน commit crash จะ rollback ทั้ง transaction

ข้อจำกัด: fees account เป็นจุด contention; THB/USD ใช้ precision สองหลักเท่านั้น; ไม่อ้าง exactly-once ข้าม external bank; compensation ยังไม่อยู่ใน transfer use case นี้

### `identity.authenticate_bootstrap()`, `issue_session()`, `authenticate()` และ `require()`

bootstrap token ใช้ได้เฉพาะแลก session ระบบเปรียบเทียบ hash แบบ constant-time แล้วออก token ที่เซ็น HMAC พร้อม issuer, audience, subject, role, tenant, expiry และ jti โดยฐานข้อมูลเก็บเฉพาะ hash ของ jti ทุก API call ตรวจลายเซ็น claims อายุ และสถานะ revocation ก่อนคืน Principal จากนั้น endpoint ใช้ `require()` บังคับ role หรือคืน 403 การซ่อนปุ่ม UI เป็นแค่ UX; server เป็นผู้บังคับจริง

ข้อจำกัด: เป็น local bootstrap + session registry ไม่ใช่ external OIDC, MFA หรือ workload identity และ signing key ยังอยู่เครื่องเดียวกับระบบ ห้ามเผยแพร่เป็น public production authentication โดยไม่เพิ่ม trust boundary เหล่านี้

### `workflow.create_change()` และ `queue_verification()`

สร้าง immutable proposal พร้อม source digest และ builder identity จากนั้นสร้าง durable job เมื่อ state อนุญาต สถานะอยู่ใน DB ไม่หายเมื่อ restart Audit เก็บการเสนอและการขอตรวจ โดยไม่มี secret ในรายละเอียด

### `workflow.work_once()`

Worker claim งานด้วย row lock และ SKIP LOCKED ตั้ง lease/claim token แล้วปล่อย transaction ก่อนรันงานช้า หลังตรวจจะกลับมาเช็ก token อีกครั้งก่อนเขียนผล งานที่ถูก cancel หรือถูก worker ใหม่ reclaim จะไม่ถูก worker เก่าเขียน PASS ทับ หาก process crash lease หมดอายุแล้วทำซ้ำได้

ข้อจำกัด: การตรวจอาจรันซ้ำได้ จึงห้ามให้ verification ไปเขียน production การสร้าง artifact อาจเหลือ cache/container จาก failure ต้องตรวจและจัดการเฉพาะ resource ของงานนั้น

### `assurance.inspect_source()` และ `verify()`

AST allowlist จำกัดภาษาเฉพาะสอง pure functions เพื่อปิดความสามารถอ่านไฟล์/เครือข่าย/เปิด process ก่อน execute Source ต้องผ่าน scans จริงและ acceptance suite ใน Docker ที่ไม่มี network และ credentials ผลคือ evidence bundle พร้อม image ID และ HMAC ไม่ใช่คำตอบว่า “ดูแล้วปลอดภัย”

`decision()` ตรวจ required checks ครบและสถานะจริง FAIL → BLOCK; ERROR/missing → INCONCLUSIVE; ผ่านทั้งหมดจึง PASS ความหมายคือผ่าน policy เวอร์ชันนี้ ไม่ใช่พิสูจน์ว่าไม่มี bug ใดในโลก

### `scanners.source_scans()` และ `image_scan()`

Gitleaks ตรวจ secrets; Semgrep ใช้ rules ที่ commit ในโปรเจกต์; Trivy ตรวจ packages ใน image ที่จะ deploy ผ่าน image archive Scanner ไม่ได้รับ Docker socket หรือ secrets ของ control plane เก็บ tool image ID/report ไว้ ผลผิดรูป/เครื่องมือขาดเป็น ERROR ไม่ใช่ไม่มี finding

### `ai.build()`, `review()` และ `diagnose()`

Builder ได้ issue/source ที่เกี่ยวข้องและคืน structured proposal Verifier ได้ requirement/source/evidence แบบคนละ context ไม่มี Builder reasoning trace ผล model ต้องผ่าน Pydantic และ evidence refs ต้องตรงกับ check ที่มีจริง Diagnose คืน hypothesis และ uncertainty ไม่อ้างพิสูจน์ root cause หรือรันคำสั่งที่ไม่ได้รัน

โมเดลตัวเดียวกันยังอาจพลาดแบบเดียวกันได้ ความเป็นอิสระที่ทำจริงคือ context/authority/trusted tests ไม่ใช่ความเป็นอิสระทางสถิติของ models Budget จำกัด calls และเก็บ usage จริง

### `workflow.approve()` และ `check_release()`

ตรวจสถานะ, proposer != approver, HMAC, source/image digest, policy และ review ต้องตรงกัน Approval ใช้เฉพาะ artifact นี้ ไม่ย้ายไป source ใหม่ได้ หาก trusted runtime/test suite เปลี่ยนต้องตรวจใหม่

### `runtime.deploy()`

รับ approved change จาก deployer identity ใช้ image ID สร้าง container จริงแล้ว probe ก่อนเปลี่ยน ACTIVE การเขียนสถานะและ side effects ข้าม Docker/DB ไม่ใช่ transaction เดียว จึงใช้ชื่อ release คงที่เพื่อให้ retry ตรวจพบ container เดิมและไม่สร้างซ้ำ

### `runtime.measure()` / `observe()` / `monitor.tick()`

ยิงคำขอสองครั้งต่อ key เก็บเวลา/error/duplicate แล้วเปรียบเทียบ policy Runtime monitor ทำซ้ำตามช่วงเวลา หากผิดให้สร้าง incident และ recover ไป standby หรือ restart approved image ก่อนวัดซ้ำ การหยุด container ทดสอบเกิดเฉพาะ target ที่บันทึกใน deployment record

ค่า p95 ในชุดนี้คือเวลาของ replay scenario สอง requests ไม่ใช่ single-request latency และไม่ใช่ user traffic จริง ต้องอ่าน provenance/sample count ด้วย

### `scripts/backup.py` และ `evaluate_data.py`

Backup ใช้ pg_dump แล้ว pg_restore ลง DB ชั่วคราวคนละชื่อ ไม่ทับ live DB ส่วน dataset script โหลดข้อมูล UCI จริง บันทึก checksum/license/transform และ replay ผ่าน financial kernel การ map GBP numerical amount ไป THB sandbox units ไม่ใช่อัตราแลกเปลี่ยนจริงและมีป้ายกำกับชัด

## สิ่งที่ให้คุณทดลองเองเมื่อเริ่มสอน

แต่ละรอบเลือกเพียงหนึ่งเรื่อง: เปลี่ยน amount แต่ใช้ key เดิม, ทำ scanner ให้ unavailable, ลอง approve ด้วย builder token, เปลี่ยน artifact หลังตรวจ, stop target, restore backup จากนั้นทายผล → รัน → อ่าน evidence → อธิบายว่าจุดไหนบังคับกฎ ไม่ต้องพิมพ์ implementation ตามทั้งหมด

## วิธีวัดความเข้าใจ

คุณควรอธิบาย input/output, จุดเปลี่ยนข้อมูล, ผู้มีสิทธิ์, failure boundary และ test ที่พิสูจน์กฎสำคัญได้ การจำ syntax ทุกบรรทัดไม่ใช่เป้าหมาย ใช้ [roadmap](LEARNING-ROADMAP.md) เมื่อต้องการเจาะหัวข้อเพิ่ม
