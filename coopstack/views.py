from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Avg, Sum
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from datetime import date, timedelta, datetime
from django.contrib.auth.models import User
import random, string
from .utils import generate_coop_docx

# Imports จากไฟล์ภายใน App ของเรา
from .models import (
    User, Student, CompanyMaster, CompanyProfile,
    TrainingRecord, JobApplication, WeeklyReport, 
    Evaluation, Announcement
)
from .forms import (
    StudentRegisterForm, TrainingRecordForm, 
    JobApplicationForm, WeeklyReportForm, 
    EvaluationForm, AnnouncementForm, 
    TeacherVerifyJobForm, TeacherVerifyReportForm,
    TeacherCompanyCommentForm, StudentRegisterForm
)

# ==============================================================================
# 0. Home & Common Views
# ==============================================================================

def index(request):
    """ หน้าแรก: Redirect ไป Dashboard ตาม Role ของผู้ใช้ """
    if not request.user.is_authenticated:
        return redirect('login')
    
    role = request.user.role
    if role == User.Role.STUDENT:
        return redirect('student-dashboard')
    elif role == User.Role.TEACHER:
        return redirect('teacher-dashboard')
    elif role == User.Role.COMPANY:
        return redirect('company-evaluation-list')
    
    return redirect('login')


class RegisterView(View):
    """ สมัครสมาชิก (เฉพาะนักศึกษา) """
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        form = StudentRegisterForm()
        return render(request, 'partials/register_modal.html', {'form': form})
    def post(self, request):
        form = StudentRegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            allowed_info = data['allowed_student_info'] # ข้อมูลจาก AllowedStudent model
            
            user = User.objects.create_user(
                username=data['student_id'], # ใช้รหัสนักศึกษาเป็น Username
                email=data['email'],
                password=data['password']
            )
            
            user.first_name = allowed_info.firstname
            user.last_name = allowed_info.lastname
            user.save()

            # 2. สร้าง Student Profile
            Student.objects.create(
                user=user,
                student_code=allowed_info.student_code,
                firstname=allowed_info.firstname,
                lastname=allowed_info.lastname,
                major=allowed_info.major, # ดึงสาขามาใส่ให้อัตโนมัติ
                # title=allowed_info.title # ถ้ามี field คำนำหน้า
            )
            
            # 3. อัปเดตสถานะว่าลงทะเบียนแล้ว
            allowed_info.is_registered = True
            allowed_info.save()
            messages.success(request, "สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ")
            return redirect('login') 
        else:
            messages.error(request, "เกิดข้อผิดพลาด กรุณาตรวจสอบข้อมูล")
            return render(request, 'partials/register_modal.html', {'form': form})

def get_register_modal(request):
    """ ส่ง HTML Modal สมัครสมาชิกกลับไป """
    form = StudentRegisterForm()
    return render(request, 'partials/register_modal.html', {'form': form})


def get_forgot_modal(request):
    """ ส่ง HTML Modal ลืมรหัสผ่านกลับไป """
    return render(request, 'partials/forgot_modal.html')


class AnnouncementListView(LoginRequiredMixin, View):
    """ รายการประกาศข่าวสาร (ทุกคนดูได้ แต่อาจารย์เห็นปุ่มสร้าง) """
    def get(self, request):
        if request.user.role == User.Role.TEACHER:
            announcements = Announcement.objects.all()
        else:
            # นศ./บริษัท เห็นเฉพาะที่ Publish แล้ว
            announcements = Announcement.objects.filter(is_published=True)
        
        return render(request, 'common/announcement_list.html', {
            'announcements': announcements
        })

class AnnouncementCreateView(LoginRequiredMixin, View):
    """ สร้างประกาศ (เฉพาะอาจารย์) """
    def get(self, request):
        if request.user.role != User.Role.TEACHER:
            return redirect('announcement-list')
        form = AnnouncementForm()
        return render(request, 'common/announcement_form.html', {'form': form})

    def post(self, request):
        if request.user.role != User.Role.TEACHER:
            return redirect('announcement-list')
        
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "สร้างประกาศเรียบร้อยแล้ว")
            return redirect('announcement-list')
        return render(request, 'common/announcement_form.html', {'form': form})


# ==============================================================================
# 1. Student System
# ==============================================================================

def download_application_form(request, job_id):
    # 1. ดึงข้อมูล
    job_app = get_object_or_404(JobApplication, id=job_id)
    
    # 2. ตรวจสอบสิทธิ์ (เหมือนเดิม)
    if job_app.student.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden("คุณไม่มีสิทธิ์")
    
    if job_app.status != 'APPROVED':
        return HttpResponseForbidden("ต้องผ่านการอนุมัติก่อน")

    # 3. สร้างไฟล์ Word
    docx_buffer = generate_coop_docx(job_app)
    
    # 4. ส่งไฟล์กลับ (Content-Type สำหรับ .docx)
    filename = f"coop_form_{job_app.student.student_code}.docx"
    response = FileResponse(
        docx_buffer, 
        as_attachment=True, 
        filename=filename
    )
    # MIME Type ของ docx
    response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    
    return response

class StudentBaseView(LoginRequiredMixin, View):
    """ Base Class สำหรับตรวจสอบว่าเป็นนักศึกษาจริงไหม """
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != User.Role.STUDENT:
            messages.warning(request, "ไม่มีสิทธิ์เข้าถึงหน้านี้")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class StudentDashboardView(StudentBaseView):
    def get(self, request):
        student = request.user.student_profile
        
        # ข้อมูลสรุป
        job_app = JobApplication.objects.filter(student=student).last()
        training_hours = sum([t.get_hours for t in TrainingRecord.objects.filter(student=student, status='APPROVED')])
        reports_count = WeeklyReport.objects.filter(job_application=job_app).count() if job_app else 0

        step = 1
        status_text = "อยู่ในช่วงเก็บชั่วโมงอบรม"

        # Step 1: ตรวจสอบชั่วโมงอบรม
        if training_hours < 30:
            step = 1
            status_text = f"สะสมชั่วโมงอบรม ({training_hours}/30 ชม.)"
        
        # Step 2: อบรมครบแล้ว -> ตรวจสอบการสมัครงาน
        elif not job_app:
            step = 2
            status_text = "ผ่านเกณฑ์อบรม / รอสมัครงาน"
        else:
            
            if job_app.status == 'PENDING':
                step = 2
                status_text = "ยื่นใบสมัครแล้ว"
            
            elif job_app.status == 'REJECTED':
                step = 2
                status_text = "ไม่อนุมัติ (กรุณาสมัครใหม่)"
            
            elif job_app.status == 'CANCELLED':
                step = 2
                status_text = "ยกเลิก (กรุณาสมัครใหม่)"
            
            elif job_app.status == 'APPROVED':
                step = 3
                status_text = "กำลังปฏิบัติงาน"
            elif job_app.status == 'COMPLETED':
                step = 4
                status_text = "เสร็จสิ้นการฝึกงาน"

        return render(request, 'student/dashboard.html', {
            'student': student,
            'job_app': job_app,
            'training_hours': training_hours,
            'reports_count': reports_count,
            'step': step,
            'current_status_text': status_text,
        })


@login_required
def get_cancel_job_modal(request, pk):
    job = get_object_or_404(JobApplication, pk=pk, student=request.user.student_profile)
    return render(request, 'student/partials/cancel_job_modal.html', {'job': job.pk})


class StudentNewsView(LoginRequiredMixin, View):
    def get(self, request):
        # 1. รายการประกาศทั้งหมด (สำหรับแสดงฝั่งซ้าย)
        # เรียงตาม Pin ก่อน, แล้วค่อยตามวันที่ใหม่สุด
        announcements = Announcement.objects.filter(is_published=True).order_by('-is_pinned', '-created_at')
        
        # 2. รายการที่มีไฟล์แนบ (สำหรับแสดงฝั่งขวา - เอกสารดาวน์โหลด)
        # กรองเอาเฉพาะที่มีไฟล์แนบ
        documents = Announcement.objects.filter(
            is_published=True
        ).exclude(attachment='').order_by('-created_at')
        
        return render(request, 'student/news.html', {
            'announcements': announcements,
            'documents': documents
        })


class StudentTrainingView(StudentBaseView):
    def get(self, request):
        # เรียงลำดับจากใหม่ไปเก่า
        records = TrainingRecord.objects.filter(student=request.user.student_profile).order_by('-date')
        total_hours = records.filter(status='APPROVED').aggregate(Sum('hours'))['hours__sum'] or 0
        form = TrainingRecordForm()
        context = {
            'history_list': records,
            'total_hours': total_hours,
            'form': form
        }
        return render(request, 'student/training.html', context)

    def post(self, request):
        form = TrainingRecordForm(request.POST, request.FILES)
        if form.is_valid():
            training = form.save(commit=False)
            training.student = request.user.student_profile
            # Default Status is PENDING (ตั้งค่าไว้ใน Model แล้ว หรือระบุตรงนี้ก็ได้)
            training.status = 'PENDING' 
            training.save()
            messages.success(request, "บันทึกข้อมูลสำเร็จ รออาจารย์ตรวจสอบ")
            return redirect('student-training')
        
        # กรณี Form Error
        records = TrainingRecord.objects.filter(student=request.user.student_profile).order_by('-date')
        total_hours = records.filter(status='APPROVED').aggregate(Sum('hours'))['hours__sum'] or 0
        context = {
            'history_list': records,
            'total_hours': total_hours,
            'form': form
        }
        messages.error(request, "เกิดข้อผิดพลาด กรุณาตรวจสอบข้อมูล")
        return render(request, 'student/training.html', context)

@login_required
def get_training_modal(request):
    if request.user.role != User.Role.STUDENT:
        return HttpResponseForbidden()
    """ HTMX View: ส่งเฉพาะ HTML Modal """
    form = TrainingRecordForm()
    return render(request, 'partials/training_form_modal.html', {'form': form})


class StudentJobView(StudentBaseView):
    def get(self, request):
        student = request.user.student_profile
        
        # 1. ตรวจสอบชั่วโมงอบรม (Logic ฝั่ง Server)
        total_hours = TrainingRecord.objects.filter(
            student=student, 
            status='APPROVED'
        ).aggregate(Sum('get_hours'))['get_hours__sum'] or 0
        
        REQUIRED_HOURS = 30
        is_training_passed = total_hours >= REQUIRED_HOURS

        # 2. ตรวจสอบสถานะการสมัครงานปัจจุบัน
        # หาใบสมัครล่าสุดที่ไม่ใช่ REJECTED (คือ PENDING, APPROVED, COMPLETED)
        active_job = JobApplication.objects.filter(
            student=student,
            status__in=['PENDING', 'APPROVED','COMPLETED'] # ❌ ไม่รวม CANCELLED, REJECTED
        ).last()
        # เตรียม Form
        form = JobApplicationForm()

        return render(request, 'student/job_application.html', {
            'student': student,
            'is_training_passed': is_training_passed,
            'current_hours': total_hours,
            'required_hours': REQUIRED_HOURS,
            'active_job': active_job,
            'form': form
        })

    def post(self, request):
        student = request.user.student_profile
        
        # Double Check ฝั่ง Server (กันคนยิง API ตรงๆ)
        total_hours = TrainingRecord.objects.filter(student=student, status='APPROVED').aggregate(Sum('get_hours'))['get_hours__sum'] or 0
        if total_hours < 30:
            messages.error(request, "คุณสมบัติไม่ผ่าน: ชั่วโมงอบรมไม่ครบ")
            return redirect('student-job')

        if JobApplication.objects.filter(student=student).exclude(status__in=['REJECTED','CANCELLED']).exists():
            messages.error(request, "คุณมีใบสมัครที่กำลังดำเนินการอยู่แล้ว")
            return redirect('student-job')

        form = JobApplicationForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.student = student
            job.status = 'PENDING'
            job.save()
            messages.success(request, "ส่งใบสมัครเรียบร้อยแล้ว รออาจารย์ตรวจสอบ")
            return redirect('student-job')
        
        # กรณี Form Error ส่งค่าเดิมกลับไป
        return render(request, 'student/job_application.html', {
            'student': student,
            'is_training_passed': True, # สมมติว่าผ่านแล้วถึง Post มาได้
            'form': form
        })


# 2. ฟังก์ชันประมวลผลการยกเลิก
@login_required
def cancel_job_application(request, pk):
    if request.method == "POST":
        # ตรวจสอบว่าเป็นเจ้าของใบสมัครจริง
        job = get_object_or_404(JobApplication, pk=pk, student=request.user.student_profile)
        
        # รับเหตุผล
        reason = request.POST.get('cancel_reason')
        
        # เปลี่ยนสถานะ
        job.status = 'CANCELLED'
        job.cancel_reason = reason
        job.save()
        
        messages.success(request, "ยกเลิกการสมัครงานเรียบร้อยแล้ว คุณสามารถสมัครที่ใหม่ได้")
        
        # return กลับไปที่หน้า Dashboard หรือหน้า Job Status เพื่อรีเฟรชหน้าจอ
        # สมมติว่าใช้ชื่อ view 'student-job-status'
        return redirect('student-job')


@login_required
def search_company(request):
    query = request.GET.get('company_search', '')
    if len(query) >= 2:
        companies = CompanyMaster.objects.filter(name__icontains=query)[:5] # เอาแค่ 5 อันดับแรก
    else:
        companies = []
    
    return render(request, 'partials/company_results.html', {'companies': companies})


class ReportDetailView(StudentBaseView):
    def get(self, request, pk):
        report = get_object_or_404(WeeklyReport, pk=pk)
        # ส่ง HTML รายละเอียดไปใส่ใน Modal Container
        return render(request, 'student/partials/report_detail_modal.html', {'report': report})


class StudentWeeklyReportView(StudentBaseView):
    """ รายการรายงาน + ฟอร์มส่งรายงาน """
    def get(self, request):
        # ต้องมี Job ที่ Approved แล้วถึงจะส่งรายงานได้
        job = JobApplication.objects.filter(student=request.user.student_profile, status__in=['APPROVED', 'COMPLETED']).last()
        
        if not job:
            messages.warning(request, "คุณต้องได้รับการอนุมัติฝึกงานก่อน จึงจะส่งรายงานได้")
            return redirect('student-dashboard')

        reports = WeeklyReport.objects.filter(job_application=job).order_by('week_number')
        form = WeeklyReportForm()
        
        return render(request, 'student/report_list.html', {
            'job': job,
            'reports': reports,
            'next_week_number': reports.count() + 1,
            'form': form
        })
    
    def post(self, request):
        job = JobApplication.objects.filter(student=request.user.student_profile, status__in=['APPROVED', 'COMPLETED']).last()
        if not job:
            return redirect('student-dashboard')

        print(request.POST)
        form = WeeklyReportForm(request.POST)
        if form.is_valid():
            # เช็คว่า Week นี้เคยส่งหรือยัง
            week_num = form.cleaned_data['week_number']
            if WeeklyReport.objects.filter(job_application=job, week_number=week_num).exists():
                messages.error(request, f"รายงานสัปดาห์ที่ {week_num} ถูกส่งไปแล้ว")
                return redirect('student-report')
                #return render(request, 'partials/report_form_modal.html', {'form': form})
            else:
                report = form.save(commit=False)
                report.job_application = job
                report.save()
                messages.success(request, "ส่งรายงานเรียบร้อยแล้ว")
                return redirect('student-report')
        
        messages.error(request, f"รายงานไม่สำเร็จ กรุณาตรวจสอบข้อมูล")
        return redirect('student-report')


# ==============================================================================
# 2. Teacher System
# ==============================================================================

class TeacherBaseView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != User.Role.TEACHER:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class TeacherDashboardView(TeacherBaseView):
    def get(self, request):
        # 1. รับค่า Search และ Filter
        search_query = request.GET.get('q', '')
        year_filter = request.GET.get('year', '')
        
        # 2. Query ข้อมูลพื้นฐาน (สมมติว่าดึงมาทั้งหมดก่อน)
        students = Student.objects.all().order_by('student_code')
        total_count = students.count() 
        coop_count = students.filter(job_applications__status__in=['APPROVED']).count()
        finished_count = students.filter(job_applications__status='COMPLETED').count()
        academic_year = set(students.filter(job_applications__status__in=['APPROVED','COMPLETED']).values_list('job_applications__academic_year', flat=True).distinct())
        academic_year = sorted(academic_year, reverse=True)
        academic_year.append('NONE')

        # 3. การกรอง (Filter)
        if search_query:    
            students = students.filter(
                Q(student_code__icontains=search_query) | 
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query)
            )
        
        if year_filter:
            if year_filter == 'NONE':
                # กรณีเลือก "ยังไม่ได้ฝึกงาน": คัดคนที่ 'มี' Job Approved ออกไป
                students = students.exclude(job_applications__status__in=['APPROVED','COMPLETED'])
            else:
                try:
                    students = students.filter(
                        job_applications__status__in=['APPROVED','COMPLETED'],
                        job_applications__academic_year=year_filter
                    )
                except ValueError:
                    pass # กรณีค่า year ไม่ถูกต้อง
            
        # 4. Pagination (แบ่งหน้า ทีละ 5 คน ตามไฟล์ต้นฉบับ)
        paginator = Paginator(students, 5)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)


        for s in page_obj:
            # 1. ดึงใบสมัครงานล่าสุด
            job = JobApplication.objects.filter(student=s).order_by('-created_at').first()
            s.latest_job = job
            
            # ค่า Default ให้แสดงปีการศึกษาตามทะเบียนนักศึกษาไปก่อน (ถ้ายังไม่มีงาน)
            s.display_year = 'ยังไม่สมัครงาน'
            
            if job:
                s.job_status = job.status
                
                # --- [LOGIC ใหม่] คำนวณปีการศึกษาสำหรับคนที่ APPROVED ---
                if job.status == 'COMPLETED':
                    s.display_year = job.academic_year
                elif job.status == 'APPROVED' and job.start_date:
                    s.display_year = job.academic_year
                    # หา Current Week (เหมือนเดิม)
                    last_report = WeeklyReport.objects.filter(job_application=job).order_by('-week_number').first()
                    s.current_week = last_report.week_number if last_report else 0
                else:
                    s.current_week = 0

            else:
                s.job_status = None


            # B. ดึงชั่วโมงอบรมรวม (ถ้ามี Model TrainingRecord)
            # สมมติว่า TrainingRecord มี field 'total_hours'
            #total_hours = TrainingRecord.objects.filter(student=s).aggregate(Sum('hours'))['hours__sum']
            total_hours = TrainingRecord.objects.filter(
                student=s, 
                status='APPROVED' # (Optional) ควรนับเฉพาะที่สถานะอนุมัติด้วยเพื่อความชัวร์
            ).aggregate(
                sum_val=Sum('get_hours')
            )['sum_val']
            s.training_hours = total_hours if total_hours else 0
        # ====================================================

        context = {
            'students': page_obj,
            'page_obj': page_obj,
            'search_query': search_query,
            'year_filter': year_filter,
            'total_count': total_count,
            'coop_count': coop_count,
            'finished_count': finished_count,
            'academic_year': academic_year
        }

        if request.headers.get('HX-Request'):
            return render(request, 'teacher/partials/student_results.html', context)
        
        return render(request, 'teacher/teacher_dashboard.html', context)


def get_student_detail_modal(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    
    REQUIRED_HOURS = 30
    total_hours = TrainingRecord.objects.filter(student=student, status='APPROVED').aggregate(Sum('hours'))['hours__sum'] or 0
    training_percent = min((total_hours / REQUIRED_HOURS) * 100, 100)

    # 2. ข้อมูลงาน (Job)
    # ดึงใบสมัครล่าสุดที่ได้รับการอนุมัติ หรือใบสมัครล่าสุด
    job = JobApplication.objects.filter(student=student, status__in=['APPROVED', 'COMPLETED']).order_by('-created_at').first()
    if not job:
        job = JobApplication.objects.filter(student=student).order_by('-created_at').first()

    # 3. ข้อมูลรายงาน (Weekly Report) (สมมติเป้าหมายคือ 16 สัปดาห์)
    REQUIRED_WEEKS = 16
    report_count = 0
    if job:
        report_count = WeeklyReport.objects.filter(job_application=job, status='ACKNOWLEDGED').count()
    report_percent = min((report_count / REQUIRED_WEEKS) * 100, 100)

    # 4. ผลประเมิน (Evaluation)
    evaluation = None
    if job:
        evaluation = getattr(job, 'evaluation', None)

    context = {
        's': student,
        'job': job,
        'training': {
            'hours': total_hours,
            'required': REQUIRED_HOURS,
            'percent': int(training_percent)
        },
        'reports': {
            'count': report_count,
            'required': REQUIRED_WEEKS,
            'percent': int(report_percent)
        },
        'eval': evaluation
    }
    
    return render(request, 'teacher/partials/student_detail_modal.html', context)

# ---- company management views ----

def get_company_summary_context(request):
    search_query = request.GET.get('q', '')
    
    companies = CompanyMaster.objects.all().order_by('name')
    all_companies = companies.count()
    
    if search_query:
        companies = companies.filter(Q(name__icontains=search_query)|Q(teacher_notes__icontains=search_query))

    company_list = []
    for comp in companies:
        jobs = JobApplication.objects.filter(company__name__icontains=comp.name, status__in=['APPROVED','COMPLETED'])

        if not jobs.exists() and search_query: 
             pass

        years = jobs.values_list('academic_year', flat=True).distinct().order_by('-academic_year') # รายการปีการศึกษา
        positions = jobs.values_list('position', flat=True).distinct() # รายการตำแหน่ง
        student_count = jobs.count()

        company_list.append({
            'id': comp.id,
            'name': comp.name,
            'address': comp.address or "-",
            'phone': getattr(comp, 'phone', '-'), # ถ้ามี field phone
            'teacher_notes': comp.teacher_notes,
            'years': [y for y in years if y], # กรอง None
            'positions': list(positions),
            'student_count': student_count,
            'has_history': student_count > 0,
        })

    paginator = Paginator(company_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return {
        'page_obj': page_obj,
        'all_companies': all_companies,
        'search_query': search_query
    }


class TeacherCompanySummaryView(TeacherBaseView):
    def get(self, request):
        if request.headers.get('HX-Request') and not request.headers.get('HX-Target') == 'modal-container':
            return render(request, 'teacher/partials/company_summary_list.html', get_company_summary_context(request))
        return render(request, 'teacher/company_summary.html', get_company_summary_context(request))

def get_company_comment_modal(request, company_id):
    company = get_object_or_404(CompanyMaster, pk=company_id)
    return render(request, 'teacher/partials/company_comment_modal.html', {'company': company})

def save_company_comment(request, company_id):
    if request.method == "POST":
        company = get_object_or_404(CompanyMaster, pk=company_id)
        comment = request.POST.get('teacher_notes')
        company.teacher_notes = comment
        company.save()
        
        # ส่งกลับเฉพาะแถวของบริษัทนั้น หรือ รีเฟรชทั้งตาราง
        # เพื่อความง่าย รีเฟรชทั้งตารางผ่าน logic เดิม
        return render(request, 'teacher/partials/company_summary_list.html', get_company_summary_context(request))

# --- Verification Section ---
#---------Training Verification Section ---------
def get_training_context(request):
    search_query = request.GET.get('q', '')
    
    trainings = TrainingRecord.objects.select_related('student__user').all().order_by('-date')

    if search_query:
        trainings = trainings.filter(
            Q(student__firstname__icontains=search_query) |
            Q(student__lastname__icontains=search_query) |
            Q(student__student_code__icontains=search_query) |
            Q(topic__icontains=search_query)
        )
    
    pending_list = trainings.filter(status='PENDING')
    history_queryset = trainings.exclude(status='PENDING')
    
    paginator = Paginator(history_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return {
        'pending_list': pending_list,
        'page_obj': page_obj,
        'search_query': search_query, # ถ้าต้องการคงค่า search อาจต้องรับค่าเพิ่ม แต่เบื้องต้นเอาแค่นี้ก่อน
        'total_count': history_queryset.count()
    }

def get_approve_modal(request, pk):
    """ ส่ง HTML Modal กลับไปแสดง """
    training = get_object_or_404(TrainingRecord, pk=pk)
    # Default ให้ get_hours เท่ากับที่ขอมา (hours)
    if training.get_hours == 0:
        training.get_hours = training.hours

    return render(request, 'teacher/partials/verify_train_modal.html', {'training': training, 'id': pk})

def approve_training(request, pk):
    """ บันทึกผลอนุมัติ """
    print(request.method)
    if request.method == "POST":
        training = get_object_or_404(TrainingRecord, pk=pk)
        approved_hours = request.POST.get('approved_hours')

        comment = request.POST.get('teacher_comment')
        
        training.status = 'APPROVED'
        training.teacher_comment = comment
        training.get_hours = int(approved_hours) if approved_hours else training.hours
        training.save()
        
        messages.success(request, f"อนุมัติ '{training.topic}' เรียบร้อย (ให้ {training.get_hours} ชม.)")
        context = get_training_context(request)
        return render(request, 'teacher/partials/verify_train_list.html', context)


def get_reject_modal(request, pk):
    training = get_object_or_404(TrainingRecord, pk=pk)
    return render(request, 'teacher/partials/verify_train_reject_modal.html', {'training': training})


def reject_training(request, pk):
    if request.method == "POST":
        training = get_object_or_404(TrainingRecord, pk=pk)
        # รับค่าเหตุผลการปฏิเสธ
        comment = request.POST.get('teacher_comment')
        
        training.status = 'REJECTED'
        training.get_hours = 0
        training.teacher_comment = comment # บันทึกเหตุผล
        training.save()

        messages.warning(request, f"ปฏิเสธรายการ '{training.topic}' แล้ว")
        context = get_training_context(request) 
        return render(request, 'teacher/partials/verify_train_list.html', context)

class TeacherVerifyTrainView(TeacherBaseView):
    def get(self, request):
        if request.headers.get('HX-Request'):
            return render(request, 'teacher/partials/verify_train_list.html', get_training_context(request))

        # 6. Full Page Load
        return render(request, 'teacher/verify_train.html', get_training_context(request))

#---------Job Verification Section ---------
def get_job_verification_context(request):
    search_query = request.GET.get('q', '')
    year_filter = request.GET.get('year', '')

    
    # Base Query: ใบสมัครงานทั้งหมด
    jobs = JobApplication.objects.select_related('student__user').order_by('-created_at')
    academic_year = set(jobs.values_list('academic_year', flat=True).distinct())
    academic_year = sorted(academic_year, reverse=True)
    
    # Search Filter
    if search_query:
        jobs = jobs.filter(
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(student__student_code__icontains=search_query) |
            Q(company__name__icontains=search_query)
        )

    # Year Filter
    if year_filter:
        jobs = jobs.filter(Q(academic_year__icontains=year_filter))

    # --- แยกข้อมูล ---
    
    # 1. Pending List: รายการรออนุมัติ (สถานะ PENDING)
    pending_list = jobs.filter(status='PENDING')
    
    # 2. History List: รายการที่ดำเนินการแล้ว (APPROVED, REJECTED, CANCELED)
    history_queryset = jobs.exclude(status='PENDING')
    
    # ✅ Pagination สำหรับ History (10 รายการต่อหน้า)
    paginator = Paginator(history_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return {
        'pending_list': pending_list,
        'page_obj': page_obj, # ใช้ page_obj แทน history_list
        'search_query': search_query,
        'total_count': history_queryset.count(),
        'academic_year': academic_year
    }

class VerifyJobListView(TeacherBaseView):
    def get(self, request):
        # HTMX Request
        if request.headers.get('HX-Request') and not request.headers.get('HX-Target') == 'modal-container':
             return render(request, 'teacher/partials/job_list.html', get_job_verification_context(request))
             
        return render(request, 'teacher/verify_job.html', get_job_verification_context(request))
    

# 3. Approve Modal Logic
def get_job_approve_modal(request, pk):
    job = get_object_or_404(JobApplication, pk=pk)
    return render(request, 'teacher/partials/verify_job_approve_modal.html', {'job': job})

def approve_job(request, pk):
    if request.method == "POST":
        job = get_object_or_404(JobApplication, pk=pk)
        note = request.POST.get('teacher_note', '-')
        
        job.status = 'APPROVED'
        job.teacher_note = note
        job.save()

        messages.success(request, f"อนุมัติให้นักศึกษาฝึกงานที่ '{job.company.name}' เรียบร้อย")
        context = get_job_verification_context(request)
        return render(request, 'teacher/partials/job_list.html', context)

# 4. Reject Modal Logic
def get_job_reject_modal(request, pk):
    job = get_object_or_404(JobApplication, pk=pk)
    return render(request, 'teacher/partials/verify_job_reject_modal.html', {'job': job})

def reject_job(request, pk):
    if request.method == "POST":
        job = get_object_or_404(JobApplication, pk=pk)
        reason = request.POST.get('teacher_note')
        
        job.status = 'REJECTED'
        job.teacher_note = reason
        job.save()
        
        messages.warning(request, f"ปฏิเสธคำร้องของ '{job.student.user.get_full_name()}' แล้ว")
        context = get_job_verification_context(request)
        return render(request, 'teacher/partials/job_list.html', context)


def get_job_detail_modal(request, pk):
    job = get_object_or_404(JobApplication, pk=pk)
    return render(request, 'teacher/partials/verify_job_detail_modal.html', {'job': job})

#---------Repoirt Verification Section ---------
def get_report_verification_context(request):
    search_query = request.GET.get('q', '')
    week_filter = request.GET.get('week', '')
    year_filter = request.GET.get('year', '')
    
    # Base Query: รายงานทั้งหมด เรียงจากใหม่ไปเก่า
    reports = WeeklyReport.objects.select_related(
        'job_application__student__user', 
        'job_application'
    ).order_by('-submitted_at')
        
    academic_year = set(reports.values_list('job_application__academic_year', flat=True).distinct())
    academic_year = sorted(academic_year, reverse=True)
    
    # Search Filter
    if search_query:
        reports = reports.filter(
            Q(job_application__student__firstname__icontains=search_query) |
            Q(job_application__student__lastname__icontains=search_query) |
            Q(job_application__student__student_code__icontains=search_query)
        )
    # Year Filter
    if year_filter:
        reports = reports.filter(
            job_application__academic_year__icontains=year_filter
        )

    if week_filter:
        try:
            week_num = int(week_filter)
            reports = reports.filter(week_number=week_num)
        except ValueError:
            pass # กรณีค่า week ไม่ถูกต้อง
    # --- แยกข้อมูล ---
    
    # 1. Pending List: รายงานที่ยังไม่ตรวจ (สถานะ PENDING)
    pending_list = reports.filter(status='PENDING')
    
    # 2. History List: รายงานที่ตรวจแล้ว (APPROVED, REJECTED)
    history_queryset = reports.exclude(status='PENDING')
    
    # ✅ Pagination สำหรับ History (10 รายการต่อหน้า)
    paginator = Paginator(history_queryset, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return {
        'pending_list': pending_list,
        'page_obj': page_obj, # ใช้ page_obj แทน history_list
        'search_query': search_query,
        'total_count': history_queryset.count(),
        'academic_year': academic_year
    }

class TeacherVerifyReportView(TeacherBaseView):
    def get(self, request):
        # HTMX Request
        if request.headers.get('HX-Request') and not request.headers.get('HX-Target') == 'modal-container':
             return render(request, 'teacher/partials/report_list.html', get_report_verification_context(request))
             
        return render(request, 'teacher/verify_report.html', get_report_verification_context(request))
    

def get_report_detail_modal(request, pk):
    report = get_object_or_404(WeeklyReport, pk=pk)
    return render(request, 'teacher/partials/report_detail_modal.html', {'report': report})


def acknowledge_report(request, pk):
    if request.method == "POST":
        report = get_object_or_404(WeeklyReport, pk=pk)
        comment = request.POST.get('teacher_comment')
        
        report.status = 'ACKNOWLEDGED'
        report.teacher_comment = comment
        report.submitted_at = timezone.now()
        report.save()
        
        messages.success(request, f"รับทราบรายงาน Week {report.week_number} ของ {report.job_application.student.user.get_full_name()} แล้ว")
        
        # คืนค่า List ใหม่กลับไปอัปเดตหน้าจอ
        return render(request, 'teacher/partials/report_list.html', get_report_verification_context(request))
    

# --- Evaluation Section ---
def get_evaluation_list_context(request):
    search_query = request.GET.get('q', '')
    year_filter = request.GET.get('year', '')
    
    # Base Query: นักศึกษาที่ฝึกงานอยู่ (Job Status = APPROVED)
    jobs = JobApplication.objects.filter(status__in=['APPROVED','COMPLETED']).select_related('student__user', 'evaluation')
    jobs = jobs.filter(evaluation__isnull=False)  # ดึงเฉพาะที่มีการประเมินแล้ว
    academic_year = set(jobs.values_list('academic_year', flat=True).distinct())
    academic_year = sorted(academic_year, reverse=True)

    # Filter Search
    if search_query:
        jobs = jobs.filter(
            Q(student__firstname__icontains=search_query) |
            Q(student__lastname__icontains=search_query) |
            Q(student__student_code__icontains=search_query) |
            Q(company__name__icontains=search_query)
        )
    print(search_query, year_filter)
    if year_filter:
        jobs = jobs.filter(academic_year=year_filter)

    # --- แยกข้อมูลเป็น 2 ส่วน ---
    
    # 1. Pending List: รายการที่บริษัท "SUBMITTED" มาแล้ว (รออาจารย์กดรับทราบ)
    pending_list = jobs.filter(evaluation__status='SUBMITTED').order_by('created_at')
    
    # 2. History List: รายการที่ "APPROVED" แล้ว หรือ "DRAFT/ยังไม่ประเมิน" (ไว้ดูสถานะ)
    # ใช้ exclude SUBMITTED เพราะ SUBMITTED อยู่ข้างบนแล้ว
    history_list = jobs.exclude(evaluation__status='SUBMITTED').order_by('-student__student_code')
    
    # Pagination เฉพาะส่วน History
    paginator = Paginator(history_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return {
        'pending_list': pending_list,
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_year': year_filter,
        'total_count': history_list.count(),
        'academic_year':academic_year
    }

class TeacherVerifyEvaluationView(TeacherBaseView):
    def get(self, request):
        # ถ้าเป็น HTMX Request ให้ส่งกลับเฉพาะส่วนตาราง+Pagination
        if request.headers.get('HX-Request') and not request.headers.get('HX-Target') == 'modal-container':
            return render(request, 'teacher/partials/evaluation_list.html', get_evaluation_list_context(request))
            
        return render(request, 'teacher/verify_evaluation.html', get_evaluation_list_context(request))


def get_evaluation_detail_modal(request, job_id):
    job = get_object_or_404(JobApplication, pk=job_id)
    # พยายามดึง Evaluation (ถ้ายังไม่ประเมินจะได้ None)
    evaluation = getattr(job, 'evaluation', None)
    
    return render(request, 'teacher/partials/verify_evaluation_modal.html', {
        'job': job,
        'eval': evaluation
    })

def acknowledge_evaluation(request, eval_id):
    """ อาจารย์กดรับทราบผลการประเมิน """
    if request.method == "POST":
        evaluation = get_object_or_404(Evaluation, pk=eval_id)
        evaluation.status = 'APPROVED' # เปลี่ยนสถานะเป็นรับรองแล้ว
        evaluation.save()
        
        job = evaluation.job_application
        if job.status == 'APPROVED':
            job.status = 'COMPLETED'
            job.save()
        
        messages.success(request, f"รับทราบผลการประเมินของ {evaluation.job_application.student.user.get_full_name()} แล้ว")
        
        # ปิด Modal และ Refresh ตาราง
        return render(request, 'teacher/partials/evaluation_list.html', get_evaluation_list_context(request))

# ----Announcement Section----
def get_announcement_list_context():
    return {
        'news_list': Announcement.objects.all()
    }

class TeacherNewsView(TeacherBaseView):
    def get(self, request):
        context = {
            'form': AnnouncementForm(),
            'news_list': Announcement.objects.all()
        }
        return render(request, 'teacher/news.html', context)


def create_announcement(request):
    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            # ส่งกลับรายการใหม่ (Update List)
            return render(request, 'partials/news_list.html', get_announcement_list_context())
    
    return HttpResponse(status=400)

def delete_announcement(request, pk):
    item = get_object_or_404(Announcement, pk=pk)
    item.delete()
    return render(request, 'partials/news_list.html', get_announcement_list_context())

# --create_company_account_view--
# --- Helper Functions ---
def get_current_year():
    now = datetime.now()
    thai_year = now.year + 543
    
    if now.month >= 5: # พฤษภาคม เป็นต้นไป
        return thai_year
    else: # มกราคม - เมษายน (ยังเป็นปีการศึกษาเก่า)
        return thai_year - 1

def generate_random_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_account_context(search_query=''):
    year = get_current_year()
    # ดึงข้อมูล Profile ในปีปัจจุบัน
    profiles = CompanyProfile.objects.filter(academic_year=year).select_related('user', 'company').order_by('-id')
    if search_query:
        profiles = profiles.filter(
            Q(company__name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
 
    return {
        'profiles': profiles,
        'current_year': year,
        'search_query': search_query
    }


class TeacherCompanyAccountView(TeacherBaseView):
    def get(self, request):
        search_query = request.GET.get('q', '')
        
        # HTMX Search Request
        if request.headers.get('HX-Request'):
            return render(request, 'partials/company_account_list.html', get_account_context(search_query))
            
        return render(request, 'teacher/company_account.html', get_account_context())
    

def get_account_modal(request, pk=None):
    profile = None
    if pk:
        profile = get_object_or_404(CompanyProfile, pk=pk)
    
    # ส่งรายชื่อบริษัท Master ไปให้เลือกด้วย (กรณีสร้าง manual)
    companies = CompanyMaster.objects.all().order_by('name')
    return render(request, 'teacher/partials/company_account_modal.html', {
        'profile': profile,
        'companies': companies
    })

@transaction.atomic
def save_account(request, pk=None):
    if request.method == "POST":
        # รับค่าจาก Form
        company_id = request.POST.get('company_id') # เลือกจาก Dropdown หรือ Hidden
        new_company_name = request.POST.get('new_company_name') # กรณีกรอกชื่อใหม่
        
        username = request.POST.get('username')
        password = request.POST.get('password')
        position = request.POST.get('position')
        phone = request.POST.get('phone')
        
        current_year = get_current_year()

        # จัดการ Company Master (หาที่มีอยู่ หรือ สร้างใหม่)
        company = None
        if company_id:
            company = CompanyMaster.objects.get(pk=company_id)
        elif new_company_name:
            company, created = CompanyMaster.objects.get_or_create(name=new_company_name)
        
        if not company:
            messages.error(request, "กรุณาระบุบริษัท")
            return render(request, 'teacher/partials/company_account_list.html', get_account_context())

        if pk:
            # --- Update ---
            profile = get_object_or_404(CompanyProfile, pk=pk)
            user = profile.user
            
            # Update User
            user.username = username
            if password:
                user.set_password(password)
            user.save()
            
            # Update Profile
            profile.company = company
            profile.position = position
            profile.phone = phone
            profile.save()
            
            messages.success(request, f"แก้ไขบัญชี {username} เรียบร้อย")
            
        else:
            # --- Create New ---
            # เช็คก่อนว่าบริษัทนี้มีบัญชีในปีนี้หรือยัง
            if CompanyProfile.objects.filter(company=company, academic_year=current_year).exists():
                messages.error(request, f"บริษัท {company.name} มีบัญชีในปี {current_year} แล้ว")
                return render(request, 'teacher/partials/company_account_list.html', get_account_context())

            # เช็ค Username ซ้ำ
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Username '{username}' มีผู้ใช้งานแล้ว")
                return render(request, 'teacher/partials/company_account_list.html', get_account_context())

            # 1. Create User
            user = User.objects.create_user(username=username, password=password, role=User.Role.COMPANY)
            
            # 2. Create Profile
            CompanyProfile.objects.create(
                user=user,
                company=company,
                position=position,
                phone=phone,
                academic_year=current_year
            )
            messages.success(request, f"สร้างบัญชี {username} สำเร็จ")

        return render(request, 'teacher/partials/company_account_list.html', get_account_context())

@transaction.atomic
def delete_account(request, pk):
    profile = get_object_or_404(CompanyProfile, pk=pk)
    user = profile.user
    
    # ลบ User (Profile จะถูกลบตามเพราะ on_delete=CASCADE)
    user.delete()
    
    return render(request, 'teacher/partials/company_account_list.html', get_account_context())

@transaction.atomic
def auto_generate_accounts(request):
    current_year = get_current_year()
    
    # ดึงชื่อบริษัทจากใบสมัครงานที่อนุมัติแล้วในปีนี้
    # สมมติ JobApplication เชื่อมกับ CompanyMaster หรือเก็บชื่อไว้
    # กรณีเก็บเป็นชื่อ (CharField) ต้องเอามา map กับ CompanyMaster
    job_companies = JobApplication.objects.filter(status='APPROVED').values_list('company__name', flat=True).distinct()
    
    created_count = 0
    
    for comp_name in job_companies:
        # 1. หาหรือสร้าง CompanyMaster
        company, _ = CompanyMaster.objects.get_or_create(name=comp_name)
        
        # 2. เช็คว่ามี Profile หรือยัง
        if not CompanyProfile.objects.filter(company=company, academic_year=current_year).exists():
            # Generate Username (เช่น comp_abc123)
            clean_name = "".join(e for e in company.name if e.isalnum())[:8]
            username = f"{clean_name.lower()}_{random.randint(100,999)}"
            password = generate_random_password(8)
            
            # Create User & Profile
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password=password, role=User.Role.COMPANY)
                
                CompanyProfile.objects.create(
                    user=user,
                    company=company,
                    position="HR / ผู้ดูแล",
                    academic_year=current_year
                )
                
                # Note: อาจต้องบันทึก password (plaintext) ไว้ชั่วคราวเพื่อแจ้งบริษัท 
                # หรือใช้วิธีส่ง email reset password แต่ในที่นี้จะโชว์หน้าเว็บตาม requirement เดิม
                # (การเก็บ plaintext password ไม่แนะนำใน production แต่ทำตาม flow เดิมเพื่อความสะดวก)
                
                created_count += 1
    
    if created_count > 0:
        messages.success(request, f"สร้างบัญชีอัตโนมัติสำเร็จ {created_count} รายการ")
    else:
        messages.info(request, "ข้อมูลครบถ้วนแล้ว ไม่มีบัญชีที่ต้องสร้างเพิ่ม")

    return render(request, 'teacher/partials/company_account_list.html', get_account_context())

# ==============================================================================
# 3. Company System
# ==============================================================================

class CompanyBaseView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != User.Role.COMPANY:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class CompanyEvaluationListView(CompanyBaseView):
    def get(self, request):
        # ดึง Profile ของบริษัทที่ Login อยู่
        try:
            company_profile = request.user.company_profile
        except CompanyProfile.DoesNotExist:
            messages.error(request, "บัญชีนี้ไม่มีสิทธิ์เข้าถึง")
            return render(request, 'auth/login.html')

        # ดึงรายชื่อนักศึกษาที่ 'Approved' ให้มาฝึกงานที่บริษัทนี้ในปีการศึกษาปัจจุบัน
        students = JobApplication.objects.filter(
            company__name=company_profile.company.name, # หรือเชื่อมด้วย ID ถ้ามี
            status__in=['APPROVED', 'COMPLETED'],
            academic_year=company_profile.academic_year # กรองปีถ้าจำเป็น
        ).select_related('student__user', 'evaluation')

        return render(request, 'company/evaluation_list.html', {'students': students, 'company': company_profile.company})

# --- HTMX Views ---
def get_evaluation_modal(request, job_id):
    job = get_object_or_404(JobApplication, pk=job_id)
    eval_obj, created = Evaluation.objects.get_or_create(job_application=job)
    
    # สร้าง Form โดยดึงค่าจาก eval_obj มาแสดง (Instance)
    form = EvaluationForm(instance=eval_obj)
    
    context = {
        'job': job,
        'eval': eval_obj,
        'form': form, # ส่ง form ไปที่ template
        'is_readonly': eval_obj.status == 'APPROVED'
    }
    return render(request, 'company/partials/evaluation_modal.html', context)

# ... (ส่วน save_evaluation) ...
def save_evaluation(request, job_id):
    if request.method == "POST":
        job = get_object_or_404(JobApplication, pk=job_id)
        eval_obj = get_object_or_404(Evaluation, job_application=job)

        if eval_obj.status == 'APPROVED':
            messages.error(request, "ไม่สามารถแก้ไขผลประเมินที่รับรองแล้วได้")
            return render(request, 'company/partials/evaluation_row.html', {'s': job})

        # ใช้ Form รับค่าและ Validate
        form = EvaluationForm(request.POST, instance=eval_obj)
        
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.status = 'SUBMITTED' # เปลี่ยนสถานะเมื่อบันทึก
            evaluation.save() # model จะคำนวณ total_score เองใน method save()
            
            messages.success(request, f"บันทึกผลประเมินเรียบร้อย")
            return render(request, 'company/partials/evaluation_row.html', {'s': job})
        else:
            # กรณี Form ไม่ผ่าน (เช่น กรอกไม่ครบ)
            # ใน HTMX อาจจะต้อง return modal เดิมพร้อม error แต่เพื่อความง่ายจะแจ้งเตือนแทน
            messages.error(request, "กรุณากรอกข้อมูลให้ครบถ้วน")
            context = {
                'job': job,
                'eval': eval_obj,
                'form': form, # ส่ง form ที่มี error กลับไป
                'is_readonly': False
            }
            # Swap modal เดิมด้วยตัวที่มี error message
            return render(request, 'company/partials/evaluation_modal.html', context)