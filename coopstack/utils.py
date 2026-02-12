import os
import io
from django.conf import settings
from docxtpl import DocxTemplate
from datetime import datetime

# ฟังก์ชันแปลงเดือนเป็นภาษาไทย
def format_thai_date(date_obj):
    if not date_obj: return ""
    months = [
        "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
    ]
    year = date_obj.year + 543
    return f"{date_obj.day} {months[date_obj.month-1]} {year}"

def generate_coop_docx(job_application):
    """
    สร้างไฟล์ Word (.docx) จาก Template โดยใช้ docxtpl
    """
    # 1. ระบุตำแหน่งไฟล์ Template
    template_path = os.path.join(settings.BASE_DIR, 'static', 'forms', 'form_template.docx')
    
    # 2. โหลด Template
    doc = DocxTemplate(template_path)
    
    student = job_application.student
    user = student.user
    
    # 3. เตรียมข้อมูล (Context) ให้ตรงกับ Tag {{ }} ใน Word
    context = {
        'date': format_thai_date(datetime.now()), # วันที่ปัจจุบัน
        'full_name': f"{user.first_name} {user.last_name}",
        'student_id': student.student_code,
        'year': "4", # หรือคำนวณจากรหัส นศ.
        'phone': student.phone or "-",
        
        # ข้อมูลบริษัท
        'company_name': job_application.company,
        'company_address': job_application.company.address or "-",
        'company_phone': job_application.supervisor_phone or "-",
        'contact_person': job_application.supervisor_name or "-",
        'internship_period': "1 มิ.ย. 67 - 30 ก.ย. 67", # ดึงจาก field จริงถ้ามี
        
        # ข้อมูลติดต่อ นศ.
        'student_address': job_application.accommodation or "-",
        'email': user.email or "-",
        
        # ผู้ติดต่อฉุกเฉิน (สมมติว่ามี field นี้ใน model)
        'emergency_name': getattr(job_application, 'emergency_contact', "-"), 
        'emergency_phone': getattr(job_application, 'emergency_phone', "-"),
    }
    
    # 4. Render ข้อมูลลงใน Template
    doc.render(context)
    
    # 5. บันทึกลง Memory Buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer