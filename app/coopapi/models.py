# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# ==========================================
# 1. Custom User Model
# ==========================================

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'นักศึกษา'
        TEACHER = 'TEACHER', 'อาจารย์'
        COMPANY = 'COMPANY', 'ตัวแทนบริษัท'

    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.STUDENT,
        verbose_name="บทบาท"
    )
    # email มีอยู่แล้วใน AbstractUser แต่เราสามารถบังคับให้ Unique ได้หากต้องการ
    email = models.EmailField(unique=True, verbose_name="อีเมล")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

# ==========================================
# 2. Company Knowledge Base (Master Data)
# ==========================================

class CompanyMaster(models.Model):
    """ฐานข้อมูลบริษัทกลาง (Knowledge Base)"""
    company_name = models.CharField(max_length=200, verbose_name="ชื่อบริษัท")
    address = models.TextField(blank=True, null=True, verbose_name="ที่อยู่หลัก")
    contact_person = models.CharField(max_length=100, blank=True, null=True, verbose_name="ผู้ติดต่อหลัก/HR")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="เบอร์โทรศัพท์")
    
    # FR-19: อาจารย์บันทึกความเห็นเกี่ยวกับบริษัท
    teacher_comments = models.TextField(blank=True, null=True, verbose_name="ความคิดเห็นอาจารย์")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name

# ==========================================
# 3. User Profiles
# ==========================================

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    student_code = models.CharField(max_length=20, unique=True, verbose_name="รหัสนักศึกษา")
    major = models.CharField(max_length=100, verbose_name="สาขาวิชา")

    def __str__(self):
        return f"{self.student_code} - {self.firstname} {self.lastname}"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)

    def __str__(self):
        return f"อ.{self.firstname} {self.lastname}"

class CompanyRepresentative(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')
    # ผูกกับบริษัทในฐานข้อมูลกลาง
    company = models.ForeignKey(CompanyMaster, on_delete=models.CASCADE, related_name='representatives')
    # ชื่อบริษัท ณ ตอนสมัคร (เผื่อ Master เปลี่ยนชื่อ แต่ปกติใช้ FK ก็พอ)
    display_company_name = models.CharField(max_length=200, blank=True, null=True) 
    created_by_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.company.company_name}"

# ==========================================
# 4. Training Module
# ==========================================

class TrainingRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'รอตรวจสอบ'
        APPROVED = 'APPROVED', 'อนุมัติ'
        REJECTED = 'REJECTED', 'ปฏิเสธ'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='training_records')
    topic_name = models.CharField(max_length=200, verbose_name="หัวข้อการอบรม")
    proof_file = models.FileField(upload_to='training_proofs/', verbose_name="ไฟล์หลักฐาน")
    
    requested_hours = models.IntegerField(verbose_name="ชั่วโมงที่ขอ")
    approved_hours = models.IntegerField(default=0, verbose_name="ชั่วโมงที่อนุมัติ")
    
    teacher_note = models.TextField(blank=True, null=True, verbose_name="หมายเหตุจากอาจารย์")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.topic_name} ({self.student.firstname})"

# ==========================================
# 5. Job Application Module (Snapshot Data)
# ==========================================

class JobApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'รออนุมัติ'
        APPROVED = 'APPROVED', 'อนุมัติ (กำลังฝึกงาน)'
        REJECTED = 'REJECTED', 'ปฏิเสธ'
        CANCELLED = 'CANCELLED', 'ยกเลิก'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='job_applications')
    # เชื่อมโยงกับ Knowledge Base
    company = models.ForeignKey(CompanyMaster, on_delete=models.SET_NULL, null=True, related_name='job_history')
    
    # Snapshot Data (ข้อมูลจำเพาะของการฝึกครั้งนี้ อาจต่างจาก Master)
    company_name_snapshot = models.CharField(max_length=200, verbose_name="ชื่อบริษัท (ขณะสมัคร)")
    position = models.CharField(max_length=100, verbose_name="ตำแหน่งงาน")
    company_location = models.TextField(verbose_name="ที่ตั้งสถานประกอบการ")
    
    supervisor_name = models.CharField(max_length=100, verbose_name="ชื่อผู้ดูแล")
    supervisor_phone = models.CharField(max_length=20, verbose_name="เบอร์โทรผู้ดูแล")
    
    accommodation = models.TextField(blank=True, null=True, verbose_name="ที่พักระหว่างฝึก")
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="ผู้ติดต่อฉุกเฉิน")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="เบอร์โทรฉุกเฉิน")

    # Tracking info
    academic_year = models.CharField(max_length=4, default="2566", verbose_name="ปีการศึกษา")
    semester = models.CharField(max_length=1, default="1", verbose_name="ภาคเรียน")

    start_date = models.DateField(verbose_name="วันเริ่มฝึกงาน")
    end_date = models.DateField(verbose_name="วันสิ้นสุดฝึกงาน")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    teacher_note = models.TextField(blank=True, null=True, verbose_name="เหตุผลการปฏิเสธ")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.firstname} -> {self.company_name_snapshot}"

# ==========================================
# 6. Weekly Report Module
# ==========================================

class WeeklyReport(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'ส่งแล้ว'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'อาจารย์รับทราบ'

    # ผูกกับ Job Application (เพื่อให้รู้ว่ารายงานของงานไหน หากมีการยกเลิกสมัครใหม่)
    job_application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='reports')
    week_number = models.IntegerField(verbose_name="สัปดาห์ที่")
    
    # 4 หัวข้อรายงาน
    work_summary = models.TextField(verbose_name="สรุปงานที่ปฏิบัติ")
    problems_found = models.TextField(blank=True, null=True, verbose_name="ปัญหาที่พบ")
    knowledge_gained = models.TextField(blank=True, null=True, verbose_name="สิ่งที่ได้เรียนรู้")
    supervisor_feedback = models.TextField(blank=True, null=True, verbose_name="ข้อเสนอแนะจากพี่เลี้ยง")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['week_number']
        unique_together = ('job_application', 'week_number')

# ==========================================
# 7. Evaluation Module (JSON & Detailed)
# ==========================================

class Evaluation(models.Model):
    class TeacherAckStatus(models.TextChoices):
        UNREAD = 'UNREAD', 'ยังไม่ตรวจสอบ'
        READ = 'READ', 'ตรวจสอบแล้ว'

    job_application = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name='evaluation')
    evaluator = models.ForeignKey(CompanyRepresentative, on_delete=models.SET_NULL, null=True, related_name='evaluations')
    
    total_score = models.IntegerField(verbose_name="คะแนนรวม")
    
    # เก็บข้อมูลคะแนนรายข้อแบบ JSON { "q11": 5, "q12": 4, ... }
    # รองรับการปรับเปลี่ยนฟอร์มประเมินในอนาคตได้ง่าย
    evaluation_data = models.JSONField(default=dict, verbose_name="ข้อมูลประเมินละเอียด")
    
    strengths = models.TextField(blank=True, null=True, verbose_name="จุดเด่น")
    weaknesses = models.TextField(blank=True, null=True, verbose_name="ข้อควรปรับปรุง")
    comments = models.TextField(blank=True, null=True, verbose_name="ความคิดเห็นเพิ่มเติม")
    
    teacher_ack_status = models.CharField(
        max_length=10, 
        choices=TeacherAckStatus.choices, 
        default=TeacherAckStatus.UNREAD
    )
    evaluated_at = models.DateTimeField(auto_now=True)

# ==========================================
# 8. Announcements & Documents
# ==========================================
class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    attachment = models.FileField(upload_to='announcements/', null=True, blank=True)
    is_published = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False) # ปักหมุดข่าวสำคัญ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Document(models.Model):
    file_name = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)