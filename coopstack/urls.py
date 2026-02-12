from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

# กำหนด app_name ช่วยให้เรียก url ใน template ได้ง่าย เช่น {% url 'internship:login' %}
# แต่ถ้าคุณไม่ได้แยกหลาย App ก็เว้นว่างไว้ หรือไม่ใส่ namespace ก็ได้
# ในที่นี้ผมขอไม่ใส่ namespace เพื่อความง่ายครับ

urlpatterns = [
    # ===========================================
    # 0. Home / Landing
    # ===========================================
    # ถ้าเข้ามาหน้าแรก ให้เด้งไปหน้า Login หรือ Dashboard (เขียน Logic ใน views.index หรือ redirect)
    path('', views.index, name='home'), 


    # ===========================================
    # 1. Authentication (ใช้ Built-in Views)
    # ===========================================
    path('auth/login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('auth/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # สมัครสมาชิก (Custom View)
    path('auth/register/', views.RegisterView.as_view(), name='register'),

    # เปลี่ยนรหัสผ่าน (Password Reset) - Optional
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='auth/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='auth/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/token/', auth_views.PasswordResetConfirmView.as_view(template_name='auth/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='auth/password_reset_complete.html'), name='password_reset_complete'),

    # HTMX Routes
    path('htmx/modal/register/', views.get_register_modal, name='get-register-modal'),
    path('htmx/modal/forgot/', views.get_forgot_modal, name='get-forgot-modal'),

    # ===========================================
    # 2. Common / Announcements
    # ===========================================
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement-list'),
    path('announcements/create/', views.AnnouncementCreateView.as_view(), name='announcement-create'), # เฉพาะอาจารย์


    # ===========================================
    # 3. Student System
    # ===========================================
    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student-dashboard'),
    #path('student/profile/', views.StudentProfileView.as_view(), name='student-profile'),
    # Path หน้าข่าวสาร
    path('student/news/', views.StudentNewsView.as_view(), name='student-news'), 
    # Training: รวมดูประวัติและฟอร์มส่งในหน้าเดียว
    path('student/training/', views.StudentTrainingView.as_view(), name='student-training'),
    path('htmx/modal/training/', views.get_training_modal, name='get-training-modal'),
    # Job Application: รวมดูสถานะและฟอร์มสมัคร
    path('student/job/', views.StudentJobView.as_view(), name='student-job'),
    path('student/job/cancel/<int:pk>/', views.cancel_job_application, name='cancel-job-application'),
    path('htmx/job/modal/cancel/<int:pk>/', views.get_cancel_job_modal, name='get-cancel-job-modal'),

    path('htmx/search/company/', views.search_company, name='search-company'),
    # Weekly Report: รวมรายการและฟอร์มส่ง
    path('student/report/', views.StudentWeeklyReportView.as_view(), name='student-report'),
    path('student/report/detail/<int:pk>/', views.ReportDetailView.as_view(), name='report-detail-modal'),

    # ===========================================
    # 4. Teacher System
    # ===========================================
    path('teacher/dashboard/', views.TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('teacher/dashboard/student/<int:student_id>/', views.get_student_detail_modal, name='get-student-detail-modal'),

    # Training Verification
    path('teacher/verify-training/', views.TeacherVerifyTrainView.as_view(), name='teacher-verify-train'),
    path('htmx/training/modal/<int:pk>/', views.get_approve_modal, name='get-approve-modal'),
    path('htmx/training/approve/<int:pk>/', views.approve_training, name='approve-training'),
    path('htmx/training/modal/reject/<int:pk>/', views.get_reject_modal, name='get-reject-modal'),
    path('htmx/training/reject/<int:pk>/', views.reject_training, name='reject-training'),
    # Companies Info
    path('teacher/company-summary/', views.TeacherCompanySummaryView.as_view(), name='teacher-company-summary'),
    path('teacher/company/comment/<int:company_id>/', views.get_company_comment_modal, name='get-company-comment-modal'),
    path('teacher/company/save-comment/<int:company_id>/', views.save_company_comment, name='save-company-comment'),
    # Verification Lists

    path('teacher/verify-job/', views.VerifyJobListView.as_view(), name='teacher-verify-job'),
    path('htmx/job/modal/approve/<int:pk>/', views.get_job_approve_modal, name='get-job-approve-modal'),
    path('htmx/job/approve/<int:pk>/', views.approve_job, name='approve-job'),
    path('htmx/job/modal/reject/<int:pk>/', views.get_job_reject_modal, name='get-job-reject-modal'),
    path('htmx/job/reject/<int:pk>/', views.reject_job, name='reject-job'),
    path('htmx/job/modal/detail/<int:pk>/', views.get_job_detail_modal, name='get-job-detail-modal'),
    # Job Application Verification
    # Weekly Report Verification
    path('teacher/verify-report/', views.TeacherVerifyReportView.as_view(), name='teacher-verify-report'),
    path('htmx/report/modal/<int:pk>/', views.get_report_detail_modal, name='get-report-detail-modal'),
    path('htmx/report/acknowledge/<int:pk>/', views.acknowledge_report, name='acknowledge-report'),

    # Evaluation
    path('teacher/verify-evaluation/', views.TeacherVerifyEvaluationView.as_view(), name='teacher-verify-evaluation'),
    path('htmx/eval/modal/<int:job_id>/', views.get_evaluation_detail_modal, name='get-eval-detail-modal'),
    path('htmx/eval/acknowledge/<int:eval_id>/', views.acknowledge_evaluation, name='acknowledge-evaluation'),

    # Announcements Management
    path('teacher/news/', views.TeacherNewsView.as_view(), name='teacher-news'),
    path('htmx/announcement/create/', views.create_announcement, name='create-announcement'),
    path('htmx/announcement/delete/<int:pk>/', views.delete_announcement, name='delete-announcement'),

    # Company Accounts Management
    path('teacher/company-account/', views.TeacherCompanyAccountView.as_view(), name='teacher-company-account'),
    path('htmx/company/modal/', views.get_account_modal, name='get-account-modal'), # Create
    path('htmx/company/modal/<int:pk>/', views.get_account_modal, name='get-account-modal-edit'), # Edit
    path('htmx/company/save/', views.save_account, name='save-account'), # Save New
    path('htmx/company/save/<int:pk>/', views.save_account, name='update-account'), # Save Edit
    path('htmx/company/delete/<int:pk>/', views.delete_account, name='delete-account'),
    path('htmx/company/auto-gen/', views.auto_generate_accounts, name='auto-gen-accounts'),

    # ===========================================
    # 5. Company System
    # ===========================================
    # 1. หน้าหลักแสดงรายชื่อนักศึกษาในสังกัด (Class-based View)
    path('company/evaluations/', views.CompanyEvaluationListView.as_view(), name='company-evaluation-list'),
    path('company/evaluation/modal/<int:job_id>/', views.get_evaluation_modal, name='get-evaluation-modal'),
    path('company/evaluation/save/<int:job_id>/', views.save_evaluation, name='save-evaluation'),
]