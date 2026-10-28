from django.contrib import admin
from django.urls import path

from core import views
from grafik import views as g

W = "api/w/<uuid:workplace_id>"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", views.health),
    path("api/session/", views.session),
    path("api/register/", views.register),
    path("api/me/password/", views.password),
    path("api/terms/", views.terms),
    path("api/public-config/", views.public_config),
    # panel
    path("api/workplaces/", g.workplaces),
    path(f"{W}/", g.workplace),
    path(f"{W}/export/", g.workplace_export),
    path(f"{W}/departments/", g.departments),
    path(f"{W}/departments/<uuid:department_id>/", g.department),
    path(f"{W}/employees/", g.employees),
    path(f"{W}/employees/<uuid:employee_id>/", g.employee),
    path(f"{W}/employees/<uuid:employee_id>/account/", g.employee_account),
    path(f"{W}/employees/<uuid:employee_id>/card/", g.employee_card),
    path(f"{W}/employees/<uuid:employee_id>/invite/", g.employee_invite),
    path(f"{W}/unknown-cards/", g.unknown_cards),
    path(f"{W}/points/", g.points),
    path(f"{W}/points/<uuid:point_id>/", g.point),
    path(f"{W}/points/<uuid:point_id>/tag/", g.point_tag),
    path(f"{W}/points/<uuid:point_id>/kiosk/", g.point_kiosk),
    path(f"{W}/week/", g.week),
    path(f"{W}/week/copy/", g.copy_week),
    path(f"{W}/shifts/", g.shifts),
    path(f"{W}/shifts/<uuid:shift_id>/", g.shift),
    path(f"{W}/unavailability/", g.unavailabilities),
    path(f"{W}/unavailability/<uuid:unavailability_id>/", g.unavailability),
    path(f"{W}/requests/", g.requests_),
    path(f"{W}/requests/<uuid:request_id>/", g.request_),
    path(f"{W}/requests/<uuid:request_id>/approve/", g.request_approve),
    path(f"{W}/requests/<uuid:request_id>/reject/", g.request_reject),
    path(f"{W}/today/", g.today),
    path(f"{W}/report/", g.report),
    path(f"{W}/report.csv", g.report_csv),
    path(f"{W}/punches/", g.punches),
    path(f"{W}/punches/<int:punch_id>/void/", g.punch_void),
    # NFC
    path("api/nfc/<str:tag_token>/", g.nfc),
    path("api/kiosk/<str:secret>/", g.kiosk),
    path("api/invite/<str:secret>/", g.invitation),
]
