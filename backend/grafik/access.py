"""One authority boundary. Another firm's objects answer 404, never 403; inside the firm a missing
right is a 403 with a sentence saying who can do it.

Roles (PLAN.md §2): dyrektor — everything; kierownik — schedule, requests and time records of the
people in his own department, and the accounts of its employees (team.manageable); pracownik — sees his department's schedule, manages his own
unavailability and requests. Superuser (agencja) acts as „admin” = dyrektor of every firm.
"""

from core.domain_errors import DomainError

from .domain import identifier
from .models import Employee, Workplace

RANK = {"pracownik": 0, "kierownik": 1, "dyrektor": 2, "admin": 3}


def workplace_access(user, workplace_id, minimum="pracownik"):
    workplace = Workplace.objects.filter(pk=identifier(workplace_id, "Firma")).first()
    if not workplace or not user.is_authenticated:
        raise DomainError("Firma: nie znaleziono", 404)
    me = Employee.objects.filter(workplace=workplace, user=user, active=True).first()
    role = "admin" if user.is_superuser else me.role if me else None
    if role is None:
        raise DomainError("Firma: nie znaleziono", 404)
    if RANK[role] < RANK[minimum]:
        raise DomainError("To może zrobić tylko dyrektor firmy" if minimum == "dyrektor"
                          else "To może zrobić kierownik działu albo dyrektor", 403)
    workplace.me, workplace.role = me, role
    return workplace


def is_director(workplace):
    return workplace.role in ("dyrektor", "admin")


def manages(workplace, employee):
    """Can arrange this person's shifts, review their requests and correct their time records."""
    if is_director(workplace):
        return True
    me = workplace.me
    return workplace.role == "kierownik" and me.department_id is not None and employee.department_id == me.department_id


def require_manager(workplace, employee):
    if not manages(workplace, employee):
        raise DomainError("To może zrobić kierownik działu tej osoby albo dyrektor", 403)


def sees(workplace, employee):
    """Everyone sees their own department's schedule (who works with whom); the director sees all."""
    if is_director(workplace) or employee.pk == workplace.me.pk:
        return True
    return workplace.me.department_id is not None and employee.department_id == workplace.me.department_id


def employee_in(workplace, employee_id, lock=False):
    qs = Employee.objects.select_for_update() if lock else Employee.objects
    employee = qs.filter(workplace=workplace, pk=identifier(employee_id, "Pracownik")).first()
    if not employee or not sees(workplace, employee):
        raise DomainError("Pracownik: nie znaleziono", 404)
    return employee


def workplaces_for(user):
    if user.is_superuser:  # all real firms; visitors' demo sandboxes are not the agency's business
        return Workplace.objects.filter(demo_until__isnull=True).order_by("name")
    return Workplace.objects.filter(employees__user=user, employees__active=True).order_by("name").distinct()
