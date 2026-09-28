# M00–M01 — จากไฟล์โค้ดสู่ Payment API ที่เรียกได้จริง

## สถานะ

- Engineering: รันทดสอบผ่านสำหรับขอบเขต M00–M01
- Learning: อธิบายผ่านเอกสารแล้ว; รอผู้ใช้ทดลองและ teach-back
- Evidence run: local run วันที่ 21 กันยายน 2026; ยังไม่มี Git commit
- Prerequisites: Python 3.13, `uv`; Docker ยังไม่ต้องใช้ในบทนี้

## ปัญหาและผลที่ต้องได้

เราต้องการรับคำขอชำระเงินที่มี tenant, บัญชีต้นทาง/ปลายทาง, จำนวนเงินและสกุลเงิน ข้อมูลผิดต้องถูกปฏิเสธก่อนเกิดผลด้านการเงิน รุ่นนี้ยังไม่บันทึกฐานข้อมูล จึงยังไม่ได้โอนเงินจริง สร้าง fee หรือทำ idempotency

ตัวอย่างที่ผ่าน:

```json
{
  "tenant_id": "tenant-demo",
  "source_account_id": "account-alice",
  "destination_account_id": "account-bob",
  "amount": "125.50",
  "currency": "THB"
}
```

ส่งพร้อม header `Idempotency-Key: payment-demo-001` แล้วได้ HTTP 201 และสถานะ `accepted` จำนวนเงินใช้ string เพื่อรักษาค่า decimal จาก JSON ให้ชัดเจน

## ตำแหน่งในระบบ

```text
HTTP client
  → FastAPI route: post_payment()
  → Pydantic: PaymentRequest
  → PaymentCommand
  → domain: create_payment()
  → PaymentResponse
  → HTTP 201 / JSON
```

เส้นแบ่งสำคัญมีสองชั้น:

1. **Transport validation:** รูปร่าง JSON, ความยาวข้อความ, amount มากกว่า 0 และ header ที่ต้องมี อยู่ใน `schemas.py` และ FastAPI
2. **Domain validation:** กฎที่ต้องจริงไม่ว่าจะเรียกจาก HTTP, job หรือ event เช่น ห้ามบัญชีต้นทางเท่าปลายทาง อยู่ใน `payments.py`

## พื้นฐานที่ต้องรู้รอบนี้

- **File:** โค้ดที่เก็บบนดิสก์ ยังไม่ทำงานด้วยตัวเอง
- **Process:** โปรแกรมที่ Python โหลดไฟล์แล้วกำลังทำงาน เช่น Uvicorn
- **Dependency:** library ภายนอก เช่น FastAPI และ Pydantic ถูกล็อกเวอร์ชันใน `uv.lock`
- **Virtual environment (`.venv`):** พื้นที่ dependencies ของโปรเจกต์ แยกจาก Python ระบบ
- **HTTP 201:** server รับและสร้าง representation สำเร็จในขอบเขต API นี้ ไม่ได้พิสูจน์ว่าเงินถูกบันทึกหรือ ledger ถูกต้อง
- **HTTP 422:** ข้อมูลมีรูปแบบหรือเงื่อนไขที่ API/domain ไม่ยอมรับ
- **JSON:** รูปแบบส่งข้อมูลผ่าน HTTP
- **Decimal:** ชนิดจำนวนที่เหมาะกับกฎความแม่นยำของเงินมากกว่า binary floating point แต่ยังต้องกำหนด rounding และ minor units ใน M02

## อ่านโค้ดตามลำดับ

| ฟังก์ชัน/ไฟล์ | หน้าที่และ caller | Input/output | Side effects / dependencies |
| --- | --- | --- | --- |
| `PaymentRequest` ใน `src/veriforge/api/schemas.py` | FastAPI สร้างจาก JSON | JSON → typed request หรือ 422 | ไม่มีผลการเงิน |
| `post_payment()` ใน `src/veriforge/api/app.py` | HTTP `POST /payments` | request + header → response | ตอนนี้ไม่มี DB; เรียก domain function |
| `create_payment()` ใน `src/veriforge/domain/payments.py` | route เรียกด้วย command | command → immutable Payment หรือ error | สร้าง UUID ในหน่วยความจำเท่านั้น |
| Tests ใน `tests/test_api.py` | pytest เรียก API in-process | requests → assertions | ไม่มี network/database |
| Tests ใน `tests/test_payments.py` | pytest เรียก domain โดยตรง | commands → result/error | ไม่มี network/database |

## ฟังก์ชันสำคัญ: `create_payment()`

- **Purpose:** บังคับกฎของ payment ที่ไม่ควรผูกกับ HTTP
- **Caller:** ตอนนี้คือ `post_payment()`; ในอนาคตอาจมี worker เรียก
- **Input:** `PaymentCommand` ที่ประกอบด้วย identity ของ tenant/accounts, amount, currency และ idempotency key
- **Output:** `Payment` สถานะ accepted หรือ `InvalidPayment`
- **Dependencies:** Python `Decimal` และ UUID; ยังไม่มี database
- **Side effects:** สร้าง UUID แบบสุ่มใน memory ไม่มี financial posting
- **Invariants:** amount ต้องมากกว่า 0, currency รองรับ, บัญชีต้นทางกับปลายทางต้องต่างกัน
- **Identity:** ยังไม่มี authentication/authorization จึงยังเปิด pilot ไม่ได้
- **Concurrency:** ยังไม่มี shared state; key เดิมจะสร้าง UUID ใหม่ทุกครั้ง นี่เป็นช่องว่างตั้งใจสำหรับ M02–M03
- **Failure:** validation fail แล้วไม่มี state ค้าง เพราะยังไม่ persist
- **Evidence:** domain tests และ API behavior tests รวม 7 รายการ
- **Trade-off:** โครงเล็กและอ่านง่าย แต่ยังไม่ทำเงินจริง, transaction, fee หรือ idempotency

## ทดลองปกติที่รันแล้ว

```bash
.venv/bin/pytest -q
```

ผลจริง: `7 passed` มี 2 deprecation warnings จาก FastAPI/Starlette TestClient dependencies ไม่ใช่ test failures และต้องติดตามเมื่ออัปเกรด dependencies

รัน process จริงด้วย:

```bash
.venv/bin/uvicorn --app-dir src veriforge.api.app:app --host 127.0.0.1 --port 8123
```

ผล HTTP ที่สังเกตจริง:

- `GET /health` → 200 `{"status":"ok"}`
- valid `POST /payments` → 201 และ amount `125.50`, currency `THB`, status `accepted`
- amount `-1.00` → 422 พร้อม validation detail

Server ถูกปิดหลังตรวจเสร็จ

## ทดลองให้พังอย่างปลอดภัย

การทดสอบครั้งแรกพบ `ModuleNotFoundError: veriforge` เพราะ source อยู่ใน `src/` แต่ test process ยังไม่ได้รับ source path แก้โดยกำหนด `pythonpath = ["src"]` ใน `pyproject.toml` แล้วรันใหม่ผ่าน นี่พิสูจน์ว่า file มีอยู่ไม่เท่ากับ Python process import พบ

การเปิด localhost ใน filesystem sandbox ถูกปฏิเสธด้วย `operation not permitted` จึงเปิด Uvicorn โดยขอสิทธิ์เฉพาะ localhost ชั่วคราว แล้วปิดหลังตรวจ HTTP สำเร็จ

## สิ่งที่ผลนี้ยังไม่พิสูจน์

- ไม่มี PostgreSQL, database transaction, ledger หรือ fee
- header idempotency ถูกตรวจว่ามี แต่ยังไม่ถูกบังคับให้ retry ได้ผลเดิม
- ยังไม่มี authentication, authorization, audit trail หรือ evidence bundle
- tests แบบ in-process ไม่แทน production networking และ local HTTP run ไม่แทน deployment
- health endpoint ตรวจเพียง process ตอบได้ ยังไม่ตรวจ dependencies

## แบบฝึกเล็กหนึ่งข้อ

ก่อนเราสร้าง M03 ลองตอบ: หากส่ง `Idempotency-Key` เดิมสองครั้ง แต่ครั้งที่สองเปลี่ยน amount จาก `125.50` เป็น `999.00` ระบบควรคืนผลเดิม รับคำขอใหม่ หรือปฏิเสธ? เพราะอะไร?

ตอนนี้โค้ดยังสร้าง payment ใหม่ทั้งสองครั้ง แบบฝึกนี้ใช้กำหนด contract ที่เราจะ implement และทดสอบจริงภายหลัง

## Teach-back

1. `PaymentRequest` กับ `PaymentCommand` มีหน้าที่ต่างกันอย่างไร?
2. ทำไม HTTP 201 ในรุ่นนี้ยังไม่พิสูจน์ว่าเงินถูกต้อง?
3. ถ้าต้องเพิ่มกฎ “THB ต้องไม่มีทศนิยมเกิน 2 ตำแหน่ง” ควรวางกฎตรงไหนเพื่อให้ HTTP และ worker ใช้กฎเดียวกัน?

## จุดต่อ

เริ่ม M02: เปิด Docker Desktop, เพิ่ม PostgreSQL ด้วย Compose, ออกแบบ account/payment/ledger schema และสร้าง transaction แรกที่มี debit/credit สมดุล จากนั้นจึงสร้าง duplicate-fee reproducer ใน M03
