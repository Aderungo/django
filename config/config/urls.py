"""URL configuration for the catering project."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
]

# Медиафайлы (эскизы заказов, фото блюд) отдаются и при DEBUG=False,
# чтобы учебный проект можно было проверить без веб-сервера.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

handler403 = 'main.views.handler403'
handler404 = 'main.views.handler404'
