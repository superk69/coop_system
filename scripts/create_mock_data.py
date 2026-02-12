import random
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.files.base import ContentFile

# Import Models จาก App ของคุณ (แก้ชื่อ internship_app เป็นชื่อ app จริงของคุณ)
from coopstack.models import (
    Student, CompanyMaster, CompanyProfile,
    TrainingRecord, JobApplication, WeeklyReport, 
    Evaluation, Announcement
)

User = get_user_model()

def run():
    print("🚀 เริ่มต้นกระบวนการ Mock Data...")

    # ใช้ transaction.atomic เพื่อความปลอดภัย (ถ้าพังให้ Rollback ทั้งหมด)
    with transaction.atomic():
        # 1. Clear Data เก่า (เรียงลำดับการลบเพื่อป้องกัน Foreign Key Error)
        print("🗑️  ล้างข้อมูลเก่า...")
        Evaluation.objects.all().delete()
        WeeklyReport.objects.all().delete()
        JobApplication.objects.all().delete()
        TrainingRecord.objects.all().delete()
        Announcement.objects.all().delete()
        CompanyProfile.objects.all().delete()
        CompanyMaster.objects.all().delete()
        Student.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete() # เก็บ Superuser ไว้

        # ==========================================
        # 2. สร้าง Users หลัก (Teacher & Companies)
        # ==========================================
        print("👤 สร้างบัญชีอาจารย์และบริษัท...")
        
        # 2.1 อาจารย์
        teacher_user = User.objects.create_user(
            username='teacher', email='teacher@uni.edu', password='password123',
            first_name='สมศรี', last_name='ใจดี', role=User.Role.TEACHER
        )

        # 2.2 บริษัท (สร้าง 2 บริษัท)
        # บริษัท A: Tech Connect (รับเด็กแล้ว)
        comp_a_user = User.objects.create_user(
            username='company_a', email='hr@techconnect.com', password='password123',
            first_name='John', last_name='Doe', role=User.Role.COMPANY
        )
        comp_a_master = CompanyMaster.objects.create(
            name='บริษัท เทค คอนเน็ค จำกัด',
            address='123 ถ.สาทร กทม.',
            phone='02-111-2222',
            email='hr@techconnect.com',
            website='www.techconnect.com',
            contact_person='คุณจอห์น (HR)'
        )
        CompanyProfile.objects.create(user=comp_a_user, company=comp_a_master)

        # บริษัท B: Soft Solution (ยังว่าง)
        comp_b_user = User.objects.create_user(
            username='company_b', email='hr@softsol.com', password='password123',
            first_name='Jane', last_name='Smith', role=User.Role.COMPANY
        )
        comp_b_master = CompanyMaster.objects.create(
            name='บริษัท ซอฟต์ โซลูชั่น',
            address='456 ถ.สุขุมวิท กทม.',
            phone='02-333-4444',
            email='hr@softsol.com',
            contact_person='คุณเจน (Manager)'
        )
        CompanyProfile.objects.create(user=comp_b_user, company=comp_b_master)


        # ==========================================
        # 3. สร้าง Students (4 Scenarios)
        # ==========================================
        print("🎓 สร้างข้อมูลนักศึกษา (4 Cases)...")

        # --- Case 1: เด็กใหม่ (Training ยังไม่ครบ) ---
        u1 = User.objects.create_user(
            username='student_new', email='s1@uni.edu', password='password123',
            first_name='สมชาย', last_name='เรียนดี', role=User.Role.STUDENT
        )
        s1 = Student.objects.create(
            user=u1, student_code='660001', firstname='สมชาย', lastname='เรียนดี', 
            major='วิทยาการคอมพิวเตอร์', gpa=3.50, phone='081-111-1111'
        )
        # เพิ่มอบรมไปแค่นิดเดียว (10 ชม.)
        TrainingRecord.objects.create(
            student=s1, topic='อบรม Python เบื้องต้น', date=timezone.now().date(),
            hours=6, status='APPROVED'
        )
        TrainingRecord.objects.create(
            student=s1, topic='อบรม Git', date=timezone.now().date(),
            hours=4, status='PENDING'
        )

        # --- Case 2: พร้อมสมัครงาน (Training ครบ 30 ชม.) ---
        u2 = User.objects.create_user(
            username='student_ready', email='s2@uni.edu', password='password123',
            first_name='สมหญิง', last_name='จริงใจ', role=User.Role.STUDENT
        )
        s2 = Student.objects.create(
            user=u2, student_code='660002', firstname='สมหญิง', lastname='จริงใจ', 
            major='เทคโนโลยีสารสนเทศ', gpa=3.80, phone='082-222-2222'
        )
        TrainingRecord.objects.create(
            student=s2, topic='อบรม Fullstack Development', date=timezone.now().date(),
            hours=30, status='APPROVED'
        )
        # (สถานะ: พร้อมสมัครงาน แต่ยังไม่ได้สมัคร)

        # --- Case 3: กำลังฝึกงาน (Active Intern) ---
        u3 = User.objects.create_user(
            username='student_active', email='s3@uni.edu', password='password123',
            first_name='เอกชัย', last_name='ใฝ่รู้', role=User.Role.STUDENT
        )
        s3 = Student.objects.create(
            user=u3, student_code='660003', firstname='เอกชัย', lastname='ใฝ่รู้', 
            major='วิศวกรรมซอฟต์แวร์', gpa=2.90, phone='083-333-3333'
        )
        TrainingRecord.objects.create(student=s3, topic='Camp', hours=35, status='APPROVED', date=timezone.now().date())
        
        # สมัครงานและได้รับการอนุมัติแล้ว
        job3 = JobApplication.objects.create(
            student=s3, company=comp_a_master, position='Backend Developer',
            start_date=timezone.now().date() - timedelta(days=20), # เริ่มมา 20 วันแล้ว
            end_date=timezone.now().date() + timedelta(days=70),
            status='APPROVED',
            supervisor_name='พี่เลี้ยง A', supervisor_email='mentor@tech.com'
        )

        # ส่งรายงาน 2 สัปดาห์
        WeeklyReport.objects.create(
            job_application=job3, week_number=1,
            start_date=job3.start_date,
            end_date=job3.start_date + timedelta(days=5),
            work_summary='เรียนรู้ระบบงานวันแรก Setup Environment',
            problems='ยังไม่ชินกับ Ubuntu',
            knowledge_gained='Command Line พื้นฐาน',
            status='ACKNOWLEDGED', teacher_comment='ดีมากครับ พยายามต่อไป'
        )
        WeeklyReport.objects.create(
            job_application=job3, week_number=2,
            start_date=job3.start_date + timedelta(days=7),
            end_date=job3.start_date + timedelta(days=12),
            work_summary='เริ่มเขียน API เล็กๆ',
            problems='ติดเรื่อง Join Table ใน SQL',
            knowledge_gained='Django ORM',
            status='PENDING' # อาจารย์ยังไม่ตรวจ
        )

        # --- Case 4: ฝึกงานจบแล้ว (Completed & Evaluated) ---
        u4 = User.objects.create_user(
            username='student_done', email='s4@uni.edu', password='password123',
            first_name='วิภา', last_name='กล้าหาญ', role=User.Role.STUDENT
        )
        s4 = Student.objects.create(
            user=u4, student_code='660004', firstname='วิภา', lastname='กล้าหาญ', 
            major='วิทยาการคอมพิวเตอร์', gpa=3.95, phone='084-444-4444'
        )
        TrainingRecord.objects.create(student=s4, topic='Workshop', hours=40, status='APPROVED', date=timezone.now().date())
        
        job4 = JobApplication.objects.create(
            student=s4, company=comp_a_master, position='Data Analyst',
            start_date=timezone.now().date() - timedelta(days=100),
            end_date=timezone.now().date() - timedelta(days=10), # จบไปแล้ว
            status='COMPLETED',
            supervisor_name='พี่เลี้ยง B', supervisor_email='mentor2@tech.com'
        )

        # สร้างผลประเมินจากบริษัท
        Evaluation.objects.create(
            job_application=job4,
            evaluator_name='คุณจอห์น (HR)',
            part1_score=28, # เต็ม 30
            part2_score=35, # เต็ม 40
            part3_score=29, # เต็ม 30
            total_score=92,
            strengths='เรียนรู้งานไวมาก ขยัน',
            weaknesses='บางครั้งไม่กล้าถาม',
            suggestion='อยากให้มั่นใจในตัวเองมากกว่านี้',
            teacher_ack_status='PENDING' # อาจารย์ยังไม่กดรับทราบ
        )

        # ==========================================
        # 4. สร้างประกาศข่าวสาร (Announcements)
        # ==========================================
        print("📢 สร้างประกาศข่าวสาร...")
        Announcement.objects.create(
            title='แจ้งกำหนดการส่งเอกสารสหกิจศึกษา',
            content='ขอให้นักศึกษาชั้นปีที่ 4 ส่งเอกสารภายในวันที่ 30 นี้...',
            is_published=True,
            is_pinned=True
        )
        Announcement.objects.create(
            title='รับสมัครงานบริษัท Tech Connect',
            content='บริษัท Tech Connect เปิดรับสมัคร Backend Dev 2 ตำแหน่ง...',
            is_published=True,
            is_pinned=False
        )
        Announcement.objects.create(
            title='(Draft) กำหนดการนิเทศงาน',
            content='อาจารย์จะเริ่มออกนิเทศงานเดือนหน้า...',
            is_published=False # ยังไม่เผยแพร่
        )

    print("✅ Mock Data เสร็จสมบูรณ์! พร้อมใช้งาน")
    print("----------------------------------------------------")
    print("Login Users:")
    print("1. อาจารย์:   teacher / password123")
    print("2. บริษัท A:  company_a / password123")
    print("3. นศ.ใหม่:   student_new / password123")
    print("4. นศ.พร้อม:  student_ready / password123")
    print("5. นศ.ฝึกงาน: student_active / password123")
    print("6. นศ.จบแล้ว: student_done / password123")
    print("----------------------------------------------------")