from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
import os
import uuid
import datetime

# ==========================================
# 0. Helper Functions (จัดการไฟล์อัปโหลด)
# ==========================================

def training_proof_path(instance, filename):
    # e.g. uploads/student_6601001/training/cert.pdf
    return f'uploads/student_{instance.student.student_code}/training/{filename}'

def announcement_file_path(instance, filename):
    return f'uploads/announcements/{filename}'


# ==========================================
# 1. Custom User Model (จัดการสิทธิ์)
# ==========================================

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'ผู้ดูแลระบบ'
        TEACHER = 'TEACHER', 'อาจารย์นิเทศ'
        STUDENT = 'STUDENT', 'นักศึกษา'
        COMPANY = 'COMPANY', 'พี่เลี้ยง/สถานประกอบการ'

    role = models.CharField(
        max_length=10, 
        choices=Role.choices, 
        default=Role.STUDENT,
        verbose_name="สิทธิ์ผู้ใช้งาน"
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    

class AllowedStudent(models.Model):
    student_code = models.CharField(max_length=20, unique=True, verbose_name="รหัสนักศึกษา")
    title = models.CharField(max_length=20, blank=True, verbose_name="คำนำหน้า") # นาย/นางสาว
    firstname = models.CharField(max_length=100, verbose_name="ชื่อจริง")
    lastname = models.CharField(max_length=100, verbose_name="นามสกุล")
    major = models.CharField(max_length=100, verbose_name="สาขาวิชา")
    
    # เช็คว่าลงทะเบียนไปแล้วหรือยัง (Optional)
    is_registered = models.BooleanField(default=False, verbose_name="ลงทะเบียนแล้ว")

    def __str__(self):
        return f"{self.student_code} - {self.first_name} {self.last_name}"


# ==========================================
# 2. Master Data (ข้อมูลหลัก)
# ==========================================

class CompanyMaster(models.Model):
    """ ฐานข้อมูลรายชื่อสถานประกอบการ """
    name = models.CharField(max_length=255, verbose_name="ชื่อบริษัท")
    address = models.TextField(verbose_name="ที่อยู่", blank=True)
    contact_person = models.CharField(max_length=100, verbose_name="ผู้ติดต่อหลัก", blank=True)
    phone = models.CharField(max_length=20, verbose_name="เบอร์โทรศัพท์", blank=True)
    email = models.EmailField(verbose_name="อีเมลบริษัท", blank=True)
    website = models.URLField(verbose_name="เว็บไซต์", blank=True)
    
    # Note ส่วนตัวของอาจารย์ (นักศึกษาไม่เห็น)
    teacher_notes = models.TextField(verbose_name="บันทึกช่วยจำของอาจารย์", blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ข้อมูลบริษัท (Master)"
        verbose_name_plural = "ข้อมูลบริษัท (Master)"

    def __str__(self):
        return self.name


def announcement_file_path(instance, filename):
    """ Generate path: uploads/announcements/UUID_filename """
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('uploads/announcements/', filename)


class Announcement(models.Model):
    """ ประกาศข่าวสาร """
    title = models.CharField(max_length=200, verbose_name="หัวข้อประกาศ")
    content = models.TextField(verbose_name="เนื้อหา")
    attachment = models.FileField(upload_to=announcement_file_path, null=True, blank=True, verbose_name="ไฟล์แนบ")
    is_published = models.BooleanField(default=True, verbose_name="เผยแพร่ทันที")
    is_pinned = models.BooleanField(default=False, verbose_name="ปักหมุดข่าวสำคัญ")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "ประกาศข่าวสาร"
        verbose_name_plural = "ประกาศข่าวสาร"

    def __str__(self):
        return self.title

    @property
    def extension(self):
        if self.attachment:
            name, extension = os.path.splitext(self.attachment.name)
            return extension.lower()
        return ""

    @property
    def filename(self):
        if self.attachment:
            return os.path.basename(self.attachment.name)
        return ""


# ==========================================
# 3. User Profiles (ข้อมูลส่วนตัวตามบทบาท)
# ==========================================

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_code = models.CharField(max_length=20, unique=True, verbose_name="รหัสนักศึกษา")
    firstname = models.CharField(max_length=100, verbose_name="ชื่อจริง")
    lastname = models.CharField(max_length=100, verbose_name="นามสกุล")
    major = models.CharField(max_length=100, verbose_name="สาขาวิชา")
    gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name="เกรดเฉลี่ย")
    phone = models.CharField(max_length=20, blank=True, verbose_name="เบอร์โทรศัพท์")
    
    class Meta:
        verbose_name = "ข้อมูลนักศึกษา"
        verbose_name_plural = "ข้อมูลนักศึกษา"

    def __str__(self):
        return f"{self.student_code} - {self.firstname} {self.lastname}"


def current_academic_year():
    now = datetime.datetime.now()
    thai_year = now.year + 543
    if now.month >= 5:
        return thai_year
    return thai_year - 1

class CompanyProfile(models.Model):
    """ บัญชีผู้ใช้สำหรับพี่เลี้ยง (ผูกกับ CompanyMaster) """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')
    company = models.ForeignKey(CompanyMaster, on_delete=models.CASCADE, related_name='staffs', verbose_name="สังกัดบริษัท")
    position = models.CharField(max_length=100, verbose_name="ตำแหน่งงาน", blank=True)
    phone = models.CharField(max_length=20, verbose_name="เบอร์โทรศัพท์ส่วนตัว", blank=True)
    academic_year = models.IntegerField(verbose_name="ปีการศึกษา", default=current_academic_year)
    #created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ข้อมูลพี่เลี้ยง (User)"
        verbose_name_plural = "ข้อมูลพี่เลี้ยง (User)"
        unique_together = ('company', 'academic_year')
        #ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.company.name} ({self.academic_year})"
    
# ==========================================
# 4. Training System (การเตรียมความพร้อม)
# ==========================================

class TrainingRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'รอตรวจสอบ'
        APPROVED = 'APPROVED', 'ผ่าน'
        REJECTED = 'REJECTED', 'ไม่ผ่าน (แก้ไข)'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='trainings')
    topic = models.CharField(max_length=200, verbose_name="หัวข้อการอบรม")
    date = models.DateField(verbose_name="วันที่อบรม")
    hours = models.IntegerField(verbose_name="จำนวนชั่วโมงที่เคลม")
    get_hours = models.PositiveIntegerField(default=0, verbose_name="จำนวนชั่วโมงที่ได้รับจริง")
    proof_file = models.FileField(upload_to=training_proof_path, verbose_name="หลักฐาน (Cert/รูปภาพ)")
    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name="สถานะ")
    teacher_comment = models.TextField(blank=True, verbose_name="ความเห็นอาจารย์")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ประวัติการอบรม"
        verbose_name_plural = "ประวัติการอบรม"

    def __str__(self):
        return f"{self.topic} (ขอ {self.hours} -> ได้ {self.get_hours})"

# ==========================================
# 5. Internship Process (การฝึกงาน)
# ==========================================

class JobApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'รออนุมัติ'
        APPROVED = 'APPROVED', 'กำลังฝึกงาน'
        REJECTED = 'REJECTED', 'ไม่อนุมัติ'
        COMPLETED = 'COMPLETED', 'ฝึกงานเสร็จสิ้น'
        CANCELLED = 'CANCELLED', 'ยกเลิกโดยนักศึกษา'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='job_applications')
    company = models.ForeignKey(CompanyMaster, on_delete=models.PROTECT, related_name='job_applications', verbose_name="บริษัท")
    
    position = models.CharField(max_length=100, verbose_name="ตำแหน่งที่ฝึก")
    location = models.TextField(
        verbose_name="ที่ตั้งสถานประกอบการ (สถานที่จริง)", 
        blank=True,
        help_text="ระบุที่อยู่สถานที่ทำงานจริง หากแตกต่างจากที่อยู่บริษัทหลัก"
    )
    
    start_date = models.DateField(verbose_name="วันเริ่มฝึกงาน")
    end_date = models.DateField(verbose_name="วันสิ้นสุดฝึกงาน")
    academic_year = models.IntegerField(verbose_name="ปีการศึกษา", blank=True, null=True)
    
    # --- ส่วนข้อมูลพี่เลี้ยงหน้างาน ---
    supervisor_name = models.CharField(max_length=100, verbose_name="ชื่อพี่เลี้ยง (หน้างาน)")
    supervisor_email = models.EmailField(blank=True, verbose_name="อีเมลพี่เลี้ยง")
    supervisor_phone = models.CharField(max_length=20, blank=True, verbose_name="เบอร์โทรพี่เลี้ยง")

    # --- ส่วนข้อมูลเพิ่มเติม (อัปเดตใหม่ตาม HTML) ---
    accommodation = models.TextField(verbose_name="ที่พักระหว่างฝึกงาน", blank=True, help_text="ระบุที่อยู่หอพักหรือบ้านพัก")
    emergency_contact = models.CharField(max_length=100, verbose_name="ชื่อผู้ติดต่อฉุกเฉิน", blank=True)
    emergency_phone = models.CharField(max_length=20, verbose_name="เบอร์โทรฉุกเฉิน", blank=True)

    # --- สถานะ ---
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name="สถานะ")
    teacher_note = models.TextField(blank=True, verbose_name="หมายเหตุจากอาจารย์")
    cancel_reason = models.TextField(verbose_name="เหตุผลการยกเลิก", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ใบสมัครงาน/การฝึกงาน"
        verbose_name_plural = "ใบสมัครงาน/การฝึกงาน"

    def save(self, *args, **kwargs):
        # Logic คำนวณปีการศึกษาอัตโนมัติก่อนบันทึก
        if self.start_date:
            year_ad = self.start_date.year
            month = self.start_date.month

            if month < 5:
                academic_year_ad = year_ad - 1
            else:
                academic_year_ad = year_ad
            
            # แปลงเป็น พ.ศ.
            self.academic_year = academic_year_ad + 543

        super(JobApplication, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.student_code} @ {self.company.name}"


class WeeklyReport(models.Model):
    """ รายงานประจำสัปดาห์ """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'รอตรวจ'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'ตรวจแล้ว'

    job_application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='reports')
    week_number = models.IntegerField(verbose_name="สัปดาห์ที่")
    
    work_summary = models.TextField(verbose_name="สรุปงานที่ปฏิบัติ")
    problems = models.TextField(verbose_name="ปัญหาและอุปสรรค", blank=True)
    knowledge_gained = models.TextField(verbose_name="สิ่งที่ได้เรียนรู้", blank=True)
    supervisor_feedback = models.TextField(verbose_name="ข้อเสนอแนะจากพี่เลี้ยง", blank=True)
    
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, verbose_name="สถานะการตรวจ")
    teacher_comment = models.TextField(blank=True, verbose_name="ความเห็นอาจารย์")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['week_number']
        unique_together = ('job_application', 'week_number') # ห้ามส่ง week ซ้ำใน job เดิม
        verbose_name = "รายงานประจำสัปดาห์"
        verbose_name_plural = "รายงานประจำสัปดาห์"

    def __str__(self):
        return f"Week {self.week_number} - {self.job_application.student.firstname}"


class Evaluation(models.Model):
    job_application = models.OneToOneField(
        'JobApplication', 
        on_delete=models.CASCADE, 
        related_name='evaluation'
    )
    
    # ข้อมูลคะแนน (15 ข้อ) - เก็บแยก field เพื่อความง่ายในการ query/report
    # ส่วนที่ 1: ผลสำเร็จของงาน
    q1_1 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q1_2 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q1_3 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    c1_comment = models.TextField(blank=True, verbose_name="ข้อเสนอแนะส่วนที่ 1")

    # ส่วนที่ 2: ความรู้ความสามารถ
    q2_1 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q2_2 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q2_3 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    c2_comment = models.TextField(blank=True, verbose_name="ข้อเสนอแนะส่วนที่ 2")

    # ส่วนที่ 3: ความรับผิดชอบ
    q3_1 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q3_2 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q3_3 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    c3_comment = models.TextField(blank=True, verbose_name="ข้อเสนอแนะส่วนที่ 3")

    # ส่วนที่ 4: ลักษณะส่วนบุคคล
    q4_1 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q4_2 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q4_3 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    c4_comment = models.TextField(blank=True, verbose_name="ข้อเสนอแนะส่วนที่ 4")

    # ส่วนที่ 5: การมีส่วนร่วมกับองค์กร
    q5_1 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q5_2 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    q5_3 = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    c5_comment = models.TextField(blank=True, verbose_name="ข้อเสนอแนะส่วนที่ 5")

    # สรุปภาพรวม
    strengths = models.TextField(blank=True, verbose_name="จุดเด่น")
    weaknesses = models.TextField(blank=True, verbose_name="จุดที่ควรปรับปรุง")
    total_score = models.IntegerField(default=0, verbose_name="คะแนนรวม")

    STATUS_CHOICES = [
        ('DRAFT', 'บันทึกชั่วคราว'),
        ('SUBMITTED', 'ส่งผลการประเมิน'),
        ('APPROVED', 'อาจารย์รับรองแล้ว'), # สถานะนี้แก้ไขไม่ได้
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_total(self):
        """คำนวณคะแนนรวมอัตโนมัติ"""
        fields = [
            self.q1_1, self.q1_2, self.q1_3,
            self.q2_1, self.q2_2, self.q2_3,
            self.q3_1, self.q3_2, self.q3_3,
            self.q4_1, self.q4_2, self.q4_3,
            self.q5_1, self.q5_2, self.q5_3
        ]
        self.total_score = sum(fields)
        return self.total_score

    def save(self, *args, **kwargs):
        self.calculate_total()
        super().save(*args, **kwargs)