from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import (
    DepartmentViewSet,
    ChangeControlRequestViewSet,
    CFTEvaluationViewSet,
    RiskAssessmentViewSet,
    DocumentRevisionViewSet,
    ActionPlanViewSet,
    WorkflowHistoryViewSet,
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'change-control', ChangeControlRequestViewSet, basename='change-control')
router.register(r'cft-evaluations', CFTEvaluationViewSet, basename='cft-evaluation')
router.register(r'risk-assessments', RiskAssessmentViewSet, basename='risk-assessment')
router.register(r'document-revisions', DocumentRevisionViewSet, basename='document-revision')
router.register(r'action-plans', ActionPlanViewSet, basename='action-plan')
router.register(r'workflow-history', WorkflowHistoryViewSet, basename='workflow-history')

app_name = 'change_control'

urlpatterns = [
    path('api/', include(router.urls)),
]

