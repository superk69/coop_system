from django.shortcuts import render
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from rest_framework.parsers import MultiPartParser, FormParser

from django.db import transaction

from .models import Student, JobApplication, TrainingRecord, CompanyMaster, WeeklyReport, Evaluation, JobApplication

from django.shortcuts import get_object_or_404

from django.db.models import Q, Sum, Prefetch
from .serializers import (
    StudentProfileSerializer, 
    TrainingRecordSerializer, 
    JobApplicationSerializer, 
    WeeklyReportSerializer,
    EvaluationSerializer
)
from .serializers import RegisterSerializer
from .serializers import CompanyMasterSerializer 

from rest_framework.permissions import AllowAny
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

class LoginView(APIView):
    """
    API สำหรับเข้าสู่ระบบ (Authentication)
    - รับ: username, password
    - ส่งกลับ: Access Token, Refresh Token และข้อมูล User Profile (Role, Name)
    """
    permission_classes = [AllowAny] # ใครก็เข้าถึงได้ ไม่ต้อง Login ก่อน

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {"detail": "กรุณากรอก Username และ Password"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # ตรวจสอบ Username/Password
        user = authenticate(username=username, password=password)

        if user is not None:
            if not user.is_active:
                return Response(
                    {"detail": "บัญชีนี้ถูกระงับการใช้งาน กรุณาติดต่อเจ้าหน้าที่"}, 
                    status=status.HTTP_403_FORBIDDEN
                )

            # สร้าง JWT Token (Access & Refresh)
            refresh = RefreshToken.for_user(user)
            
            # เตรียมข้อมูลส่งกลับ (User Info + Tokens)
            # Frontend จะใช้ 'role' ในการ Route ไปยัง Dashboard ที่ถูกต้อง
            data = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,  # STUDENT, TEACHER, COMPANY, ADMIN
                    'firstname': user.first_name,
                    'lastname': user.last_name,
                }
            }

            return Response(data, status=status.HTTP_200_OK)

        else:
            return Response(
                {"detail": "Username หรือ Password ไม่ถูกต้อง"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )


class RegisterView(APIView):
    """
    API สำหรับลงทะเบียนนักศึกษาใหม่ (FR-01)
    - รับข้อมูล: username, password, email, student_code, firstname, lastname, major
    - การทำงาน: สร้าง User + Student Profile (Atomic Transaction)
    - ผลลัพธ์: ลงทะเบียนสำเร็จ พร้อมส่ง JWT Token กลับไปให้ (Auto Login)
    """
    # อนุญาตให้เข้าถึงได้โดยไม่ต้องมี Token (Guest)
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        # 1. Validate Data (เช็ค format, เช็ค student_code ซ้ำ ฯลฯ)
        if serializer.is_valid():
            # 2. Save User & Profile (เรียก create method ใน serializer)
            user = serializer.save()

            # 3. Auto Login Logic (Generate JWT Token ทันที)
            # ช่วยลดขั้นตอน User ไม่ต้องไปกรอก Login อีกรอบ
            refresh = RefreshToken.for_user(user)

            return Response({
                "message": "ลงทะเบียนสำเร็จ ยินดีต้อนรับเข้าสู่ระบบ",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role, # Should be 'STUDENT'
                    "firstname": user.first_name,
                    "lastname": user.last_name
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
        
        # กรณีข้อมูลไม่ถูกต้อง (เช่น รหัสผ่านสั้นไป, รหัสนักศึกษาซ้ำ)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    """
    Step 1: ผู้ใช้กรอก Email เพื่อขอ Reset Password
    - ตรวจสอบว่ามี Email นี้ในระบบหรือไม่
    - ถ้ามี: สร้าง Token และส่ง Link ไปทาง Email
    """
    permission_classes = [AllowAny] # ไม่ต้อง Login ก็เข้าได้

    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({"detail": "กรุณาระบุ Email"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            User = get_user_model()
            user = User.objects.get(email=email)
            
            # 1. สร้าง Token สำหรับ Reset Password (ใช้ Django Built-in)
            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            
            # 2. Encode User ID (เพื่อความปลอดภัยในการส่งผ่าน URL)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            
            # 3. สร้าง Link (ลิงก์นี้ต้องชี้ไปที่หน้า Frontend ของคุณ)
            # ตัวอย่าง: http://localhost:3000/reset-password/MTU/ar45-xz...
            # Frontend ต้องดึง uidb64 และ token จาก URL นี้เพื่อส่งกลับมาใน Step 2
            reset_link = f"http://localhost:3000/reset-password/{uidb64}/{token}/"
            
            # 4. ส่ง Email (Console Print สำหรับ Dev, send_mail สำหรับ Prod)
            print(f"------------ RESET PASSWORD LINK ------------")
            print(f"Send to: {email}")
            print(f"Link: {reset_link}")
            print(f"---------------------------------------------")
            
            # ใน Production ให้เปิดบรรทัดนี้:
            # send_mail(
            #     subject="Reset Password Request",
            #     message=f"Click verify link to reset password: {reset_link}",
            #     from_email=settings.EMAIL_HOST_USER,
            #     recipient_list=[email],
            # )

            return Response({
                "message": "หาก Email นี้มีอยู่ในระบบ เราได้ส่งลิงก์กู้คืนรหัสผ่านไปให้แล้ว",
                # "dev_link": reset_link # (Optional: เปิดบรรทัดนี้ตอน Dev เพื่อ Copy Link ง่ายๆ)
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            # Security: เราจะไม่บอกว่า "ไม่มี Email นี้" เพื่อป้องกันการสุ่มเดา Email
            # เราจะตอบกลับเหมือนกับว่าส่งไปแล้ว
            return Response({
                "message": "หาก Email นี้มีอยู่ในระบบ เราได้ส่งลิงก์กู้คืนรหัสผ่านไปให้แล้ว"
            }, status=status.HTTP_200_OK)


class ResetPasswordConfirmView(APIView):
    """
    Step 2: ผู้ใช้ตั้งรหัสผ่านใหม่ (ต้องมี UID และ Token ที่ถูกต้อง)
    - รับ: uid, token, new_password
    """
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not uidb64 or not token or not new_password:
            return Response({"detail": "ข้อมูลไม่ครบถ้วน"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Decode UID เพื่อหาว่าคือ User คนไหน
            uid = force_str(urlsafe_base64_decode(uidb64))
            User = get_user_model()
            user = User.objects.get(pk=uid)
            
            # 2. ตรวจสอบความถูกต้องของ Token
            token_generator = PasswordResetTokenGenerator()
            if not token_generator.check_token(user, token):
                return Response(
                    {"detail": "ลิงก์รีเซ็ตรหัสผ่านไม่ถูกต้องหรือหมดอายุแล้ว"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 3. ตั้งรหัสผ่านใหม่
            user.set_password(new_password)
            user.save()

            return Response({"message": "เปลี่ยนรหัสผ่านสำเร็จ คุณสามารถเข้าสู่ระบบได้ทันที"}, status=status.HTTP_200_OK)

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"detail": "ลิงก์ไม่ถูกต้อง"}, status=status.HTTP_400_BAD_REQUEST)
        

# ============================================
 # 2. Student Module
 # ============================================

class StudentDashboardView(APIView):
    """
    API สำหรับหน้า Dashboard ของนักศึกษา (FR-05)
    แสดงข้อมูลโปรไฟล์, ความก้าวหน้าชั่วโมงอบรม, และสถานะการสมัครงานปัจจุบัน
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบว่าเป็นนักศึกษาหรือไม่
        if user.role != 'STUDENT':
            return Response(
                {"detail": "สิทธิ์การเข้าถึงไม่ถูกต้อง เฉพาะนักศึกษาเท่านั้น"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # ดึงข้อมูล Profile
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            return Response(
                {"detail": "ไม่พบข้อมูลโปรไฟล์นักศึกษา"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. คำนวณความก้าวหน้าการอบรม (Training Progress)
        # รวมชั่วโมงที่สถานะเป็น APPROVED เท่านั้น
        training_agg = TrainingRecord.objects.filter(
            student=student,
            status=TrainingRecord.Status.APPROVED
        ).aggregate(total_approved=Sum('approved_hours'))

        approved_hours = training_agg['total_approved'] or 0
        required_hours = 30
        
        # คำนวณเปอร์เซ็นต์ (ไม่เกิน 100%)
        progress_percentage = min((approved_hours / required_hours) * 100, 100)
        is_qualified_for_job = approved_hours >= required_hours

        # 3. ดึงสถานะการสมัครงานล่าสุด (Current Job Status)
        # เลือกใบสมัครล่าสุด ที่ไม่ได้ถูก 'ยกเลิก' (CANCELLED)
        current_job = JobApplication.objects.filter(
            student=student
        ).exclude(
            status=JobApplication.Status.CANCELLED
        ).order_by('-created_at').first()

        job_data = None
        if current_job:
            job_data = {
                "id": current_job.id,
                "company_name": current_job.company_name_snapshot,
                "position": current_job.position,
                "status": current_job.status,
                "status_display": current_job.get_status_display(), # แปลง ENUM เป็นข้อความภาษาไทย
                "teacher_note": current_job.teacher_note,
                "updated_at": current_job.updated_at
            }

        # 4. ประกอบข้อมูล Response
        data = {
            "profile": {
                "fullname": f"{student.firstname} {student.lastname}",
                "student_code": student.student_code,
                "major": student.major,
                "email": user.email
            },
            "progress": {
                "approved_hours": approved_hours,
                "required_hours": required_hours,
                "percentage": round(progress_percentage, 1),
                "is_qualified": is_qualified_for_job,
                "message": "ผ่านเกณฑ์อบรมแล้ว" if is_qualified_for_job else f"ขาดอีก {required_hours - approved_hours} ชั่วโมง"
            },
            "current_job": job_data # จะเป็น Object หรือ null
        }

        return Response(data, status=status.HTTP_200_OK)


class StudentTrainingView(APIView):
    """
    API สำหรับจัดการข้อมูลการอบรมของนักศึกษา (FR-07)
    - GET: ดูประวัติการอบรม
    - POST: บันทึกการอบรมใหม่ พร้อมอัปโหลดไฟล์หลักฐาน
    """
    permission_classes = [IsAuthenticated]
    
    # รองรับการอัปโหลดไฟล์ (Multipart)
    parser_classes = [MultiPartParser, FormParser]

    def get_student(self, user):
        """Helper: ตรวจสอบและดึงข้อมูลนักศึกษา"""
        if user.role != 'STUDENT':
            return None
        try:
            return user.student_profile
        except Student.DoesNotExist:
            return None

    def get(self, request):
        student = self.get_student(request.user)
        if not student:
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะนักศึกษาเท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 1. Query Data
        records = TrainingRecord.objects.filter(student=student).order_by('-submitted_at')
        
        # 2. Serialize Data
        # context={'request': request} จำเป็นเพื่อให้ Serializer สร้าง Absolute URL สำหรับไฟล์รูปภาพ/PDF ได้ถูกต้อง
        serializer = TrainingRecordSerializer(records, many=True, context={'request': request})
        
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        student = self.get_student(request.user)
        if not student:
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง"}, status=status.HTTP_403_FORBIDDEN)

        # 1. Pass Data to Serializer
        serializer = TrainingRecordSerializer(data=request.data)

        # 2. Validate Data
        if serializer.is_valid():
            # 3. Save Data (พร้อมระบุว่าใครเป็นเจ้าของ record นี้)
            # เราต้องส่ง student instance เข้าไปตอน save เพราะใน request.data ไม่มี student_id
            serializer.save(student=student)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        # กรณีข้อมูลไม่ถูกต้อง (เช่น ลืมแนบไฟล์, ใส่ชั่วโมงไม่ใช่ตัวเลข)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class StudentJobApplicationView(APIView):
    """
    API สำหรับการสมัครงานสหกิจ (FR-08 - Smart Form)
    - GET: ดูข้อมูลใบสมัครปัจจุบัน (ที่ไม่ใช่สถานะ Cancelled)
    - POST: ส่งใบสมัครใหม่ (พร้อม Logic สร้าง Company Master อัตโนมัติ)
    """
    permission_classes = [IsAuthenticated]

    def get_student(self, user):
        if user.role != 'STUDENT':
            return None
        try:
            return user.student_profile
        except Student.DoesNotExist:
            return None

    def get(self, request):
        student = self.get_student(request.user)
        if not student:
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง"}, status=status.HTTP_403_FORBIDDEN)

        # ดึงใบสมัครล่าสุด ที่ยังไม่ถูกยกเลิก (Active Application)
        try:
            job = JobApplication.objects.filter(student=student) \
                .exclude(status=JobApplication.Status.CANCELLED) \
                .latest('created_at')
            
            serializer = JobApplicationSerializer(job)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except JobApplication.DoesNotExist:
            # กรณีไม่มีใบสมัคร หรือยกเลิกไปหมดแล้ว ให้ return null หรือ 404
            return Response(None, status=status.HTTP_204_NO_CONTENT)

    def post(self, request):
        student = self.get_student(request.user)
        if not student:
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง"}, status=status.HTTP_403_FORBIDDEN)

        # ==========================================
        # 1. ตรวจสอบเงื่อนไข 30 ชั่วโมง (FR-08 Condition)
        # ==========================================
        training_agg = TrainingRecord.objects.filter(
            student=student,
            status=TrainingRecord.Status.APPROVED
        ).aggregate(total=Sum('approved_hours'))
        
        total_hours = training_agg['total'] or 0
        if total_hours < 30:
            return Response(
                {"detail": f"คุณมีชั่วโมงอบรมเพียง {total_hours} ชม. (ต้องการ 30 ชม.)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ==========================================
        # 2. ตรวจสอบว่ามีงานค้างอยู่หรือไม่
        # ==========================================
        has_active_job = JobApplication.objects.filter(student=student) \
            .exclude(status=JobApplication.Status.CANCELLED).exists()
        
        if has_active_job:
            return Response(
                {"detail": "คุณมีใบสมัครที่กำลังดำเนินการอยู่ ไม่สามารถสมัครซ้ำได้"},
                status=status.HTTP_409_CONFLICT
            )

        # ==========================================
        # 3. Process Smart Form (Company Logic)
        # ==========================================
        data = request.data.copy()
        
        # รับค่า company_id (ถ้าเลือกจาก Search) หรือ company_name (ถ้ากรอกใหม่)
        req_company_id = data.get('company_id') 
        req_company_name = data.get('company_name')

        company_instance = None

        try:
            with transaction.atomic():
                # กรณี A: เลือกบริษัทที่มีอยู่แล้ว
                if req_company_id:
                    try:
                        company_instance = CompanyMaster.objects.get(pk=req_company_id)
                        # อัปเดตข้อมูลล่าสุดลง Master ด้วย (Optional: เพื่อให้ Master ทันสมัยเสมอ)
                        # company_instance.address = data.get('company_location')
                        # company_instance.save()
                    except CompanyMaster.DoesNotExist:
                        return Response({"detail": "ไม่พบ ID บริษัทที่ระบุ"}, status=status.HTTP_400_BAD_REQUEST)
                
                # กรณี B: บริษัทใหม่ (ไม่มี ID ส่งมา) -> สร้างลง Knowledge Base
                elif req_company_name:
                    company_instance = CompanyMaster.objects.create(
                        company_name=req_company_name,
                        address=data.get('company_location'), # เก็บ Address หลัก
                        contact_person=data.get('supervisor_name'), # เก็บผู้ติดต่อเบื้องต้น
                        contact_phone=data.get('supervisor_phone')
                    )

                # ==========================================
                # 4. Save Job Application
                # ==========================================
                serializer = JobApplicationSerializer(data=data)
                if serializer.is_valid():
                    # บันทึกโดยผูกกับ student และ company_master (ที่หาได้หรือสร้างใหม่ตะกี้)
                    serializer.save(
                        student=student,
                        company=company_instance, # FK ไปยัง Master
                        
                        # บันทึก Snapshot Data (ชื่อบริษัท ณ วันที่สมัคร)
                        company_name_snapshot=company_instance.company_name if company_instance else req_company_name,
                        
                        # กำหนด Status เริ่มต้น
                        status=JobApplication.Status.PENDING
                    )
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class StudentJobCancelView(APIView):
    """
    API สำหรับยกเลิกการฝึกงาน (FR-18)
    - เปลี่ยนสถานะใบสมัครเป็น CANCELLED
    - ทำให้นักศึกษาสามารถกดสมัครงานที่ใหม่ได้ (Reset Process)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        
        # 1. ตรวจสอบสิทธิ์ว่าเป็นนักศึกษา
        if user.role != 'STUDENT':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            return Response({"detail": "ไม่พบข้อมูลโปรไฟล์นักศึกษา"}, status=status.HTTP_404_NOT_FOUND)

        # 2. ดึงข้อมูลใบสมัคร (ต้องเป็นของนักศึกษาคนนี้เท่านั้น)
        job = get_object_or_404(JobApplication, pk=pk, student=student)

        # 3. Validation ก่อนยกเลิก
        if job.status == JobApplication.Status.CANCELLED:
            return Response(
                {"detail": "ใบสมัครนี้ถูกยกเลิกไปแล้ว"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # ป้องกันการยกเลิกงานที่ถูกประเมินผลไปแล้ว (ถ้ามี)
        if hasattr(job, 'evaluation'):
            return Response(
                {"detail": "ไม่สามารถยกเลิกงานที่ได้รับการประเมินผลแล้วได้"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. ดำเนินการยกเลิก (Soft Delete / Status Change)
        job.status = JobApplication.Status.CANCELLED
        
        # อาจจะเพิ่ม Note ว่าใครเป็นคนยกเลิก
        original_note = job.teacher_note if job.teacher_note else ""
        job.teacher_note = f"{original_note} [นักศึกษากดยกเลิกเองเมื่อ {status.HTTP_200_OK}]".strip()
        
        job.save()

        return Response({
            "id": job.id,
            "status": job.status,
            "message": "ยกเลิกการสมัครงานเรียบร้อยแล้ว คุณสามารถสมัครงานใหม่ได้ทันที"
        }, status=status.HTTP_200_OK)
    
class StudentWeeklyReportView(APIView):
    """
    API สำหรับจัดการรายงานรายสัปดาห์ (FR-09)
    - GET: ดูรายการรายงานทั้งหมดของงานปัจจุบัน
    - POST: ส่งรายงานประจำสัปดาห์ใหม่ (4 หัวข้อ)
    """
    permission_classes = [IsAuthenticated]

    def get_active_job(self, user):
        """
        Helper: ค้นหางานที่กำลังฝึกอยู่ (Status = APPROVED)
        """
        if user.role != 'STUDENT':
            return None, "สิทธิ์ไม่ถูกต้อง"
        
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            return None, "ไม่พบข้อมูลนักศึกษา"

        # ค้นหางานล่าสุดที่ได้รับอนุมัติแล้ว (APPROVED)
        # เราไม่เอางานที่ PENDING (ยังไม่เริ่มฝึก) หรือ CANCELLED/REJECTED
        job = JobApplication.objects.filter(
            student=student,
            status=JobApplication.Status.APPROVED
        ).order_by('-created_at').first()

        if not job:
            return None, "คุณยังไม่มีงานที่อยู่ในสถานะ 'กำลังฝึกงาน' (Approved) จึงยังไม่สามารถส่งรายงานได้"

        return job, None

    def get(self, request):
        # 1. หางานที่ Active อยู่
        job, error_msg = self.get_active_job(request.user)
        if not job:
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # 2. ดึงรายงานทั้งหมดของงานนี้ เรียงตามสัปดาห์
        reports = WeeklyReport.objects.filter(job_application=job).order_by('week_number')
        
        serializer = WeeklyReportSerializer(reports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # 1. หางานที่ Active อยู่
        job, error_msg = self.get_active_job(request.user)
        if not job:
            return Response({"detail": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        # 2. รับข้อมูลและตรวจสอบ
        serializer = WeeklyReportSerializer(data=request.data)
        if serializer.is_valid():
            week_number = serializer.validated_data.get('week_number')

            # 3. ตรวจสอบว่าสัปดาห์นี้เคยส่งไปหรือยัง? (Prevent Duplicate)
            if WeeklyReport.objects.filter(job_application=job, week_number=week_number).exists():
                return Response(
                    {"detail": f"รายงานสัปดาห์ที่ {week_number} ถูกส่งไปแล้ว ไม่สามารถส่งซ้ำได้"},
                    status=status.HTTP_409_CONFLICT
                )

            # 4. บันทึกข้อมูล (ผูกกับ Job Application ปัจจุบัน)
            serializer.save(job_application=job)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# 3. Teacher Module
# ============================================

class TeacherStudentListView(APIView):
    """
    API สำหรับอาจารย์ดูรายชื่อและสถานะนักศึกษาทั้งหมด (FR-16)
    - แสดงสรุปชั่วโมงอบรม (ผ่าน/ไม่ผ่าน)
    - แสดงสถานะการฝึกงานปัจจุบัน (ได้งาน/รออนุมัติ/ยังไม่สมัคร)
    - รองรับ Search & Filter
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Query Parameters สำหรับการค้นหา
        search_query = request.query_params.get('search', '') # ค้นหาชื่อหรือรหัส
        status_filter = request.query_params.get('status', 'ALL') # ALL, TRAINING_NOT_PASS, JOB_WAITING, JOB_APPROVED

        # 3. Base Query: ดึงนักศึกษาทั้งหมด
        # ใช้ select_related เพื่อดึง user มาด้วย (ลด query)
        students = Student.objects.select_related('user').all()

        # Apply Search
        if search_query:
            students = students.filter(
                Q(firstname__icontains=search_query) | 
                Q(lastname__icontains=search_query) | 
                Q(student_code__icontains=search_query)
            )

        # 4. Optimization: Prefetch Data
        # ดึงข้อมูล Training และ Job มารอไว้เลย ไม่ต้อง Query ใหม่ทุกรอบ Loop
        # (เทคนิคนี้ช่วยให้โหลดรายชื่อ 100 คนได้เร็วมาก)
        students = students.prefetch_related(
            'training_records',
            'job_applications'
        )

        student_list = []

        for s in students:
            # --- Logic คำนวณชั่วโมงอบรม ---
            # คำนวณใน Python (เร็วกว่า Query ซ้ำๆ ถ้าข้อมูล Prefetch มาแล้ว)
            approved_hours = sum(t.approved_hours for t in s.training_records.all() if t.status == TrainingRecord.Status.APPROVED)
            is_training_passed = approved_hours >= 30

            # --- Logic หาสถานะงานปัจจุบัน ---
            # หางานล่าสุดที่ไม่ใช่ Cancelled
            active_jobs = [j for j in s.job_applications.all() if j.status != JobApplication.Status.CANCELLED]
            # เรียงลำดับตามวันที่สร้าง (ใหม่สุดขึ้นก่อน) -> จำลอง logic .latest()
            active_jobs.sort(key=lambda x: x.created_at, reverse=True)
            
            current_job = active_jobs[0] if active_jobs else None
            
            job_status_display = "ยังไม่สมัคร"
            company_name = "-"
            job_status_code = "NONE"

            if current_job:
                job_status_code = current_job.status
                job_status_display = current_job.get_status_display()
                company_name = current_job.company_name_snapshot

            # --- Filter Logic (กรองตามเงื่อนไขพิเศษ) ---
            include_student = True
            if status_filter == 'TRAINING_NOT_PASS' and is_training_passed:
                include_student = False
            elif status_filter == 'JOB_WAITING' and job_status_code != 'PENDING':
                include_student = False
            elif status_filter == 'JOB_APPROVED' and job_status_code != 'APPROVED':
                include_student = False
            
            if include_student:
                student_list.append({
                    "id": s.id,
                    "student_code": s.student_code,
                    "fullname": f"{s.firstname} {s.lastname}",
                    "major": s.major,
                    "training_info": {
                        "hours": approved_hours,
                        "is_passed": is_training_passed
                    },
                    "job_info": {
                        "status": job_status_code,
                        "status_display": job_status_display,
                        "company": company_name
                    }
                })

        return Response(student_list, status=status.HTTP_200_OK)
    

class TeacherStudentDetailView(APIView):
    """
    API สำหรับอาจารย์ดูรายละเอียดเจาะลึกของนักศึกษารายคน (FR-16 Detail)
    - ข้อมูลส่วนตัว
    - ประวัติการอบรม (รวมชั่วโมง)
    - ประวัติการสมัครงาน (รวมถึงงานที่เคยยกเลิกไปแล้ว)
    - รายงานรายสัปดาห์ (ของงานปัจจุบัน)
    - ผลการประเมิน (ถ้ามี)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        
        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. ดึงข้อมูลนักศึกษา (ตาม PK ที่ส่งมา)
        student = get_object_or_404(Student, pk=pk)

        # ==========================================
        # Part A: Training Records
        # ==========================================
        training_records = TrainingRecord.objects.filter(student=student).order_by('-submitted_at')
        
        # คำนวณชั่วโมงรวมเฉพาะที่อนุมัติแล้ว
        total_approved_hours = training_records.filter(
            status=TrainingRecord.Status.APPROVED
        ).aggregate(total=Sum('approved_hours'))['total'] or 0

        # ใช้ Serializer แปลงข้อมูลรายการอบรม
        training_serializer = TrainingRecordSerializer(training_records, many=True, context={'request': request})

        # ==========================================
        # Part B: Job Applications History
        # ==========================================
        # ดึงประวัติการสมัครทั้งหมด (รวมถึงที่ยกเลิกไปแล้ว) เพื่อดู Timeline
        jobs = JobApplication.objects.filter(student=student).order_by('-created_at')
        job_serializer = JobApplicationSerializer(jobs, many=True)

        # ==========================================
        # Part C: Active Job Context (Reports & Eval)
        # ==========================================
        # หางาน "ปัจจุบัน" ที่ยังไม่ยกเลิก (เพื่อดึงรายงาน)
        active_job = jobs.exclude(status=JobApplication.Status.CANCELLED).first()
        
        reports_data = []
        evaluation_data = None

        if active_job:
            # 1. รายงานรายสัปดาห์ของงานปัจจุบัน
            reports = WeeklyReport.objects.filter(job_application=active_job).order_by('week_number')
            reports_data = WeeklyReportSerializer(reports, many=True).data

            # 2. การประเมินผล (ถ้ามี)
            if hasattr(active_job, 'evaluation'):
                evaluation_data = EvaluationSerializer(active_job.evaluation).data

        # ==========================================
        # Final Response Construction
        # ==========================================
        response_data = {
            "profile": StudentProfileSerializer(student).data,
            
            "training_summary": {
                "total_approved_hours": total_approved_hours,
                "is_passed": total_approved_hours >= 30,
                "records": training_serializer.data
            },
            
            "job_history": job_serializer.data, # List ของงานทั้งหมด
            
            "current_activity": {
                "has_active_job": active_job is not None,
                "weekly_reports": reports_data,
                "evaluation": evaluation_data
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
class VerifyTrainingListView(APIView):
    """
    API สำหรับอาจารย์ดึงรายการอบรมเพื่อรอการตรวจสอบ (FR-12)
    - Default: แสดงเฉพาะสถานะ PENDING (รอตรวจสอบ)
    - Option: ?status=ALL (แสดงทั้งหมด), ?status=APPROVED (แสดงที่ผ่านแล้ว)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Query Params (Default คือ PENDING)
        status_filter = request.query_params.get('status', 'PENDING')

        # 3. Base Query
        # ใช้ select_related('student') เพื่อลด Query เวลาดึงชื่อนักศึกษา (Performance Tuning)
        queryset = TrainingRecord.objects.select_related('student').order_by('submitted_at')

        # 4. Apply Filter
        if status_filter != 'ALL':
            # กรองตาม Status ที่ส่งมา (เช่น PENDING, APPROVED, REJECTED)
            queryset = queryset.filter(status=status_filter)
        
        # 5. Construct Custom Response
        # เราต้องการข้อมูล Training Record + ข้อมูลนักศึกษา (ชื่อ, รหัส)
        results = []
        
        # ใช้ Serializer เดิมเพื่อแปลงข้อมูลฝั่ง Training (จะได้ URL รูปภาพที่ถูกต้อง)
        # context={'request': request} สำคัญมากสำหรับการสร้าง Full URL ของไฟล์
        
        for record in queryset:
            record_data = TrainingRecordSerializer(record, context={'request': request}).data
            
            # Inject ข้อมูลนักศึกษาเข้าไปใน JSON
            record_data['student_info'] = {
                "id": record.student.id,
                "fullname": f"{record.student.firstname} {record.student.lastname}",
                "student_code": record.student.student_code,
                "major": record.student.major
            }
            
            results.append(record_data)

        return Response(results, status=status.HTTP_200_OK)
    

class VerifyTrainingUpdateView(APIView):
    """
    API สำหรับอาจารย์บันทึกผลการตรวจสอบการอบรม (FR-12)
    - Method: PUT
    - รับค่า: status (APPROVED/REJECTED), approved_hours (optional), teacher_note
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. ดึงข้อมูล Record ที่จะตรวจ
        record = get_object_or_404(TrainingRecord, pk=pk)

        # 3. รับค่าจาก Request
        new_status = request.data.get('status')
        teacher_note = request.data.get('teacher_note', '')
        
        # รับค่าชั่วโมง (ถ้าไม่ส่งมา จะเป็น None)
        try:
            approved_hours = float(request.data.get('approved_hours')) if request.data.get('approved_hours') is not None else None
        except ValueError:
            return Response({"detail": "จำนวนชั่วโมงต้องเป็นตัวเลข"}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Validation Logic
        if new_status not in [TrainingRecord.Status.APPROVED, TrainingRecord.Status.REJECTED, TrainingRecord.Status.PENDING]:
            return Response({"detail": "สถานะไม่ถูกต้อง (ต้องเป็น APPROVED หรือ REJECTED)"}, status=status.HTTP_400_BAD_REQUEST)

        # 5. Process Update
        record.status = new_status
        record.teacher_note = teacher_note

        if new_status == TrainingRecord.Status.APPROVED:
            # กรณีอนุมัติ: ถ้าอาจารย์ระบุชั่วโมงมาให้ใช้ค่านั้น, ถ้าไม่ระบุให้ใช้ตามที่นักศึกษาขอมา
            if approved_hours is not None:
                record.approved_hours = approved_hours
            else:
                record.approved_hours = record.requested_hours
        
        elif new_status == TrainingRecord.Status.REJECTED:
            # กรณีปฏิเสธ: ชั่วโมงที่ได้ต้องเป็น 0 เสมอ
            record.approved_hours = 0

        # 6. Save ลง Database
        record.save()

        # 7. Return Updated Data
        # ส่งข้อมูลล่าสุดกลับไปเพื่อให้ Frontend อัปเดต UI (เช่น เปลี่ยนป้าย Status ทันที)
        serializer = TrainingRecordSerializer(record, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class VerifyJobListView(APIView):
    """
    API สำหรับอาจารย์ดึงรายการใบสมัครงานเพื่อรอการอนุมัติ (FR-12)
    - Default: แสดงเฉพาะสถานะ PENDING (รอตรวจสอบ)
    - Option: ?status=ALL (แสดงทั้งหมด), ?status=APPROVED, ?status=REJECTED
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Query Params (Default คือ PENDING)
        status_filter = request.query_params.get('status', 'PENDING')

        # 3. Base Query
        # ใช้ select_related เพื่อดึงข้อมูล Student และ Company มาพร้อมกัน (ลด N+1 Query)
        queryset = JobApplication.objects.select_related('student', 'company').order_by('-created_at')

        # 4. Apply Filter
        if status_filter != 'ALL':
            queryset = queryset.filter(status=status_filter)

        # 5. Construct Response Data
        results = []
        
        for job in queryset:
            # แปลงข้อมูล Job เป็น JSON
            job_data = JobApplicationSerializer(job).data
            
            # Inject ข้อมูลนักศึกษา (เพื่อให้แสดงหัวการ์ดได้ว่าใครขอมา)
            job_data['student_info'] = {
                "id": job.student.id,
                "fullname": f"{job.student.firstname} {job.student.lastname}",
                "student_code": job.student.student_code,
                "major": job.student.major,
                "gpa": job.student.gpa # เผื่ออาจารย์ใช้ประกอบการตัดสินใจ
            }
            
            # Inject ข้อมูลบริษัท (กรณีอยากโชว์ที่อยู่หรือเบอร์โทรเพิ่มเติมจาก Snapshot)
            # หมายเหตุ: company_name_snapshot มีใน serializer อยู่แล้ว
            if job.company:
                job_data['company_info'] = {
                    "id": job.company.id,
                    "address": job.company.address,
                    "contact_person": job.company.contact_person
                }

            results.append(job_data)

        return Response(results, status=status.HTTP_200_OK)
    

class VerifyJobUpdateView(APIView):
    """
    API สำหรับอาจารย์บันทึกผลการตรวจสอบใบสมัครงาน (FR-12)
    - Method: PUT
    - รับค่า: status (APPROVED/REJECTED), teacher_note
    - Logic พิเศษ: ป้องกันการอนุมัติงานซ้อน (1 คน มีงาน Active ได้แค่งานเดียว)
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. ดึงใบสมัครที่ต้องการตรวจสอบ
        job = get_object_or_404(JobApplication, pk=pk)

        # 3. รับค่าจาก Request
        new_status = request.data.get('status')
        teacher_note = request.data.get('teacher_note', '')

        # 4. Validation: ตรวจสอบค่า Status ที่ส่งมา
        if new_status not in [JobApplication.Status.APPROVED, JobApplication.Status.REJECTED]:
            return Response(
                {"detail": "สถานะไม่ถูกต้อง (ต้องเป็น APPROVED หรือ REJECTED เท่านั้น)"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Logic สำคัญ: ป้องกันการอนุมัติงานซ้อน
        # ถ้านักศึกษาคนนี้มีงานอื่นที่เป็น APPROVED อยู่แล้ว จะอนุมัติงานนี้เพิ่มไม่ได้
        if new_status == JobApplication.Status.APPROVED:
            has_active_job = JobApplication.objects.filter(
                student=job.student,
                status=JobApplication.Status.APPROVED
            ).exclude(pk=pk).exists() # exclude ตัวเองออก (เผื่อกดย้ำ)

            if has_active_job:
                return Response(
                    {"detail": "ไม่สามารถอนุมัติได้ เนื่องจากนักศึกษาคนนี้มีงานที่ 'อนุมัติ' อยู่แล้วในระบบ (ต้องให้นักศึกษายกเลิกงานเก่าก่อน)"},
                    status=status.HTTP_409_CONFLICT
                )

        # 6. บันทึกข้อมูล
        job.status = new_status
        job.teacher_note = teacher_note
        job.save()

        # 7. ส่งข้อมูลล่าสุดกลับไป
        serializer = JobApplicationSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class VerifyReportListView(APIView):
    """
    API สำหรับอาจารย์ดูรายการรายงานประจำสัปดาห์ (Weekly Reports)
    - ใช้สำหรับอ่านความก้าวหน้าและกด 'รับทราบ' (Acknowledge)
    - Default: แสดงเฉพาะ PENDING (ยังไม่ได้รับทราบ)
    - Option: ?status=ALL (ดูย้อนหลังทั้งหมด), ?student_id=123 (ดูเฉพาะคน)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Query Params
        status_filter = request.query_params.get('status', 'PENDING')
        student_id_filter = request.query_params.get('student_id') # เผื่ออยากเจาะจงดูรายคน

        # 3. Base Query
        # ใช้ select_related ข้ามไปหา Job -> Student และ Job -> Company เพื่อลด Query
        queryset = WeeklyReport.objects.select_related(
            'job_application', 
            'job_application__student', 
            'job_application__company'
        ).order_by('-submitted_at')

        # 4. Apply Filters
        if status_filter != 'ALL':
            queryset = queryset.filter(status=status_filter)
        
        if student_id_filter:
            queryset = queryset.filter(job_application__student_id=student_id_filter)

        # 5. Construct Response
        results = []
        for report in queryset:
            # ใช้ Serializer แปลงข้อมูล Report
            data = WeeklyReportSerializer(report).data
            
            # ดึง Object ที่เกี่ยวข้องมาใช้งาน (ผ่าน select_related แล้ว ไม่ช้า)
            job = report.job_application
            student = job.student
            
            # Inject ข้อมูลบริบท (Context) เพิ่มเติม
            # อาจารย์ต้องรู้ว่า: ใครส่ง? ฝึกที่ไหน? สัปดาห์ที่เท่าไหร่?
            data['student_info'] = {
                "fullname": f"{student.firstname} {student.lastname}",
                "student_code": student.student_code,
                "major": student.major
            }
            
            data['job_info'] = {
                "company_name": job.company_name_snapshot,
                "position": job.position
            }

            results.append(data)

        return Response(results, status=status.HTTP_200_OK)
    

class VerifyReportUpdateView(APIView):
    """
    API สำหรับอาจารย์บันทึกการรับทราบหรือให้ความเห็นต่อรายงาน (FR-09)
    - Method: PUT
    - หน้าที่: เปลี่ยนสถานะเป็น 'ACKNOWLEDGED' และบันทึกข้อเสนอแนะ (Teacher Comment)
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. ดึงรายงานที่ต้องการตอบกลับ
        report = get_object_or_404(WeeklyReport, pk=pk)

        # 3. รับค่าจาก Request
        # อาจารย์ส่ง status='ACKNOWLEDGED' มาเพื่อยืนยันว่าอ่านแล้ว
        new_status = request.data.get('status')
        teacher_comment = request.data.get('teacher_comment')

        # 4. Update Data
        # อัปเดตสถานะ (ถ้ามีการส่งค่ามา)
        if new_status:
            if new_status not in [WeeklyReport.Status.PENDING, WeeklyReport.Status.ACKNOWLEDGED]:
                 return Response({"detail": "สถานะไม่ถูกต้อง"}, status=status.HTTP_400_BAD_REQUEST)
            report.status = new_status

        # อัปเดตความเห็นอาจารย์ (ถ้ามีการส่งค่ามา)
        if teacher_comment is not None:
            report.teacher_comment = teacher_comment

        # 5. Save
        report.save()

        # 6. Return Updated Data
        serializer = WeeklyReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class TeacherCompanySummaryView(APIView):
    """
    API สำหรับอาจารย์ดูสรุปข้อมูลสถานประกอบการ (Company Dashboard)
    - แสดงรายชื่อบริษัททั้งหมดที่มีในระบบ
    - แสดงจำนวนนักศึกษาที่กำลังฝึกงานอยู่ (Active Students) ในแต่ละบริษัท
    - ใช้สำหรับวางแผนนิเทศงาน (บริษัทไหนเด็กเยอะ ต้องไปเยี่ยมก่อน)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Search (เผื่อค้นหาบริษัท)
        search_query = request.query_params.get('search', '')

        # 3. Query & Aggregation (หัวใจสำคัญ)
        # เราจะดึง CompanyMaster และ "นับ" จำนวน JobApplication ที่สถานะเป็น APPROVED ของบริษัทนั้นๆ
        companies = CompanyMaster.objects.annotate(
            active_student_count=Count(
                'job_applications', 
                filter=Q(job_applications__status=JobApplication.Status.APPROVED)
            )
        )

        # 4. Filter Search
        if search_query:
            companies = companies.filter(company_name__icontains=search_query)

        # 5. Ordering
        # เรียงตามจำนวนนักศึกษา (มากไปน้อย) เพื่อให้เห็นบริษัทที่เป็น Partner หลักก่อน
        companies = companies.order_by('-active_student_count', 'company_name')

        # 6. Construct Data
        results = []
        for comp in companies:
            # ดึงรายชื่อนักศึกษาในบริษัทนี้ (เฉพาะคนที่ Approved) มาใส่ list ย่อย (เผื่ออาจารย์กดดู)
            # ใช้ prefetch_related จะดีกว่าถ้าข้อมูลเยอะ แต่เพื่อความง่ายใน logic นี้ใช้ query set ปกติ
            active_jobs = comp.job_applications.filter(status=JobApplication.Status.APPROVED).select_related('student')
            
            student_list = []
            for job in active_jobs:
                student_list.append({
                    "id": job.student.id,
                    "fullname": f"{job.student.firstname} {job.student.lastname}",
                    "position": job.position
                })

            results.append({
                "id": comp.id,
                "company_name": comp.company_name,
                "address": comp.address,
                "contact_person": comp.contact_person,
                "contact_phone": comp.contact_phone,
                "stats": {
                    "active_students": comp.active_student_count,
                },
                "student_list": student_list # รายชื่อเด็กที่ฝึกอยู่ที่นี่
            })

        return Response(results, status=status.HTTP_200_OK)
    

class TeacherCompanyCommentView(APIView):
    """
    API สำหรับอาจารย์บันทึก 'Note ส่วนตัว' ลงในข้อมูลบริษัท (Internal Knowledge Base)
    - Method: PATCH (แก้ไขข้อมูลบางส่วน)
    - ใช้สำหรับ: Note ข้อมูลเชิงลึกที่ไม่อยากให้คนนอกรู้ เช่น "HR ดุแต่ใจดี", "ควรส่ง นศ. เกรด 3.00 ขึ้นไป"
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. ดึงข้อมูลบริษัท
        company = get_object_or_404(CompanyMaster, pk=pk)

        # 3. รับค่า Note จาก Request
        # ใช้ key ว่า 'teacher_notes' หรือ 'comment' ตามที่ตกลงกับ Frontend
        notes = request.data.get('teacher_comments')

        if notes is None:
            return Response({"detail": "กรุณาส่งข้อมูล teacher_notes มาด้วย"}, status=status.HTTP_400_BAD_REQUEST)

        # 4. บันทึกข้อมูล
        company.teacher_commnets = notes
        company.save()

        # 5. Return Updated Data
        # ส่งข้อมูลกลับไปเพื่อให้ Frontend อัปเดต UI ทันที
        return Response({
            "id": company.id,
            "company_name": company.company_name,
            "teacher_notes": company.teacher_comments,
            "message": "บันทึกข้อมูลเรียบร้อยแล้ว"
        }, status=status.HTTP_200_OK)
    

class TeacherEvaluationListView(APIView):
    """
    API สำหรับอาจารย์ดูรายการผลประเมินการฝึกงาน (Evaluation List)
    - แสดงคะแนนรวม, จุดแข็ง/จุดอ่อน
    - ใช้สำหรับตัดเกรด หรือกดรับทราบผลการประเมิน
    - Default: แสดงทั้งหมด (เรียงตามวันที่ประเมินล่าสุด)
    - Filter: ?status=PENDING (ดูเฉพาะที่ยังไม่ได้รับทราบ)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Query Params
        status_filter = request.query_params.get('status') # 'PENDING' or None
        search_query = request.query_params.get('search')  # ค้นหาชื่อ นศ.

        # 3. Base Query
        # Join ตาราง Evaluation -> Job -> Student และ Company
        queryset = Evaluation.objects.select_related(
            'job_application',
            'job_application__student',
            'job_application__company'
        ).order_by('-evaluated_at')

        # 4. Apply Filters
        if status_filter == 'PENDING':
            queryset = queryset.filter(teacher_ack_status='PENDING')

        if search_query:
            queryset = queryset.filter(
                Q(job_application__student__firstname__icontains=search_query) |
                Q(job_application__student__lastname__icontains=search_query) |
                Q(job_application__student__student_code__icontains=search_query)
            )

        # 5. Construct Response Data
        results = []
        for eval_obj in queryset:
            job = eval_obj.job_application
            student = job.student
            
            # ใช้ Serializer พื้นฐานสำหรับข้อมูล Evaluation
            eval_data = EvaluationSerializer(eval_obj).data
            
            # Inject ข้อมูลสำคัญสำหรับ Display ในตาราง
            eval_data['student_info'] = {
                "fullname": f"{student.firstname} {student.lastname}",
                "student_code": student.student_code,
                "major": student.major
            }
            
            eval_data['job_info'] = {
                "company_name": job.company_name_snapshot,
                "position": job.position,
                "supervisor_name": job.supervisor_name
            }

            results.append(eval_data)

        return Response(results, status=status.HTTP_200_OK)


class TeacherEvaluationUpdateView(APIView):
    """
    API สำหรับอาจารย์กด 'รับทราบ' ผลการประเมิน (FR-18)
    - Method: PUT
    - หน้าที่: เปลี่ยนสถานะ teacher_ack_status เป็น 'ACKNOWLEDGED'
    - ใช้เมื่ออาจารย์อ่านผลประเมินแล้ว และต้องการ Mark ว่า "ตรวจแล้ว"
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        user = request.user

        # 1. ตรวจสอบสิทธิ์อาจารย์
        if user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. ดึงข้อมูลการประเมิน
        evaluation = get_object_or_404(Evaluation, pk=pk)

        # 3. รับค่าจาก Request (ถ้ามี) หรือ Default เป็น ACKNOWLEDGED
        # ส่วนใหญ่อาจารย์จะกดปุ่ม "รับทราบ" เฉยๆ เราเลย Set Default ให้เลยเพื่อความสะดวก
        new_status = request.data.get('teacher_ack_status', 'ACKNOWLEDGED')

        # 4. Validation
        if new_status not in ['PENDING', 'ACKNOWLEDGED']:
            return Response({"detail": "สถานะไม่ถูกต้อง"}, status=status.HTTP_400_BAD_REQUEST)

        # 5. Update & Save
        evaluation.teacher_ack_status = new_status
        evaluation.save()

        # 6. Return Data
        serializer = EvaluationSerializer(evaluation)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class CompanyStudentListView(APIView):
    """
    API สำหรับ 'พี่เลี้ยง' (Supervisor) ดูรายชื่อเด็กฝึกงานในสังกัดตัวเอง
    - ไม่ต้องส่ง ID บริษัท (ระบบดึงจาก User ที่ Login)
    - แสดงสถานะการส่งรายงาน และสถานะการประเมิน
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 1. ตรวจสอบว่าเป็น User ฝั่งบริษัทหรือไม่
        if user.role != 'COMPANY':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะเจ้าหน้าที่บริษัทเท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. หาบริษัทของ User คนนี้
        # สมมติว่ามีการผูก Profile ไว้แบบ OneToOne: User <-> CompanyProfile <-> CompanyMaster
        try:
            # หากไม่มี CompanyProfile ให้แก้บรรทัดนี้ตาม Logic ของคุณ
            my_company = user.company_profile.company 
        except AttributeError:
            return Response({"detail": "บัญชีผู้ใช้นี้ไม่ได้ผูกกับข้อมูลบริษัทใดๆ"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Query หานักศึกษาที่กำลังฝึกงาน (APPROVED) ในบริษัทนี้
        active_jobs = JobApplication.objects.filter(
            company=my_company,
            status=JobApplication.Status.APPROVED
        ).select_related('student').order_by('student__firstname')

        # 4. Construct Data
        results = []
        for job in active_jobs:
            student = job.student
            
            # นับจำนวนรายงานที่ส่งมา (อาจจะแยกเป็น อ่านแล้ว/ยังไม่อ่าน)
            report_stats = WeeklyReport.objects.filter(job_application=job).aggregate(
                total=Count('id'),
                unread=Count('id', filter=Q(status='PENDING')) # สมมติว่าพี่เลี้ยงต้องอ่าน
            )

            # เช็คว่าประเมินผลไปหรือยัง (Evaluation)
            is_evaluated = Evaluation.objects.filter(job_application=job).exists()

            results.append({
                "job_id": job.id, # สำคัญ: ใช้ ID นี้สำหรับ Link ไปหน้าอ่านรายงาน/ประเมินผล
                "student_info": {
                    "fullname": f"{student.firstname} {student.lastname}",
                    "student_code": student.student_code,
                    "major": student.major,
                    "phone": student.phone,
                    "email": student.email
                },
                "position": job.position,
                "duration": {
                    "start": job.start_date,
                    "end": job.end_date
                },
                "status_summary": {
                    "reports_total": report_stats['total'],
                    "reports_unread": report_stats['unread'], # แจ้งเตือนพี่เลี้ยงว่ามีงานค้าง
                    "is_evaluated": is_evaluated
                }
            })

        return Response({
            "company_name": my_company.company_name,
            "interns": results
        }, status=status.HTTP_200_OK)
    

class CompanyEvaluationCreateView(APIView):
    """
    API สำหรับพี่เลี้ยง (Company) ประเมินผลนักศึกษา (FR-10)
    - Method: POST
    - รับค่า: job_id, scores (รายข้อ), strengths, weaknesses
    - Logic:
      1. ตรวจสอบว่าเป็นเด็กในสังกัดตัวเองจริงไหม
      2. ตรวจสอบว่าเคยประเมินไปหรือยัง (ห้ามประเมินซ้ำ)
      3. คำนวณคะแนนรวม (Total Score) อัตโนมัติ
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # 1. ตรวจสอบสิทธิ์ (ต้องเป็น Company User)
        if user.role != 'COMPANY':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะเจ้าหน้าที่บริษัทเท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        # 2. รับค่า Job ID ที่ต้องการประเมิน
        job_id = request.data.get('job_application_id')
        if not job_id:
             return Response({"detail": "กรุณาระบุ ID ของใบสมัครงาน (job_application_id)"}, status=status.HTTP_400_BAD_REQUEST)

        job = get_object_or_404(JobApplication, pk=job_id)

        # 3. Security Check: เด็กคนนี้ฝึกอยู่ที่บริษัทของ User นี้จริงหรือไม่?
        try:
            # สมมติว่า User ผูกกับ CompanyProfile -> CompanyMaster
            my_company = user.company_profile.company
            if job.company != my_company:
                return Response({"detail": "คุณไม่มีสิทธิ์ประเมินนักศึกษาต่างบริษัท"}, status=status.HTTP_403_FORBIDDEN)
        except AttributeError:
             return Response({"detail": "บัญชีของคุณยังไม่ได้ผูกข้อมูลบริษัท"}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Check Duplicate: เคยประเมินไปแล้วหรือยัง?
        if Evaluation.objects.filter(job_application=job).exists():
            return Response({"detail": "นักศึกษาคนนี้ได้รับการประเมินไปแล้ว ไม่สามารถประเมินซ้ำได้"}, status=status.HTTP_409_CONFLICT)

        # 5. เตรียมข้อมูลสำหรับ Save
        data = request.data.copy()
        data['job_application'] = job.id # Force ใส่ Job ID ที่ผ่านการตรวจสอบแล้ว
        
        # --- Logic การคำนวณคะแนนรวม (Total Score) ---
        # สมมติว่า Frontend ส่งคะแนนย่อยมา เช่น part1_score, part2_score
        # เราควรบวกกันที่ Backend เพื่อความถูกต้อง
        try:
            p1 = float(data.get('part1_score', 0)) # คะแนนความประพฤติ
            p2 = float(data.get('part2_score', 0)) # คะแนนการทำงาน
            p3 = float(data.get('part3_score', 0)) # คะแนนทักษะเฉพาะทาง
            
            total_score = p1 + p2 + p3
            data['total_score'] = total_score
        except ValueError:
            return Response({"detail": "รูปแบบคะแนนไม่ถูกต้อง"}, status=status.HTTP_400_BAD_REQUEST)
        # ---------------------------------------------

        # 6. Save Data (ใช้ Transaction เพื่อความชัวร์)
        with transaction.atomic():
            serializer = EvaluationSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                
                # (Optional) เมื่อประเมินเสร็จ อาจจะเปลี่ยนสถานะ Job เป็น 'COMPLETED' (จบการฝึกงาน) โดยอัตโนมัติ
                # job.status = 'COMPLETED' 
                # job.save()
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

class CompanyEvaluationDetailView(APIView):
    """
    API สำหรับพี่เลี้ยง (Company) ดูและแก้ไขผลการประเมิน
    - Method GET: ดูรายละเอียด
    - Method PUT: แก้ไขผลการประเมิน (ทำได้เฉพาะตอนที่อาจารย์ยังไม่กดรับทราบ)
    """
    permission_classes = [IsAuthenticated]

    def get_object_and_check_permission(self, request, pk):
        """ Helper method เพื่อลด code ซ้ำ และเช็คสิทธิ์ """
        user = request.user
        
        # 1. เช็คว่าเป็น Company User
        if user.role != 'COMPANY':
            return None, Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะเจ้าหน้าที่บริษัทเท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        evaluation = get_object_or_404(Evaluation, pk=pk)

        # 2. เช็คว่าเป็นเด็กฝึกงานของบริษัทเราจริงไหม
        try:
            my_company = user.company_profile.company
            if evaluation.job_application.company != my_company:
                return None, Response({"detail": "คุณไม่มีสิทธิ์เข้าถึงผลประเมินของบริษัทอื่น"}, status=status.HTTP_403_FORBIDDEN)
        except AttributeError:
             return None, Response({"detail": "บัญชีของคุณยังไม่ได้ผูกข้อมูลบริษัท"}, status=status.HTTP_400_BAD_REQUEST)
             
        return evaluation, None

    def get(self, request, pk):
        evaluation, error_response = self.get_object_and_check_permission(request, pk)
        if error_response: return error_response

        # Construct Response
        serializer = EvaluationSerializer(evaluation)
        data = serializer.data

        # Inject Context Info
        job = evaluation.job_application
        student = job.student
        data['context_info'] = {
            "student_fullname": f"{student.firstname} {student.lastname}",
            "student_code": student.student_code,
            "position": job.position,
            "can_edit": (evaluation.teacher_ack_status == 'PENDING') # บอก Frontend ว่าปุ่ม Edit ควร Disable หรือไม่
        }

        return Response(data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        evaluation, error_response = self.get_object_and_check_permission(request, pk)
        if error_response: return error_response

        # --- LOGIC สำคัญ: ห้ามแก้ถ้าอาจารย์รับทราบแล้ว ---
        if evaluation.teacher_ack_status != 'PENDING':
            return Response(
                {"detail": "ไม่สามารถแก้ไขได้ เนื่องจากอาจารย์ได้รับทราบผลการประเมินนี้ไปแล้ว"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        # -------------------------------------------------

        # เตรียมข้อมูลสำหรับ Update
        data = request.data.copy()
        
        # คำนวณคะแนนรวมใหม่ (ถ้ามีการส่งคะแนนใหม่มา)
        # หมายเหตุ: ควรใช้ Logic เดียวกับ CreateView
        try:
            # ดึงค่าเดิมมาเป็น Default ถ้าไม่ได้ส่งค่าใหม่มา
            p1 = float(data.get('part1_score', evaluation.part1_score)) 
            p2 = float(data.get('part2_score', evaluation.part2_score))
            p3 = float(data.get('part3_score', evaluation.part3_score))
            
            total_score = p1 + p2 + p3
            data['total_score'] = total_score
        except ValueError:
            return Response({"detail": "รูปแบบคะแนนไม่ถูกต้อง"}, status=status.HTTP_400_BAD_REQUEST)

        # Update Data
        serializer = EvaluationSerializer(evaluation, data=data, partial=True) # partial=True อนุญาตให้ส่งมาแค่บาง field
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class AnnouncementListView(APIView):
    """
    API สำหรับจัดการประกาศข่าวสาร
    - GET: ดูรายการประกาศ (ทุกคนดูได้)
    - POST: สร้างประกาศใหม่ (เฉพาะอาจารย์)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] # รองรับการอัปโหลดไฟล์

    def get(self, request):
        user = request.user

        # 1. Base Query
        queryset = Announcement.objects.all()

        # 2. Permission Logic: ใครเห็นอะไรได้บ้าง?
        if user.role != 'TEACHER':
            # นักศึกษา/บริษัท เห็นเฉพาะที่ "Published" แล้วเท่านั้น
            queryset = queryset.filter(is_published=True)

        # 3. Ordering
        # เรียง "ปักหมุด" ไว้บนสุด, ตามด้วย "วันที่สร้างล่าสุด"
        queryset = queryset.order_by('-is_pinned', '-created_at')

        # 4. Search (Optional)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search)

        # 5. Return
        serializer = AnnouncementSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # เฉพาะอาจารย์เท่านั้นที่สร้างประกาศได้
        if request.user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง เฉพาะอาจารย์เท่านั้น"}, status=status.HTTP_403_FORBIDDEN)

        serializer = AnnouncementSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnnouncementDetailView(APIView):
    """
    API สำหรับจัดการประกาศรายตัว
    - GET: ดูรายละเอียด
    - PUT/PATCH: แก้ไข (เฉพาะอาจารย์)
    - DELETE: ลบ (เฉพาะอาจารย์)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        
        # Security: ถ้านักศึกษาพยายามเข้าถึง Link ของประกาศที่เป็น Draft (ยังไม่ publish) ต้องกันไว้
        if request.user.role != 'TEACHER' and not announcement.is_published:
             return Response({"detail": "ไม่พบประกาศนี้ หรือประกาศยังไม่เผยแพร่"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AnnouncementSerializer(announcement)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        # เฉพาะอาจารย์
        if request.user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง"}, status=status.HTTP_403_FORBIDDEN)

        announcement = get_object_or_404(Announcement, pk=pk)
        
        # รองรับ Partial Update (PATCH) ในตัว
        serializer = AnnouncementSerializer(announcement, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # เฉพาะอาจารย์
        if request.user.role != 'TEACHER':
            return Response({"detail": "สิทธิ์ไม่ถูกต้อง"}, status=status.HTTP_403_FORBIDDEN)

        announcement = get_object_or_404(Announcement, pk=pk)
        announcement.delete()
        return Response({"detail": "ลบประกาศเรียบร้อยแล้ว"}, status=status.HTTP_204_NO_CONTENT)