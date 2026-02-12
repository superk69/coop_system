import random
from datetime import date, timedelta
from faker import Faker
from django.contrib.auth import get_user_model
from django.utils import timezone
# แก้ไข .models เป็นชื่อ App ของคุณ เช่น from myapp.models import ...
# สมมติว่า App ชื่อ 'coopstack' (กรุณาเปลี่ยนให้ตรงกับโปรเจคจริง)
from coopstack.models import Student, CompanyMaster, JobApplication, CompanyProfile 

fake = Faker(['th_TH']) # ใช้ภาษาไทย

User = get_user_model()
def run():
    print("🚀 เริ่มต้นการสร้างข้อมูล Mock Data สำหรับ Company Summary...")
    
    # 1. ล้างข้อมูลเก่า (Optional: เปิดบรรทัดล่างถ้าต้องการล้างข้อมูลก่อน)
    # clean_database()

    # 2. สร้างข้อมูลบริษัท (CompanyMaster)
    companies = create_companies(15)

    # 3. สร้างนักศึกษา (Student)
    students = create_students(50)

    # 4. สร้างประวัติการฝึกงาน (JobApplication)
    create_job_applications(students, companies)

    print("✅ สร้างข้อมูลเสร็จสมบูรณ์! ทดสอบได้ที่หน้า /teacher/company-summary/")

def clean_database():
    print("🧹 กำลังล้างข้อมูลเก่า...")
    JobApplication.objects.all().delete()
    CompanyMaster.objects.all().delete()
    Student.objects.all().delete()
    # User.objects.filter(is_staff=False).delete() # ระวังลบ user admin
    print("   ล้างข้อมูลเรียบร้อย")

def create_companies(count):
    print(f"🏢 กำลังสร้างบริษัท {count} แห่ง...")
    companies = []
    
    # รายชื่อบริษัทตัวอย่างเพื่อให้ดูสมจริง
    tech_suffixes = ["เทคโนโลยี", "โซลูชั่น", "ซอฟต์แวร์", "ดิจิทัล", "อินโนเวชั่น", "จำกัด", "มหาชน"]
    
    for _ in range(count):
        name = f"{fake.company()} {random.choice(tech_suffixes)}"
        
        # สุ่มใส่ความเห็นอาจารย์ (ประมาณ 40% ของบริษัทจะมีคอมเมนต์)
        comment = ""
        if random.random() < 0.4:
            comment = random.choice([
                "ดูแลนักศึกษาดีมาก มีเบี้ยเลี้ยงให้",
                "งานค่อนข้างหนัก แต่ได้ทักษะเยอะ",
                "เน้นงานเอกสารมากกว่าเขียนโค้ด ควรพิจารณา",
                "สถานที่ทำงานเดินทางสะดวก พี่เลี้ยงเป็นกันเอง",
                "ต้องใช้ภาษาอังกฤษในการสื่อสาร",
                "เทคโนโลยีทันสมัย แนะนำสำหรับเด็กเก่ง",
            ])

        company = CompanyMaster.objects.create(
            name=name,
            address=fake.address(),
            phone=fake.phone_number(),
            teacher_notes=comment
        )
        companies.append(company)
        
    return companies

def create_students(count):
    print(f"🎓 กำลังสร้างนักศึกษา {count} คน...")
    students = []
    for _ in range(count):
        first_name = fake.first_name()
        last_name = fake.last_name()
        username = f"std_{random.randint(1000, 9999)}_{first_name}"
        
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=f"{username}@example.com",
            password="password123",
            role=User.Role.STUDENT
        )
        
        # รหัสนักศึกษาแบบสุ่ม
        student_id = f"{random.choice(['64', '65', '66', '67'])}{random.randint(10000000, 99999999)}"
        
        student = Student.objects.create(
            user=user,
            student_code=student_id
            # academic_year อาจจะถูกอัปเดตอัตโนมัติหรือใส่ไว้ก่อน
            #academic_year=f"25{student_id[:2]}" 
        )
        students.append(student)
    return students

def create_job_applications(students, companies):
    print("📝 กำลังสร้างประวัติการฝึกงาน (JobApplication)...")
    
    positions = [
        "Frontend Developer", "Backend Developer", "Full Stack Developer",
        "UX/UI Designer", "Software Tester", "Data Analyst", 
        "Network Engineer", "System Admin"
    ]
    
    for student in students:
        # สุ่มบริษัท
        company = random.choice(companies)
        
        # สุ่มปีการศึกษาที่จะไปฝึก (เพื่อทดสอบการรวมกลุ่มปี)
        # 2565, 2566, 2567
        year_offset = random.choice([0, 1, 2]) 
        base_year_ad = 2024 - year_offset # 2024, 2023, 2022
        
        # กำหนดวันเริ่มฝึกงาน (ช่วง มิ.ย - ส.ค)
        start_month = random.randint(6, 8)
        start_date = date(base_year_ad, start_month, 1)
        end_date = start_date + timedelta(days=120) # ฝึก 4 เดือน
        
        # สร้าง JobApplication
        # หมายเหตุ: เราใส่ company_name ให้ตรงกับ CompanyMaster เพื่อให้ Logic การค้นหาทำงานได้
        job = JobApplication.objects.create(
            student=student,
            company=company, # สำคัญ: ต้องตรงกับ CompanyMaster.name
            position=random.choice(positions),
            start_date=start_date,
            end_date=end_date,
            status='APPROVED', # ต้อง Approved ถึงจะขึ้นในสรุป
            
            # ถ้ามี field academic_year ที่คำนวณ auto ใน models.py แล้ว ไม่ต้องใส่
            # แต่ถ้าไม่มี ให้ uncomment บรรทัดล่าง
            # academic_year = base_year_ad + 543 
        )

    print(f"   สร้างใบสมัครงานเรียบร้อย {len(students)} รายการ")