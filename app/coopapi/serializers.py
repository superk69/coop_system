from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import (
    Student, Teacher, CompanyRepresentative, CompanyMaster,
    TrainingRecord, JobApplication, WeeklyReport, Evaluation,
    Announcement, Document
)

User = get_user_model()

# ==========================================
# 1. Authentication & User Serializers
# ==========================================

class UserSerializer(serializers.ModelSerializer):
    """ใช้สำหรับแสดงข้อมูล User ทั่วไป"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name']

class RegisterSerializer(serializers.ModelSerializer):
    """
    FR-01: Serializer สำหรับลงทะเบียนนักศึกษาใหม่
    จัดการสร้างทั้ง User และ Student Profile พร้อมกัน (Atomic Transaction)
    """
    password = serializers.CharField(write_only=True)
    
    # รับข้อมูลส่วนของ Student Profile มาด้วย
    student_code = serializers.CharField(write_only=True)
    firstname = serializers.CharField(write_only=True)
    lastname = serializers.CharField(write_only=True)
    major = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'student_code', 'firstname', 'lastname', 'major']

    def validate_student_code(self, value):
        if Student.objects.filter(student_code=value).exists():
            raise serializers.ValidationError("รหัสนักศึกษานี้มีอยู่ในระบบแล้ว")
        return value

    def create(self, validated_data):
        # แยกข้อมูล User และ Student
        student_data = {
            'student_code': validated_data.pop('student_code'),
            'firstname': validated_data.pop('firstname'),
            'lastname': validated_data.pop('lastname'),
            'major': validated_data.pop('major')
        }
        
        # ใช้ transaction เพื่อให้มั่นใจว่าสร้างได้ทั้งคู่ หรือไม่ได้เลย
        with transaction.atomic():
            # 1. สร้าง User
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                role=User.Role.STUDENT,
                first_name=student_data['firstname'],
                last_name=student_data['lastname']
            )
            
            # 2. สร้าง Student Profile
            Student.objects.create(user=user, **student_data)
            
        return user

class ResetPasswordSerializer(serializers.Serializer):
    """FR-01: รับ Token และรหัสผ่านใหม่"""
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

# ==========================================
# 2. Profile Serializers
# ==========================================

class StudentProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Student
        fields = ['id', 'student_code', 'firstname', 'lastname', 'major', 'email']

class CompanyRepSerializer(serializers.ModelSerializer):
    """ข้อมูลตัวแทนบริษัทและบริษัทที่สังกัด"""
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    
    class Meta:
        model = CompanyRepresentative
        fields = ['id', 'display_company_name', 'company', 'company_name']

# ==========================================
# 3. Master Data (Company KB)
# ==========================================

class CompanyMasterSerializer(serializers.ModelSerializer):
    """FR-19: ข้อมูลบริษัทกลาง (Knowledge Base)"""
    class Meta:
        model = CompanyMaster
        fields = ['id', 'company_name', 'address', 'contact_person', 'contact_phone', 'teacher_comments']
        
    def to_representation(self, instance):
        """ Override เพื่อซ่อน teacher_notes จากนักศึกษา """
        data = super().to_representation(instance)
        request = self.context.get('request', None)
        
        # ถ้าคนเรียกไม่ใช่ Teacher ให้ลบ teacher_comments ออก (Security)
        if request and request.user.role != 'TEACHER':
            data.pop('teacher_comments', None)
        
        return data
# ==========================================
# 4. Training Module Serializers
# ==========================================

class TrainingRecordSerializer(serializers.ModelSerializer):
    """
    FR-07: นักศึกษาบันทึก/ดูการอบรม
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TrainingRecord
        fields = [
            'id', 'topic_name', 'requested_hours', 'proof_file', 
            'approved_hours', 'teacher_note', 'status', 'status_display', 
            'submitted_at'
        ]
        # นักศึกษาไม่ควรแก้ฟิลด์เหล่านี้ได้
        read_only_fields = ['approved_hours', 'teacher_note', 'status', 'submitted_at']

class TrainingVerificationSerializer(serializers.ModelSerializer):
    """
    FR-12: อาจารย์ตรวจสอบการอบรม
    """
    student_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TrainingRecord
        fields = ['id', 'student_name', 'approved_hours', 'teacher_note', 'status']

    def get_student_name(self, obj):
        return f"{obj.student.firstname} {obj.student.lastname}"

# ==========================================
# 5. Job Application Serializers
# ==========================================

class JobApplicationSerializer(serializers.ModelSerializer):
    """
    FR-08: นักศึกษาสมัครงาน (Smart Form)
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    company_master_info = CompanyMasterSerializer(source='company', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'company', 'company_master_info', 'company_name_snapshot', 
            'position', 'company_location', 'supervisor_name', 'supervisor_phone',
            'accommodation', 'emergency_contact_name', 'emergency_contact_phone',
            'start_date', 'end_date', 'status', 'status_display', 'teacher_note'
        ]
        read_only_fields = ['status', 'teacher_note']

    def validate(self, data):
        """ตรวจสอบ Logic เพิ่มเติม เช่น วันที่เริ่มต้องก่อนวันจบ"""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("วันสิ้นสุดการฝึกงานต้องหลังจากวันเริ่มต้น")
        return data

class JobVerificationSerializer(serializers.ModelSerializer):
    """FR-13: อาจารย์ตรวจสอบงาน"""
    student_name = serializers.CharField(source='student.firstname', read_only=True)
    student_code = serializers.CharField(source='student.student_code', read_only=True)

    class Meta:
        model = JobApplication
        fields = ['id', 'student_name', 'student_code', 'status', 'teacher_note']

# ==========================================
# 6. Weekly Report Serializers
# ==========================================

class WeeklyReportSerializer(serializers.ModelSerializer):
    """FR-09: รายงานรายสัปดาห์ (4 หัวข้อ)"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WeeklyReport
        fields = [
            'id', 'week_number', 'work_summary', 'problems_found', 
            'knowledge_gained', 'supervisor_feedback', 'status', 'status_display',
            'submitted_at'
        ]
        read_only_fields = ['status', 'submitted_at']

class ReportVerificationSerializer(serializers.ModelSerializer):
    """FR-14: อาจารย์รับทราบรายงาน"""
    class Meta:
        model = WeeklyReport
        fields = ['id', 'status']

# ==========================================
# 7. Evaluation Serializers
# ==========================================

class EvaluationSerializer(serializers.ModelSerializer):
    """
    FR-17: บริษัทประเมินผล (ละเอียด)
    """
    student_name = serializers.SerializerMethodField()
    teacher_ack_display = serializers.CharField(source='get_teacher_ack_status_display', read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            'id', 'application_id', 'student_name', 'total_score', 
            'evaluation_data', 'strengths', 'weaknesses', 'comments', 
            'teacher_ack_status', 'teacher_ack_display', 'evaluated_at'
        ]
        read_only_fields = ['teacher_ack_status', 'evaluated_at', 'student_name']

    def get_student_name(self, obj):
        return f"{obj.job_application.student.firstname} {obj.job_application.student.lastname}"

    def validate_evaluation_data(self, value):
        """ตรวจสอบว่า JSON Data ถูกต้องหรือไม่ (Optional logic)"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("ข้อมูลการประเมินต้องเป็น JSON Object")
        return value

class EvaluationAckSerializer(serializers.ModelSerializer):
    """FR-15: อาจารย์รับทราบผลประเมิน"""
    class Meta:
        model = Evaluation
        fields = ['id', 'teacher_ack_status']

# ==========================================
# 8. Common Serializers
# ==========================================

class AnnouncementSerializer(serializers.ModelSerializer):
    """FR-06, FR-10: ข่าวประกาศ"""
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'teacher_name', 'created_at']
        read_only_fields = ['teacher_name', 'created_at']

    def get_teacher_name(self, obj):
        return f"อ.{obj.teacher.firstname} {obj.teacher.lastname}"

class DocumentSerializer(serializers.ModelSerializer):
    """FR-11: เอกสารดาวน์โหลด"""
    class Meta:
        model = Document
        fields = ['id', 'file_name', 'file', 'uploaded_at']