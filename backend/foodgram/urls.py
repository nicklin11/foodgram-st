# backend/foodgram/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include your api app's URLs under the 'api/' prefix
    path('api/', include('api.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
    # Optional: Add static files for admin if not handled by whitenoise/nginx
    # urlpatterns += static(
    #    settings.STATIC_URL, document_root=settings.STATIC_ROOT
    # )

# Note: In production, media and static files should be served by Nginx.
