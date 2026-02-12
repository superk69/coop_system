from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

# Import Models ทั้งหมด
from .models import (
    User, Student, CompanyMaster, CompanyProfile,
    TrainingRecord, JobApplication, WeeklyReport, 
    Evaluation, Announcement, AllowedStudent
)

# ==========================================
# 0. Global Settings (ปรับแต่งหน้า Admin)
# ==========================================
admin.site.site_header = "ระบบจัดการสหกิจศึกษา (Internship Admin)"
admin.site.site_title = "Internship System"
admin.site.index_title = "แผงควบคุมหลัก"


# ==========================================
# 1. User & Profiles (จัดการผู้ใช้)
# ==========================================

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """ ปรับแต่ง User Admin ให้โชว์ Role และแก้ไขได้ """
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    # เพิ่ม Field 'role' เข้าไปในหน้าแก้ไข User
    fieldsets = UserAdmin.fieldsets + (
        ('ข้อมูลเพิ่มเติม (Role)', {'fields': ('role',)}),
    )

@admin.register(AllowedStudent)
class AllowedStudentAdmin(admin.ModelAdmin):
    list_display = ['student_code', 'firstname', 'lastname', 'major', 'is_registered']
    search_fields = ['student_code', 'firstname', 'lastname']
    list_filter = ['major', 'is_registered']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_code', 'firstname', 'lastname', 'major', 'gpa', 'phone')
    search_fields = ('student_code', 'firstname', 'lastname', 'major')
    list_filter = ('major',)


class CompanyProfileInline(admin.StackedInline):
    """ แสดง User พี่เลี้ยงที่ผูกกับบริษัทนี้ """
    model = CompanyProfile
    extra = 0
    readonly_fields = ['user']

@admin.register(CompanyMaster)
class CompanyMasterAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'get_staff_count')
    search_fields = ('name', 'contact_person')
    inlines = [CompanyProfileInline] # โชว์พี่เลี้ยงด้านล่าง

    def get_staff_count(self, obj):
        return obj.staffs.count()
    get_staff_count.short_description = "จำนวนพี่เลี้ยง"


# 2. จัดการบัญชีผู้ใช้สถานประกอบการ (Profile)
@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'position', 'phone', 'academic_year')
    list_filter = ('academic_year', 'company')
    search_fields = ('user__username', 'user__first_name', 'company__name')
    autocomplete_fields = ['company', 'user'] # แนะนำให้ใช้ถ้าข้อมูลเยอะ

# ==========================================
# 2. Training System
# ==========================================

@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'topic', 'hours', 'get_hours', 'date', 'status_badge')
    list_filter = ('status', 'date')
    search_fields = ('student__firstname', 'student__student_code', 'topic')
    actions = ['approve_selected_trainings']

    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'APPROVED': 'green',
            'REJECTED': 'red',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_badge.short_description = "สถานะ"

    @admin.action(description='อนุมัติรายการที่เลือก (Batch Approve)')
    def approve_selected_trainings(self, request, queryset):
        queryset.update(status='APPROVED')


# ==========================================
# 3. Job Application & Process (หัวใจหลัก)
# ==========================================

class WeeklyReportInline(admin.TabularInline):
    """ แสดงรายงานรายสัปดาห์ภายในหน้า Job Application """
    model = WeeklyReport
    fields = ('week_number', 'status', 'submitted_at')
    readonly_fields = ('submitted_at',)
    extra = 0
    show_change_link = True # มีปุ่มให้กดเข้าไปดูรายละเอียดลึกๆ ได้

class EvaluationInline(admin.StackedInline):
    """ แสดงผลประเมินภายในหน้า Job Application """
    model = Evaluation
    extra = 0
    show_change_link = True

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('student', 'company', 'position', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'start_date')
    search_fields = ('student__firstname', 'student__student_code', 'company__name')
    
    # ใส่ Inline เพื่อให้ดูภาพรวมของเด็ก 1 คนในที่เดียวได้ครบ (งาน + รายงาน + ประเมิน)
    inlines = [WeeklyReportInline, EvaluationInline]


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'week_number', 'status', 'submitted_at')
    list_filter = ('status', 'week_number')
    search_fields = ('job_application__student__firstname', 'work_summary')

    def get_student(self, obj):
        return obj.job_application.student
    get_student.short_description = "นักศึกษา"


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        'get_student_name', 
        'get_company_name', 
        'total_score', 
        'status', 
        'updated_at'
    )
    
    # ตัวกรองด้านขวา
    list_filter = (
        'status', 
        'job_application__company__name'
    )
    
    # ช่องค้นหา (ค้นชื่อนศ. หรือ ชื่อบริษัท)
    search_fields = (
        'job_application__student__user__first_name',
        'job_application__student__user__last_name',
        'job_application__student__student_code',
        'job_application__company__name'
    )
    
    # ฟิลด์ที่อ่านได้อย่างเดียว (ป้องกัน Admin แก้คะแนนรวมมั่ว)
    readonly_fields = ('total_score', 'updated_at')

    # จัดกลุ่มฟิลด์ในหน้าแก้ไข (สำคัญมาก เพื่อความสวยงาม)
    fieldsets = (
        ('ข้อมูลทั่วไป', {
            'fields': ('job_application', 'status', 'updated_at')
        }),
        ('ส่วนที่ 1: ผลสำเร็จของงาน (15 คะแนน)', {
            'fields': (('q1_1', 'q1_2', 'q1_3'), 'c1_comment'),
            'classes': ('collapse',), # ใส่ collapse เพื่อให้พับเก็บได้เริ่มต้น
        }),
        ('ส่วนที่ 2: ความรู้ความสามารถ (15 คะแนน)', {
            'fields': (('q2_1', 'q2_2', 'q2_3'), 'c2_comment'),
            'classes': ('collapse',),
        }),
        ('ส่วนที่ 3: ความรับผิดชอบ (15 คะแนน)', {
            'fields': (('q3_1', 'q3_2', 'q3_3'), 'c3_comment'),
            'classes': ('collapse',),
        }),
        ('ส่วนที่ 4: ลักษณะส่วนบุคคล (15 คะแนน)', {
            'fields': (('q4_1', 'q4_2', 'q4_3'), 'c4_comment'),
            'classes': ('collapse',),
        }),
        ('ส่วนที่ 5: การมีส่วนร่วมกับองค์กร (15 คะแนน)', {
            'fields': (('q5_1', 'q5_2', 'q5_3'), 'c5_comment'),
            'classes': ('collapse',),
        }),
        ('สรุปผลการประเมิน', {
            'fields': ('strengths', 'weaknesses', 'total_score')
        }),
    )

    # --- Helper Methods สำหรับดึงข้อมูลข้ามตารางมาแสดง ---
    
    def get_student_name(self, obj):
        return f"{obj.job_application.student.student_id} - {obj.job_application.student.user.get_full_name()}"
    get_student_name.short_description = 'นักศึกษา'
    get_student_name.admin_order_field = 'job_application__student__student_id'

    def get_company_name(self, obj):
        return obj.job_application.company_name
    get_company_name.short_description = 'บริษัท'
    
    # บันทึกแล้วคำนวณคะแนนใหม่อัตโนมัติ (เผื่อแก้ใน Admin)
    def save_model(self, request, obj, form, change):
        obj.calculate_total()
        super().save_model(request, obj, form, change)


# ==========================================
# 4. Announcements
# ==========================================

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'is_pinned', 'created_at')
    list_filter = ('is_published', 'is_pinned', 'created_at')
    search_fields = ('title', 'content')
    actions = ['publish_announcements', 'unpublish_announcements']

    @admin.action(description='เผยแพร่ที่เลือก')
    def publish_announcements(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description='ยกเลิกการเผยแพร่ที่เลือก')
    def unpublish_announcements(self, request, queryset):
        queryset.update(is_published=False)