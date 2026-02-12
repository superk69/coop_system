from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ===========================================
    # 1. Authentication System (Fullstack Style)
    # ===========================================
    # ใช้ Built-in Views ของ Django จัดการเรื่อง Login/Logout/Password Reset ได้เลย
    # (ต้องมี folder templates/registration/ หรือกำหนด template_name เอง)
    
    path('auth/login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('auth/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('auth/register/', views.RegisterView.as_view(), name='register'), # Custom View ของเรา

    # Password Reset Flow (Optional)
    path('auth/password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('auth/password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('auth/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('auth/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),


    # ===========================================
    # 2. Student System
    # ===========================================
    # ปรับ URL ให้สั้นลงและสื่อความหมายในมุมมอง Page
    
    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student-dashboard'),
    
    # รวมการดูและแก้ไขโปรไฟล์ไว้ในหน้าเดียวกัน หรือแยก view ถ้าซับซ้อน
    path('student/profile/', views.StudentProfileView.as_view(), name='student-profile'),
    
    # GET: ดูประวัติ, POST: ส่งฟอร์ม (ในหน้าเดียวกัน)
    path('student/training/', views.StudentTrainingView.as_view(), name='student-training'),
    
    # GET: ดูสถานะ, POST: ส่งใบสมัคร
    path('student/job/', views.StudentJobView.as_view(), name='student-job'),
    
    # GET: ประวัติรายงาน, POST: สร้างรายงานใหม่
    path('student/report/', views.StudentReportView.as_view(), name='student-report'),


    # ===========================================
    # 3. Teacher System
    # ===========================================
    
    path('teacher/dashboard/', views.TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('teacher/companies/', views.TeacherCompanySummaryView.as_view(), name='teacher-company-summary'),
    
    # Drill-down: ดูเด็กในบริษัท
    path('teacher/company/<int:pk>/students/', views.TeacherCompanyStudentListView.as_view(), name='teacher-company-students'),

    # [Action] บันทึก Comment (เปลี่ยนจาก PATCH เป็น POST)
    path('teacher/company/<int:pk>/comment/', views.TeacherCompanyCommentView.as_view(), name='teacher-company-comment'),

    # [Action] ตรวจสอบรายงาน (เปลี่ยนจาก PUT เป็น POST)
    # อาจสร้าง URL แยกสำหรับการกด Approve/Reject โดยเฉพาะ
    path('teacher/report/<int:pk>/verify/', views.TeacherVerifyReportView.as_view(), name='teacher-verify-report'),

    # [Action] อนุมัติใบสมัครงาน
    path('teacher/job/<int:pk>/verify/', views.VerifyJobActionView.as_view(), name='verify-job-action'),
    
    # [Page] ดูผลประเมินทั้งหมด
    path('teacher/evaluations/', views.TeacherEvaluationView.as_view(), name='teacher-evaluation-list'),
    
    # [Action] กดรับทราบผลประเมิน
    path('teacher/evaluation/<int:pk>/ack/', views.TeacherEvaluationAckView.as_view(), name='teacher-evaluation-ack'),


    # ===========================================
    # 4. Company System
    # ===========================================
    
    path('company/dashboard/', views.CompanyStudentListView.as_view(), name='company-dashboard'),
    
    # [Page/Form] ประเมินผล (ระบุ Job ID ที่ต้องการประเมิน)
    path('company/evaluation/create/<int:job_id>/', views.CompanyEvaluationCreateView.as_view(), name='company-evaluation-create'),
    
    # [Page/Form] ดูและแก้ไขผลประเมิน (เปลี่ยนจาก PUT เป็น POST ในการ Update)
    path('company/evaluation/detail/<int:pk>/', views.CompanyEvaluationDetailView.as_view(), name='company-evaluation-detail'),

    
    # ============================================
    # 5. Common / Shared Resources
    # ============================================
    # News & Documents (FR-06, FR-10, FR-11)
    # GET (Student/Teacher), POST (Teacher only)
    path('announcements', views.AnnouncementListView.as_view(), name='announcements'),
    path('announcements/details', views.AnnouncementDetailView.as_view(), name='announcements'),
#    path('documents', views.DocumentView.as_view(), name='documents'),
]