from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import logout as auth_logout


def custom_logout(request):
    auth_logout(request)
    return redirect('/')


def custom_login_redirect(request):
    next_url = request.GET.get('next', '/dashboard/')
    return redirect(f'/?next={next_url}')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/logout/', custom_logout, name='custom_logout'),
    path('accounts/login/', custom_login_redirect),
    path('accounts/', include('allauth.urls')),
    path('', include('employees.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)