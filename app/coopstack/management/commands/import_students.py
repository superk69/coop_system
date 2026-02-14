import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from coopstack.models import AllowedStudent 

class Command(BaseCommand):
    help = 'Import data from Dataname.csv to AllowedStudent model'

    def handle(self, *args, **kwargs):
        # ระบุตำแหน่งไฟล์ CSV (สมมติว่าอยู่ที่ Root ของโปรเจกต์)
        file_path = os.path.join(settings.BASE_DIR, 'Dataname.csv')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'ไม่พบไฟล์: {file_path}'))
            return

        # รายการคำนำหน้าที่ต้องการตรวจสอบเพื่อแยกออกจากชื่อ
        prefixes = ['นาย', 'นางสาว', 'นาง', 'ว่าที่ร้อยตรี', 'ดร.', 'ผศ.', 'รศ.']

        count_created = 0
        count_updated = 0

        self.stdout.write("กำลังเริ่มนำเข้าข้อมูล...")

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    student_code = row['ID'].strip()
                    full_name_str = row['Name'].strip()

                    # 1. แยก นามสกุล ออกจาก ชื่อรวมคำนำหน้า (แยกด้วยช่องว่าง)
                    parts = full_name_str.split(maxsplit=1)
                    name_with_title = parts[0]  # เช่น "นายสมชาย"
                    lastname = parts[1] if len(parts) > 1 else "" # เช่น "ใจดี"

                    # 2. แยก คำนำหน้า ออกจาก ชื่อจริง
                    title = ""
                    firstname = name_with_title

                    for prefix in prefixes:
                        if name_with_title.startswith(prefix):
                            title = prefix
                            # ตัดคำนำหน้าออก เหลือแค่ชื่อ
                            firstname = name_with_title[len(prefix):] 
                            break
                    
                    # 3. บันทึกลง Database
                    # ใช้ update_or_create เพื่อป้องกันข้อมูลซ้ำ (เช็คจาก student_code)
                    obj, created = AllowedStudent.objects.update_or_create(
                        student_code=student_code,
                        defaults={
                            'title': title,
                            'firstname': firstname,
                            'lastname': lastname,
                            # ใส่ค่า Default สาขาไว้ก่อน (เนื่องจากใน CSV ไม่มี)
                            'major': "วิทยาการข้อมูลและนวัตกรรมซอฟต์แวร์", 
                        }
                    )

                    if created:
                        count_created += 1
                    else:
                        count_updated += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error row {row.get('ID')}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f'เสร็จสิ้น! สร้างใหม่: {count_created} คน, อัปเดต: {count_updated} คน'
        ))