from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import (
    Student, TrainingRecord, JobApplication, 
    WeeklyReport, CompanyMaster, Evaluation, Announcement, AllowedStudent
)

User = get_user_model()

# ==========================================
# 1. Authentication & Registration Forms
# ==========================================

class StudentRegisterForm(forms.ModelForm):
    """ ฟอร์มสมัครสมาชิกสำหรับนักศึกษา (User + Student Profile) """
    # เพิ่ม field ที่ไม่ได้อยู่ใน User Model โดยตรง
    student_code = forms.CharField(label="รหัสนักศึกษา", widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(
        label="รหัสผ่าน",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8
    )
    confirm_password = forms.CharField(
        label="ยืนยันรหัสผ่าน",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'password', 'confirm_password', 'email', 'student_code'] # Fields ของ User
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'ชื่อผู้ใช้ (Username)',
            'email': 'อีเมล (Email Address) ใช้อีเมลสถาบันเท่านั้น',
            'student_code': 'รหัสนักศึกษา (Student ID)',
            'password': 'รหัสผ่าน (Password)',
            'confirm_password': 'ยืนยันรหัสผ่าน (Confirm Password)',
        }
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'input input-bordered w-full focus:input-secondary',
                'placeholder': field.label
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        domain = email.split('@')[-1]
        
        # 1. ตรวจสอบ Domain
        if domain not in settings.ALLOWED_EMAIL_DOMAINS:
            raise ValidationError(f"กรุณาใช้อีเมลสถาบันเท่านั้น (@{settings.ALLOWED_EMAIL_DOMAINS[0]})")
        
        # 2. ตรวจสอบว่าอีเมลซ้ำไหม
        if User.objects.filter(email=email).exists():
            raise ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
            
        return email

    def clean(self):
        cleaned_data = super().clean()
        student_code = cleaned_data.get('student_id')
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password != confirm_password:
            self.add_error('confirm_password', "รหัสผ่านไม่ตรงกัน")

        if student_code:
            # 3. ตรวจสอบว่ามีรหัสนักศึกษาในฐานข้อมูล AllowedStudent หรือไม่
            try:
                allowed_student = AllowedStudent.objects.get(student_code=student_code)

                if allowed_student.is_registered:
                    self.add_error('student_code', "รหัสนักศึกษานี้ได้ลงทะเบียนไปแล้ว")
                
                # ฝากข้อมูลไว้ใน cleaned_data เพื่อให้ View ไปใช้ต่อ (ดึงชื่อสกุล)
                cleaned_data['allowed_student_info'] = allowed_student
                
            except AllowedStudent.DoesNotExist:
                self.add_error('student_code', "ไม่พบรหัสนักศึกษาในระบบ หรือคุณไม่มีสิทธิ์ลงทะเบียน")

        return cleaned_data
    

# ==========================================
# 2. Student Forms (Training, Job, Report)
# ==========================================

class TrainingRecordForm(forms.ModelForm):
    class Meta:
        model = TrainingRecord
        fields = ['topic', 'date', 'hours', 'proof_file']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'input input-bordered w-full',
                'type': 'date'
            }),
            'topic': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'ระบุหัวข้อการอบรม'
            }),
            'hours': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'min': 1,
                'max': 8,
                'placeholder': 'เช่น 3'
            }),
            'proof_file': forms.FileInput(attrs={
                'class': 'file-input file-input-bordered w-full',
                'accept': 'image/*,.pdf' # กำหนดประเภทไฟล์ให้ตรงกับ HTML เดิม
            }),
        }


class JobApplicationForm(forms.ModelForm):
    # 1. Input ค้นหา/กรอกชื่อบริษัทใหม่
    company_search = forms.CharField(
        label="ชื่อบริษัท (เลือกจากรายการ หรือ พิมพ์ชื่อใหม่)",
        required=True, # ต้องกรอกชื่อเสมอ
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'พิมพ์ชื่อบริษัทเพื่อค้นหา หรือระบุชื่อบริษัทใหม่...',
            'hx-get': '/htmx/search/company/',
            'hx-target': '#company-results',
            'hx-trigger': 'keyup changed delay:500ms',
            'autocomplete': 'off'
        })
    )

    # 2. Hidden Field เก็บ ID (ปรับเป็น required=False เพื่อรองรับเคสบริษัทใหม่ที่ยังไม่มี ID)
    company = forms.ModelChoiceField(
        queryset=CompanyMaster.objects.all(),
        widget=forms.HiddenInput(),
        required=False 
    )

    class Meta:
        model = JobApplication
        fields = [
            'company', 'position', 'location', 'start_date', 'end_date',
            'supervisor_name', 'supervisor_phone', 
            'accommodation', 'emergency_contact', 'emergency_phone'
        ]
        widgets = {
            'position': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'เช่น Programmer, System Analyst'
            }),
            'location': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24', # ปรับความสูง
                'placeholder': 'ระบุเลขที่อาคาร ถนน เขต จังหวัด...'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'input input-bordered w-full',
                'type': 'date'  # Browser Date Picker
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'input input-bordered w-full',
                'type': 'date'
            }),
            'supervisor_name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'ชื่อพี่เลี้ยง หรือ HR'
            }),
            'supervisor_phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': '0xx-xxx-xxxx'
            }),
            'accommodation': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24',
                'placeholder': 'ระบุที่พัก (ถ้ามี)'
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'ชื่อผู้ติดต่อฉุกเฉิน'
            }),
            'emergency_phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': '0xx-xxx-xxxx'
            }),
        }

    # 3. Logic อัตโนมัติ: ถ้าไม่มี ID ให้สร้างบริษัทใหม่
    def clean(self):
        cleaned_data = super().clean()
        company_obj = cleaned_data.get('company')      # ID ที่เลือก (ถ้ามี)
        company_name = cleaned_data.get('company_search') # ชื่อที่พิมพ์
        location = cleaned_data.get('location')        # ที่ตั้งที่กรอกมา

        # กรณีที่ 1: ผู้ใช้พิมพ์ชื่อใหม่ และไม่ได้เลือกจาก Dropdown (company เป็น None)
        if not company_obj and company_name:
            # ลองค้นหาจากชื่อดูก่อน (กันซ้ำ) หรือ สร้างใหม่เลย
            # ใช้ get_or_create เพื่อความปลอดภัย
            company_obj, created = CompanyMaster.objects.get_or_create(
                name=company_name,
                defaults={
                    # ถ้าสร้างใหม่ ให้เอาที่ตั้งที่เด็กกรอก ไปเป็นที่อยู่บริษัทเบื้องต้นด้วย
                    'address': location if location else '-' 
                }
            )
            # ยัด Object กลับเข้าไปใน cleaned_data เพื่อให้ Django บันทึกต่อได้
            cleaned_data['company'] = company_obj
        
        # กรณีที่ 2: ถ้าสุดท้ายแล้วยังไม่มีข้อมูลบริษัท
        if not cleaned_data.get('company'):
            raise ValidationError("กรุณาระบุชื่อบริษัท")

        return cleaned_data


class WeeklyReportForm(forms.ModelForm):
    class Meta:
        model = WeeklyReport
        fields = ['week_number', 'work_summary', 'problems', 'knowledge_gained', 'supervisor_feedback']
        
        widgets = {
            'week_number': forms.NumberInput(attrs={
                'class': 'input input-bordered',
                'placeholder': 'ระบุตัวเลข (เช่น 1)',
                'min': '1',
                'max': '16', # สมมติฝึกงานไม่เกิน 16 สัปดาห์
                'style': 'width: 100px;' 
            }),
            'work_summary': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered h-24 focus:textarea-primary',
                'placeholder': '- งานที่ได้รับมอบหมาย\n- รายละเอียดการปฏิบัติงาน\n- ผลลัพธ์ที่ได้'
            }),
            'problems': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered h-24 focus:textarea-primary',
                'placeholder': '- ปัญหาหรืออุปสรรคที่พบ'
            }),
            'knowledge_gained': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered h-24 focus:textarea-primary',
                'placeholder': '- ความรู้ใหม่ที่ได้รับ\n- ทักษะที่ได้รับการพัฒนา'
            }),
            'supervisor_feedback': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered h-24 focus:textarea-primary',
                'placeholder': '- ข้อเสนอแนะจากพี่เลี้ยง (ถ้ามี)'
            }),
        }
        
        labels = {
            'week_number': 'สัปดาห์ที่ (Week)',
            'work_summary': 'สรุปงานที่ปฏิบัติ (Work Summary)',
            'problems': 'ปัญหาและอุปสรรค (Problems)',
            'knowledge_gained': 'สิ่งที่ได้เรียนรู้ (Knowledge Gained)',
            'supervisor_feedback': 'ข้อเสนอแนะจากพี่เลี้ยง (Supervisor Feedback)',
        }

    # เพิ่ม Validation (Optional): ป้องกันการกรอกสัปดาห์ที่เป็น 0 หรือติดลบ
    def clean_week_number(self):
        week = self.cleaned_data.get('week_number')
        if week < 1:
            raise forms.ValidationError("สัปดาห์ต้องเริ่มต้นที่ 1")
        return week

# ==========================================
# 3. Teacher Forms (Action Forms)
# ==========================================

class TeacherCompanyCommentForm(forms.ModelForm):
    """ ฟอร์มสำหรับอาจารย์บันทึก Note เกี่ยวกับบริษัท """
    class Meta:
        model = CompanyMaster
        fields = ['teacher_notes']
        widgets = {
            'teacher_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TeacherVerifyJobForm(forms.ModelForm):
    """ ฟอร์มสำหรับอาจารย์อนุมัติงาน (ใช้ในหน้า Detail ถ้าต้องการแก้ Note) """
    class Meta:
        model = JobApplication
        fields = ['status', 'teacher_note']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'teacher_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class TeacherVerifyReportForm(forms.ModelForm):
    """ ฟอร์มตรวจรายงานประจำสัปดาห์ """
    class Meta:
        model = WeeklyReport
        fields = ['status', 'teacher_comment']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'ใส่คอมเมนต์ให้นักศึกษา...'}),
        }

class AnnouncementForm(forms.ModelForm):
    """ ฟอร์มสร้าง/แก้ไขประกาศ """
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'attachment', 'is_published', 'is_pinned']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ==========================================
# 4. Company Forms (Evaluation)
# ==========================================

class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        # ระบุ field ทั้งหมดที่จะให้กรอก (ยกเว้น job_application, status, total_score ที่ระบบจัดการเอง)
        fields = [
            'q1_1', 'q1_2', 'q1_3', 'c1_comment',
            'q2_1', 'q2_2', 'q2_3', 'c2_comment',
            'q3_1', 'q3_2', 'q3_3', 'c3_comment',
            'q4_1', 'q4_2', 'q4_3', 'c4_comment',
            'q5_1', 'q5_2', 'q5_3', 'c5_comment',
            'strengths', 'weaknesses'
        ]
        
        labels = {
            'q1_1': '1.1 ปริมาณงาน (Quantity of work)',
            'q1_2': '1.2 คุณภาพงาน (Quality of work)',
            'q1_3': '1.3 ความสำเร็จตามเป้าหมาย (Success against targets)',
            'c1_comment': 'ข้อเสนอแนะเพิ่มเติม (ส่วนที่ 1)',
            'q2_1': '2.1 ความรู้ทางวิชาการ (Academic knowledge)',
            'q2_2': '2.2 ความสามารถในการเรียนรู้งาน (Ability to learn)',
            'q2_3': '2.3 ทักษะการปฏิบัติงาน (Practical skills)',
            'c2_comment': 'ข้อเสนอแนะเพิ่มเติม (ส่วนที่ 2)',
            'q3_1': '3.1 ความรับผิดชอบต่อหน้าที่ (Responsibility)',
            'q3_2': '3.2 ความตรงต่อเวลา (Punctuality)',
            'q3_3': '3.3 การปฏิบัติตามกฎระเบียบ (Discipline)',
            'c3_comment': 'ข้อเสนอแนะเพิ่มเติม (ส่วนที่ 3)',
            'q4_1': '4.1 บุคลิกภาพและการวางตัว (Personality)',
            'q4_2': '4.2 มนุษยสัมพันธ์ (Human Relations)',
            'q4_3': '4.3 ความกระตือรือร้น (Enthusiasm)',
            'c4_comment': 'ข้อเสนอแนะเพิ่มเติม (ส่วนที่ 4)',
            'q5_1': '5.1 การทำงานเป็นทีม (Teamwork)',
            'q5_2': '5.2 การเสนอความคิดเห็น (Suggestions)',
            'q5_3': '5.3 จริยธรรมและคุณธรรม (Ethics)',
            'c5_comment': 'ข้อเสนอแนะเพิ่มเติม (ส่วนที่ 5)',
            'strengths': 'จุดเด่นของนักศึกษา',
            'weaknesses': 'จุดที่ควรปรับปรุงของนักศึกษา'
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ตัวเลือกคะแนน 1-5
        RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
        SCORE_CHOICES = [
            (5, '5 - ดีมาก (Excellent)'),
            (4, '4 - ดี (Good)'),
            (3, '3 - ปานกลาง (Fair)'),
            (2, '2 - พอใช้ (Poor)'),
            (1, '1 - ต้องปรับปรุง (Failure)'),
        ]
        # รายชื่อ field ที่เป็นคะแนน
        rating_fields = [
            'q1_1', 'q1_2', 'q1_3',
            'q2_1', 'q2_2', 'q2_3',
            'q3_1', 'q3_2', 'q3_3',
            'q4_1', 'q4_2', 'q4_3',
            'q5_1', 'q5_2', 'q5_3'
        ]
        
        # Loop ตั้งค่า Widget ให้เป็น Radio Button แนวนอน
        for field_name in rating_fields:
            self.fields[field_name].widget = forms.RadioSelect(choices=SCORE_CHOICES)
            self.fields[field_name].required = True # บังคับกรอก
            # เพิ่ม class หรือ attribute เพื่อใช้กับ JS คำนวณคะแนน
            self.fields[field_name].widget.attrs.update({
                'class': 'rating-radio',
                'onchange': 'calcScore()' 
            })

        # ตั้งค่า Textarea สำหรับคอมเมนต์
        comment_fields = ['c1_comment', 'c2_comment', 'c3_comment', 'c4_comment', 'c5_comment', 'strengths', 'weaknesses']
        for field_name in comment_fields:
            self.fields[field_name].widget = forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'ระบุรายละเอียด...'
            })
            self.fields[field_name].required = False # คอมเมนต์ไม่บังคับก็ได้
        
        # บังคับจุดเด่น/จุดด้อย
        self.fields['strengths'].required = True
        self.fields['weaknesses'].required = True

    def clean(self):
        """ สามารถเพิ่ม Logic ตรวจสอบเพิ่มเติมได้ที่นี่ """
        cleaned_data = super().clean()
        return cleaned_data