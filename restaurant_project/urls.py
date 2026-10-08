from django.contrib import admin
from django.conf import settings
from django.http import FileResponse
from django.urls import include, path


def home(request):
    return FileResponse(open(settings.BASE_DIR / 'index.html', 'rb'), content_type='text/html')

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('', include('restaurant_app.urls')),
]
