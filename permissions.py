from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from .models import ChangeControlRequest, Department, CFTEvaluator


def is_department_head(user, department):
    """Check if user is the head of the given department."""
    return department.head == user if department and department.head else False


def is_initiator(user, request):
    """Check if user is the initiator of the request."""
    return request.initiator == user


def is_qa_user(user):
    """
    Check if user is a QA user.
    In a real system, this would check user groups or roles.
    For now, we'll use a simple check - you can enhance this.
    """
    # Check if user is in a QA department or has QA in username/email
    # This is a placeholder - implement based on your user model
    qa_departments = Department.objects.filter(code__icontains='QA')
    return qa_departments.filter(head=user).exists() or user.groups.filter(name__icontains='QA').exists()


def is_qa_head(user):
    """
    Check if user is QA head.
    This is a placeholder - implement based on your user model.
    """
    # Check if user is head of QA department
    try:
        qa_dept = Department.objects.get(code='QA', head=user)
        return True
    except Department.DoesNotExist:
        return False


def is_cft_evaluator(user, request, department=None):
    """Check if user is assigned as CFT evaluator for the request."""
    evaluators = CFTEvaluator.objects.filter(request=request, evaluator=user)
    if department:
        evaluators = evaluators.filter(department=department)
    return evaluators.exists()


def can_initiate_request(user):
    """Check if user can initiate a change control request."""
    # All authenticated users can initiate requests
    return user.is_authenticated


def can_approve_dept_head(user, request):
    """Check if user can approve as department head."""
    return is_department_head(user, request.department)


def can_register_qa(user):
    """Check if user can perform QA registration."""
    return is_qa_user(user)


def can_evaluate_cft(user, request, department=None):
    """Check if user can perform CFT evaluation."""
    return is_cft_evaluator(user, request, department)


def can_perform_risk_assessment(user, request):
    """Check if user can perform risk assessment."""
    if not hasattr(request, 'risk_assessment'):
        return False
    return request.risk_assessment.assigned_to == user or is_qa_user(user)


def can_manage_documents(user, request, document_revision=None):
    """Check if user can manage document revisions."""
    if document_revision:
        return is_department_head(user, document_revision.assigned_department)
    return True  # Allow viewing


def can_manage_action_plan(user, request, action_plan=None):
    """Check if user can manage action plans."""
    if action_plan:
        return action_plan.responsible_person == user or is_qa_user(user)
    return is_qa_user(user) or is_initiator(user, request)


def can_perform_qa_evaluation(user):
    """Check if user can perform QA final evaluation."""
    return is_qa_user(user)


def can_approve_qa_head(user):
    """Check if user can approve as QA head."""
    return is_qa_head(user)


def can_perform_verification(user):
    """Check if user can perform post-implementation verification."""
    return is_qa_user(user)


def can_close_request(user):
    """Check if user can close the request."""
    return is_qa_user(user)


def can_view_request(user, request):
    """Check if user can view the request."""
    # Initiator can always view
    if is_initiator(user, request):
        return True
    
    # Department head can view
    if is_department_head(user, request.department):
        return True
    
    # QA users can view
    if is_qa_user(user):
        return True
    
    # CFT evaluators can view
    if is_cft_evaluator(user, request):
        return True
    
    # Risk assessment assignee can view
    if hasattr(request, 'risk_assessment') and request.risk_assessment.assigned_to == user:
        return True
    
    # Action plan responsible persons can view
    if request.action_plans.filter(responsible_person=user).exists():
        return True
    
    return False


# Decorator functions for views
def require_permission(permission_func):
    """Decorator to require a specific permission."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get the change control request if it's in kwargs
            cc_request = kwargs.get('request') or kwargs.get('cc_request')
            if cc_request:
                if not permission_func(request.user, cc_request):
                    raise PermissionDenied("You do not have permission to perform this action")
            elif not permission_func(request.user):
                raise PermissionDenied("You do not have permission to perform this action")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_department_head(view_func):
    """Decorator to require department head permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        cc_request = kwargs.get('request') or kwargs.get('cc_request')
        if cc_request and not can_approve_dept_head(request.user, cc_request):
            raise PermissionDenied("Only the department head can perform this action")
        return view_func(request, *args, **kwargs)
    return wrapper


def require_qa_user(view_func):
    """Decorator to require QA user permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_perform_qa_evaluation(request.user):
            raise PermissionDenied("Only QA users can perform this action")
        return view_func(request, *args, **kwargs)
    return wrapper


def require_qa_head(view_func):
    """Decorator to require QA head permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_approve_qa_head(request.user):
            raise PermissionDenied("Only QA head can perform this action")
        return view_func(request, *args, **kwargs)
    return wrapper


def require_cft_evaluator(view_func):
    """Decorator to require CFT evaluator permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        cc_request = kwargs.get('request') or kwargs.get('cc_request')
        department = kwargs.get('department')
        if cc_request and not can_evaluate_cft(request.user, cc_request, department):
            raise PermissionDenied("You are not assigned as a CFT evaluator for this request")
        return view_func(request, *args, **kwargs)
    return wrapper

