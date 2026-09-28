# Mxx — ชื่อบทเรียน

> Template เท่านั้น ยังไม่มี implementation หรือผลทดสอบในเอกสารนี้ ให้สร้างไฟล์บทเรียนแยกเมื่อมีโค้ดจริง

## สถานะ

- Engineering: ยังไม่เริ่ม
- Learning: ยังไม่สอน
- Code revision / evidence run: ยังไม่มี
- Prerequisites:

## ปัญหาและผลที่ต้องได้

เล่าสถานการณ์หนึ่งอย่าง พร้อมพฤติกรรมก่อน/หลังและเงื่อนไขที่ห้ามละเมิด

## ตำแหน่งในระบบ

วาด flow สั้นจาก caller → function → storage/dependency → response และชี้ trust/transaction boundary

## พื้นฐานที่ต้องรู้รอบนี้

อธิบายคำศัพท์ใหม่ไม่เกินที่จำเป็นกับปัญหา พร้อมตัวอย่าง input/output

## อ่านโค้ดตามลำดับ

ลิงก์ไฟล์จริงตาม execution order ไม่ใช้รายการไฟล์ยาวโดยไม่มีความสัมพันธ์

| ฟังก์ชัน/ตำแหน่ง | หน้าที่และ caller | Input/output | Side effects / dependencies |
| --- | --- | --- | --- |
| รอ implementation | — | — | — |

สำหรับฟังก์ชันสำคัญ อธิบาย invariants, permissions, concurrency, failure modes, evidence/tests และ trade-offs เพิ่มตาม agreement

## ทดลองปกติ

- Prerequisites และ command ที่ตรวจแล้ว:
- Input:
- Expected behavior:
- Actual observed output / evidence:

ห้ามใส่คำสั่งสมมติว่าใช้ได้แล้ว ระบุ “ยังไม่ได้รัน” หากยังไม่ตรวจ

## ทดลองให้พังอย่างปลอดภัย

- Environment และขอบเขต fault:
- ให้ผู้ใช้ทายผล:
- วิธี inject:
- ผลจริงและเหตุผล:
- วิธีคืนสภาพ:

## วิธีแก้และพิสูจน์

- Root cause และขอบเขตที่ยังไม่ทราบ:
- ทางแก้และเหตุผล:
- Tests/commands ที่รัน:
- ผลก่อน/หลัง:
- สิ่งที่ผลนี้ยังไม่พิสูจน์:

## แบบฝึกเล็กหนึ่งข้อ

เปลี่ยน behavior/test จุดเดียว ใช้เวลาสั้น และไม่บล็อก development ถ้าผู้ใช้ยังไม่ทำ

## Teach-back

1. อธิบายว่าข้อมูลเดินทางอย่างไร
2. ถ้าหยุดกลางทางจะเกิดอะไร
3. Test ไหนพิสูจน์กฎสำคัญ และยังขาดอะไร

## บันทึกการเรียนและจุดต่อ

- ผู้ใช้ได้ทดลอง/อธิบายอะไรจริง:
- ยังไม่ตอบ/ต้องทบทวน:
- Next action:
