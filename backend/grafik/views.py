"""HTTP is a thin layer: parse, call one service, map DomainError to a status."""

from functools import wraps

from django.http import HttpResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from core import accounts
from core.domain_errors import DomainError
from core.i18n import error_body

from . import clock, schedule, team


class KioskThrottle(AnonRateThrottle):
    scope = "kiosk"


def answer(fn):
    @wraps(fn)
    def view(request, *args, **kwargs):
        try:
            result = fn(request, *args, **kwargs)
        except DomainError as error:
            return Response(error_body(error), status=error.status)
        return result if isinstance(result, HttpResponse) else Response(result)

    return view


def methods(**handlers):
    """One URL, one handler per HTTP method: methods(GET=..., POST=...)."""

    @api_view(list(handlers))
    @answer
    def view(request, *args, **kwargs):
        return handlers[request.method](request, *args, **kwargs)

    return view


def u(request):
    return request.user


# --- workplaces and team --------------------------------------------------------------------------

workplaces = methods(
    GET=lambda r: team.list_workplaces(u(r)),
    POST=lambda r: team.workplace_json(team.workplace_access(u(r), accounts.add_firm(r, r.data).id)),
)
workplace = methods(
    PATCH=lambda r, workplace_id: team.update_workplace(u(r), workplace_id, r.data),
    DELETE=lambda r, workplace_id: team.delete_workplace(u(r), workplace_id, r.data),
)
workplace_export = methods(GET=lambda r, workplace_id: team.export_workplace(u(r), workplace_id))
departments = methods(
    GET=lambda r, workplace_id: team.list_departments(u(r), workplace_id),
    POST=lambda r, workplace_id: team.create_department(u(r), workplace_id, r.data),
)
department = methods(
    PATCH=lambda r, workplace_id, department_id: team.update_department(u(r), workplace_id, department_id, r.data),
    DELETE=lambda r, workplace_id, department_id: team.delete_department(u(r), workplace_id, department_id),
)
employees = methods(
    GET=lambda r, workplace_id: team.list_employees(u(r), workplace_id),
    POST=lambda r, workplace_id: team.create_employee(u(r), workplace_id, r.data),
)
employee = methods(
    PATCH=lambda r, workplace_id, employee_id: team.update_employee(u(r), workplace_id, employee_id, r.data),
    DELETE=lambda r, workplace_id, employee_id: team.delete_employee(u(r), workplace_id, employee_id),
)
employee_account = methods(
    POST=lambda r, workplace_id, employee_id: team.give_account(u(r), workplace_id, employee_id, r.data),
    DELETE=lambda r, workplace_id, employee_id: team.remove_account(u(r), workplace_id, employee_id),
)
employee_card = methods(
    POST=lambda r, workplace_id, employee_id: team.assign_card(u(r), workplace_id, employee_id, r.data),
    DELETE=lambda r, workplace_id, employee_id: team.remove_card(u(r), workplace_id, employee_id),
)
unknown_cards = methods(GET=lambda r, workplace_id: team.unknown_cards(u(r), workplace_id))
points = methods(
    GET=lambda r, workplace_id: team.list_points(u(r), workplace_id),
    POST=lambda r, workplace_id: team.create_point(u(r), workplace_id, r.data),
)
point = methods(
    PATCH=lambda r, workplace_id, point_id: team.update_point(u(r), workplace_id, point_id, r.data),
    DELETE=lambda r, workplace_id, point_id: team.delete_point(u(r), workplace_id, point_id),
)
point_tag = methods(POST=lambda r, workplace_id, point_id: team.new_tag(u(r), workplace_id, point_id))
point_kiosk = methods(
    POST=lambda r, workplace_id, point_id: team.new_kiosk(u(r), workplace_id, point_id),
    DELETE=lambda r, workplace_id, point_id: team.remove_kiosk(u(r), workplace_id, point_id),
)

# --- schedule --------------------------------------------------------------------------------------

week = methods(GET=lambda r, workplace_id: schedule.week(u(r), workplace_id, r.query_params))
copy_week = methods(POST=lambda r, workplace_id: schedule.copy_week(u(r), workplace_id, r.data))
shifts = methods(POST=lambda r, workplace_id: schedule.create_shift(u(r), workplace_id, r.data))
shift = methods(
    PATCH=lambda r, workplace_id, shift_id: schedule.update_shift(u(r), workplace_id, shift_id, r.data),
    DELETE=lambda r, workplace_id, shift_id: schedule.delete_shift(u(r), workplace_id, shift_id),
)
unavailabilities = methods(
    GET=lambda r, workplace_id: schedule.list_unavailability(u(r), workplace_id, r.query_params),
    POST=lambda r, workplace_id: schedule.create_unavailability(u(r), workplace_id, r.data),
)
unavailability = methods(
    PATCH=lambda r, workplace_id, unavailability_id: schedule.update_unavailability(u(r), workplace_id, unavailability_id, r.data),
    DELETE=lambda r, workplace_id, unavailability_id: schedule.delete_unavailability(u(r), workplace_id, unavailability_id),
)
requests_ = methods(
    GET=lambda r, workplace_id: schedule.list_requests(u(r), workplace_id),
    POST=lambda r, workplace_id: schedule.create_request(u(r), workplace_id, r.data),
)
request_ = methods(
    PATCH=lambda r, workplace_id, request_id: schedule.update_request(u(r), workplace_id, request_id, r.data),
    DELETE=lambda r, workplace_id, request_id: schedule.withdraw_request(u(r), workplace_id, request_id),
)
request_approve = methods(POST=lambda r, workplace_id, request_id: schedule.review_request(u(r), workplace_id, request_id, r.data, True))
request_reject = methods(POST=lambda r, workplace_id, request_id: schedule.review_request(u(r), workplace_id, request_id, r.data, False))

# --- time ------------------------------------------------------------------------------------------

today = methods(GET=lambda r, workplace_id: clock.today(u(r), workplace_id))
report = methods(GET=lambda r, workplace_id: clock.report(u(r), workplace_id, r.query_params))
punches = methods(
    GET=lambda r, workplace_id: clock.punches(u(r), workplace_id, r.query_params),
    POST=lambda r, workplace_id: clock.manual_punch(u(r), workplace_id, r.data),
)
punch_void = methods(POST=lambda r, workplace_id, punch_id: clock.void_punch(u(r), workplace_id, punch_id, r.data))


def csv_report(r, workplace_id):
    month, body = clock.report_csv(u(r), workplace_id, r.query_params)
    response = HttpResponse(body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="czas-pracy-{month}.csv"'
    return response


report_csv = methods(GET=csv_report)

# --- NFC: sticker (own phone, session) and kiosk (card, secret link, no session) ----------------------


@api_view(["GET", "POST"])
@permission_classes([AllowAny])  # GET says what to do; POST itself demands a logged-in employee
@answer
def nfc(request, tag_token):
    if request.method == "POST":
        return clock.tag_punch(request.user, tag_token)
    return clock.tag_info(request.user, tag_token)


@api_view(["GET", "POST"])
@authentication_classes([])  # the secret in the link is the credential; a logged-in tablet needs no CSRF
@permission_classes([AllowAny])
@throttle_classes([KioskThrottle])
@answer
def kiosk(request, secret):
    if request.method == "POST":
        return clock.kiosk_punch(secret, request.data)
    return clock.kiosk_info(secret)
