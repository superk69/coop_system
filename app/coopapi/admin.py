from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import models
from django import forms
from .models import (
    User, CompanyMaster, Student, Teacher, CompanyRepresentative,
    TrainingRecord, JobApplication, WeeklyReport, Evaluation,
    Announcement,Document
)

# ==========================================
# 1. Custom User Admin & Inlines
# ==========================================

# สร้าง Inline เพื่อให้แก้ไข Profile ได้ในหน้า User ทันที
class StudentInline(admin.StackedInline):
    model = Student
    can_delete = False
    verbose_name_plural = 'ข้อมูลนักศึกษา'
    fk_name = 'user'

class TeacherInline(admin.StackedInline):
    model = Teacher
    can_delete = False
    verbose_name_plural = 'ข้อมูลอาจารย์'
    fk_name = 'user'

class CompanyRepInline(admin.StackedInline):
    model = CompanyRepresentative
    can_delete = False
    verbose_name_plural = 'ข้อมูลตัวแทนบริษัท'
    fk_name = 'user'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """ปรับแต่ง User Admin ให้แสดง Role และ Profile ตามประเภท"""
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
    
    # เพิ่ม field role เข้าไปในหน้าแก้ไข
    fieldsets = UserAdmin.fieldsets + (
        ('ข้อมูลเพิ่มเติม', {'fields': ('role',)}),
    )

    # Logic เลือกแสดง Inline ตาม Role (Optional: ถ้าอยากให้โชว์ทั้งหมดก็ใส่ไปเลย)
    inlines = [StudentInline, TeacherInline, CompanyRepInline]

# ==========================================
# 2. Master Data Admin
# ==========================================

@admin.register(CompanyMaster)
class CompanyMasterAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'contact_person', 'contact_phone', 'updated_at')
    search_fields = ('company_name', 'contact_person')
    list_filter = ('updated_at',)
    
    # ช่องเก็บความเห็นอาจารย์ให้กว้างหน่อย
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 4, 'cols': 80})},
    }

# ==========================================
# 3. Profiles Admin (แยกดูรายตารางได้ด้วย)
# ==========================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_code', 'firstname', 'lastname', 'major')
    search_fields = ('student_code', 'firstname', 'lastname')
    list_filter = ('major',)
    autocomplete_fields = ['user'] # ช่วยให้ค้นหา User ได้ง่ายกรณีมี User เยอะ

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('firstname', 'lastname')
    search_fields = ('firstname', 'lastname')

@admin.register(CompanyRepresentative)
class CompanyRepAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'display_company_name')
    search_fields = ('user__username', 'company__company_name')
    autocomplete_fields = ['company'] # ค้นหาบริษัทจาก Master ได้ง่าย

# ==========================================
# 4. Training Module Admin
# ==========================================

@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ('topic_name', 'student', 'status', 'requested_hours', 'approved_hours', 'submitted_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('topic_name', 'student__firstname', 'student__student_code')
    
    # จัดกลุ่ม Field
    fieldsets = (
        ('ข้อมูลการอบรม', {
            'fields': ('student', 'topic_name', 'proof_file', 'requested_hours')
        }),
        ('ส่วนตรวจสอบ (อาจารย์)', {
            'fields': ('status', 'approved_hours', 'teacher_note', 'checked_at')
        }),
    )

# ==========================================
# 5. Job Application & Inlines
# ==========================================

class WeeklyReportInline(admin.TabularInline):
    """แสดงรายการรายงานรายสัปดาห์ภายใต้ใบสมัครงาน"""
    model = WeeklyReport
    extra = 0 # ไม่ต้องโชว์แถวว่าง
    fields = ('week_number', 'status', 'submitted_at')
    readonly_fields = ('submitted_at',)
    show_change_link = True # ให้กดเข้าไปดูรายละเอียดได้

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('student', 'company_name_snapshot', 'position', 'status', 'academic_year', 'semester')
    list_filter = ('status', 'academic_year', 'semester', 'start_date')
    search_fields = ('student__firstname', 'company_name_snapshot')
    
    # แสดงรายงานที่เกี่ยวข้องในหน้า Job เลย
    inlines = [WeeklyReportInline]
    
    fieldsets = (
        ('ข้อมูลหลัก', {
            'fields': ('student', 'company', 'status')
        }),
        ('ข้อมูล Snapshot (ณ วันสมัคร)', {
            'fields': ('company_name_snapshot', 'position', 'company_location', 
                       'supervisor_name', 'supervisor_phone')
        }),
        ('ข้อมูลเพิ่มเติม', {
            'fields': ('accommodation', 'emergency_contact_name', 'emergency_contact_phone')
        }),
        ('ระยะเวลา', {
            'fields': ('start_date', 'end_date', 'academic_year', 'semester')
        }),
        ('ส่วนตรวจสอบ', {
            'fields': ('teacher_note',)
        })
    )

# ==========================================
# 6. Weekly Report Admin
# ==========================================

@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ('job_application', 'week_number', 'status', 'submitted_at')
    list_filter = ('status', 'week_number')
    search_fields = ('job_application__student__firstname',)
    readonly_fields = ('submitted_at',)

# ==========================================
# 7. Evaluation Admin (JSON Support)
# ==========================================

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('job_application', 'total_score', 'teacher_ack_status', 'evaluated_at')
    list_filter = ('teacher_ack_status',)
    search_fields = ('job_application__student__firstname', 'job_application__company_name_snapshot')
    
    # JSONField จะแสดงเป็น Text Editor ปกติใน Django Admin 
    # (ถ้าใช้ Django 3.1+ จะมี Widget สวยๆ ให้เลย)
    fieldsets = (
        ('ข้อมูลทั่วไป', {
            'fields': ('job_application', 'evaluator', 'teacher_ack_status')
        }),
        ('คะแนนและข้อมูลละเอียด', {
            'fields': ('total_score', 'evaluation_data')
        }),
        ('ความคิดเห็น', {
            'fields': ('strengths', 'weaknesses', 'comments')
        }),
    )

# ==========================================
# 8. News & Docs Admin
# ==========================================

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'content')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'teacher', 'uploaded_at')
    search_fields = ('file_name',)