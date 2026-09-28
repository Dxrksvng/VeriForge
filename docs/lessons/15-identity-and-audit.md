# M15 — Identity lifecycle และ tamper-evident audit

สถานะ engineering: complete. สถานะ learning: not started.

เส้นทางจริงเริ่มที่ bootstrap secret ซึ่งใช้ได้เฉพาะ `POST /api/session` ใน `api/app.py` แล้ว `identity.py` ออก session ที่เซ็น HMAC พร้อม `iss`, `aud`, `sub`, `role`, `tenant`, `iat`, `exp`, `jti` โดยเก็บเฉพาะ SHA-256 ของ jti ใน PostgreSQL การเรียก API ทุกครั้งต้องผ่านทั้ง signature/claims และ registry; logout ตั้ง `revoked_at` ทำให้ replay ไม่ได้

Audit event ทุกแถวมี `prev_hash` และ `event_hash` ซึ่ง HMAC ครอบคลุม id, actor, action, resource, details, timestamp และ hash ก่อนหน้า การ insert ใช้ PostgreSQL advisory lock เพื่อรักษาลำดับเมื่อเขียนพร้อมกัน ตารางปฏิเสธ UPDATE/DELETE และ endpoint `/api/audit/integrity` คำนวณ chain ใหม่เพื่อตรวจความผิดปกติ

สิ่งที่ต้องเข้าใจภายหลัง: authentication ต่างจาก authorization, bootstrap ต่างจาก session, stateless signature ต่างจาก server-side revocation, hash chain ตรวจการเปลี่ยนย้อนหลังอย่างไร และเหตุใด local administrator ที่ถือทั้งฐานข้อมูลกับ signing key ยังอยู่นอก threat model นี้

หลักฐาน: `tests/test_api.py`, `artifacts/control-plane-load.json`, browser journey และผล `/api/audit/integrity` จริง ห้ามสรุปว่าเป็น OIDC, hardware-backed key หรือ external transparency log
