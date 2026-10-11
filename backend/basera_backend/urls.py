"""
URL configuration for basera_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import home, api_root, nabd_site

urlpatterns = [
    path('', home, name='home'),
    path('nabd/', nabd_site, name='nabd-home'),
    path('nabd/<path:path>', nabd_site, name='nabd-file'),
    path('api/', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('core.urls')),
    path('api/lessons/', include('lessons.urls')),
    path('api/tests/', include('tests.urls')),
    path('api/volunteers/', include('volunteers.urls')),
]

# Shared hosting: serve uploaded media even when DEBUG=False
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
