from django.urls import path
from . import views

urlpatterns = [
    # ============================================
    # 1. Authentication & Account
    # ============================================
    path('auth/register', views.RegisterView.as_view(), name='auth-register'),
    path('auth/login', views.LoginView.as_view(), name='auth-login'),
    path('auth/forgot-password', views.ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('auth/reset-password', views.ResetPasswordConfirmView.as_view(), name='auth-reset-password'),

    # Admin/Teacher: Manage Company Accounts (FR-04)
#    path('admin/companies', views.AdminCompanyAccountView.as_view(), name='admin-companies-list-create'),
#    path('admin/companies/<int:pk>', views.AdminCompanyAccountDetailView.as_view(), name='admin-companies-detail'),

    # ============================================
    # 2. Student Module
    # ============================================
    # Dashboard (FR-05)
    path('students/me/dashboard', views.StudentDashboardView.as_view(), name='student-dashboard'),
    
    # Training Records (FR-07)
    path('students/me/trainings', views.StudentTrainingView.as_view(), name='student-trainings'),
    
    # Job Application (FR-08, FR-18)
    path('students/me/job-application', views.StudentJobApplicationView.as_view(), name='student-job'),
    path('students/me/job-application/<int:pk>/cancel', views.StudentJobCancelView.as_view(), name='student-job-cancel'),
    
    # Weekly Reports (FR-09)
    path('students/me/reports', views.StudentWeeklyReportView.as_view(), name='student-reports'),

    # ============================================
    # 3. Teacher Module
    # ============================================
    # Student Tracking & Details (FR-16)
    path('teachers/students', views.TeacherStudentListView.as_view(), name='teacher-students-list'),
    path('teachers/students/<int:pk>', views.TeacherStudentDetailView.as_view(), name='teacher-students-detail'),
    
    # Verifications (FR-12, FR-13, FR-14)
    path('teachers/verifications/trainings', views.VerifyTrainingListView.as_view(), name='verify-trainings-list'),
    path('teachers/verifications/trainings/<int:pk>', views.VerifyTrainingUpdateView.as_view(), name='verify-trainings-update'),
    
    path('teachers/verifications/jobs', views.VerifyJobListView.as_view(), name='verify-jobs-list'),
    path('teachers/verifications/jobs/<int:pk>', views.VerifyJobUpdateView.as_view(), name='verify-jobs-update'),
    
    path('teachers/verifications/reports', views.VerifyReportListView.as_view(), name='verify-reports-list'),
    path('teachers/verifications/reports/<int:pk>', views.VerifyReportUpdateView.as_view(), name='verify-reports-update'),

    # Knowledge Base & Summary (FR-19 - V2 New)
    path('teachers/companies/summary', views.TeacherCompanySummaryView.as_view(), name='teacher-company-summary'),
    path('teachers/companies/<int:pk>/comments', views.TeacherCompanyCommentView.as_view(), name='teacher-company-comment'),

    # Evaluation Summary (FR-15)
    path('teachers/evaluations', views.TeacherEvaluationListView.as_view(), name='teacher-evaluations-list'),
    path('teachers/evaluations/<int:pk>/ack', views.TeacherEvaluationUpdateView.as_view(), name='teacher-evaluations-ack'),

    # ============================================
    # 4. Company Module
    # ============================================
    # Dashboard & Student List
    path('companies/me/students', views.CompanyStudentListView.as_view(), name='company-students'),
    
    # Evaluation (FR-17)
    path('companies/me/evaluations', views.CompanyEvaluationCreateView.as_view(), name='company-evaluations-create'),
    path('companies/me/evaluations/<int:pk>', views.CompanyEvaluationDetailView.as_view(), name='company-evaluations-detail'), # รองรับ GET (view) และ PUT (update)

    # ============================================
    # 5. Common / Shared Resources
    # ============================================
    # News & Documents (FR-06, FR-10, FR-11)
    # GET (Student/Teacher), POST (Teacher only)
    path('announcements', views.AnnouncementListView.as_view(), name='announcements'),
    path('announcements/details', views.AnnouncementDetailView.as_view(), name='announcements'),
#    path('documents', views.DocumentView.as_view(), name='documents'),
]