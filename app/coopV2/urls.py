from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from coopstack import views as app_views # Import view สำหรับหน้า Home (Optional)

urlpatterns = [
    # หน้า Admin ของ Django
    path('admin/', admin.site.urls),
    # เชื่อมต่อ URLs ของ internship_app เข้ากับ Root URL ('')
    # ถ้าอยากให้มี prefix เช่น 'portal/' ให้แก้เป็น path('portal/', include(...))
    path('', include('coopstack.urls')),
]

# การตั้งค่าสำหรับ Serving Media Files (User Uploads) ในโหมด DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)