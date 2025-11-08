from django.contrib import admin
from .models import (
    Department,
    ChangeControlRequest,
    CFTEvaluator,
    CFTEvaluation,
    CFTEvaluationDocument,
    RiskAssessment,
    DocumentRevision,
    ActionPlan,
    ActionPlanEvidence,
    WorkflowHistory,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'head', 'created_at']
    list_filter = ['code', 'created_at']
    search_fields = ['code', 'name', 'head__username']
    raw_id_fields = ['head']


class CFTEvaluatorInline(admin.TabularInline):
    model = CFTEvaluator
    extra = 0
    raw_id_fields = ['evaluator']


class CFTEvaluationInline(admin.TabularInline):
    model = CFTEvaluation
    extra = 0
    readonly_fields = ['evaluation_date', 'completed_at']
    raw_id_fields = ['evaluator']


class DocumentRevisionInline(admin.TabularInline):
    model = DocumentRevision
    extra = 0
    readonly_fields = ['revision_date', 'revised_by']
    raw_id_fields = ['assigned_department', 'revised_by']


class ActionPlanInline(admin.TabularInline):
    model = ActionPlan
    extra = 0
    readonly_fields = ['created_at', 'updated_at', 'completion_date']
    raw_id_fields = ['responsible_person']


class WorkflowHistoryInline(admin.TabularInline):
    model = WorkflowHistory
    extra = 0
    readonly_fields = ['timestamp']
    can_delete = False
    raw_id_fields = ['actor']


@admin.register(ChangeControlRequest)
class ChangeControlRequestAdmin(admin.ModelAdmin):
    list_display = [
        'temporary_cc_number', 'final_cc_number', 'title', 'initiator',
        'department', 'status', 'current_step', 'impact_level', 'created_at'
    ]
    list_filter = [
        'status', 'current_step', 'impact_level', 'department', 'created_at'
    ]
    search_fields = [
        'temporary_cc_number', 'final_cc_number', 'title', 'description',
        'initiator__username', 'department__code'
    ]
    readonly_fields = [
        'temporary_cc_number', 'final_cc_number', 'initiator', 'created_at',
        'updated_at', 'closed_at', 'qa_registration_date', 'rejected_at'
    ]
    raw_id_fields = [
        'initiator', 'department', 'qa_registered_by', 'rejected_by'
    ]
    inlines = [
        CFTEvaluatorInline,
        CFTEvaluationInline,
        DocumentRevisionInline,
        ActionPlanInline,
        WorkflowHistoryInline,
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'temporary_cc_number', 'final_cc_number', 'title', 'description',
                'initiator', 'department'
            )
        }),
        ('QA Registration', {
            'fields': (
                'impact_level', 'target_completion_time',
                'qa_registered_by', 'qa_registration_date'
            )
        }),
        ('Workflow Status', {
            'fields': (
                'status', 'current_step', 'created_at', 'updated_at', 'closed_at'
            )
        }),
        ('Rejection Information', {
            'fields': (
                'rejection_reason', 'rejected_by', 'rejected_at'
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(CFTEvaluator)
class CFTEvaluatorAdmin(admin.ModelAdmin):
    list_display = ['request', 'department', 'evaluator', 'assigned_at']
    list_filter = ['department', 'assigned_at']
    search_fields = ['request__temporary_cc_number', 'evaluator__username']
    raw_id_fields = ['request', 'evaluator']


@admin.register(CFTEvaluation)
class CFTEvaluationAdmin(admin.ModelAdmin):
    list_display = [
        'request', 'department', 'evaluator', 'impact_type',
        'decision', 'risk_level', 'evaluation_date'
    ]
    list_filter = ['impact_type', 'decision', 'risk_level', 'evaluation_date']
    search_fields = ['request__temporary_cc_number', 'evaluator__username']
    readonly_fields = ['evaluation_date', 'completed_at']
    raw_id_fields = ['request', 'evaluator']


@admin.register(CFTEvaluationDocument)
class CFTEvaluationDocumentAdmin(admin.ModelAdmin):
    list_display = ['evaluation', 'description', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['evaluation__request__temporary_cc_number', 'description']


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'request', 'assigned_to', 'status', 'created_at', 'completion_date'
    ]
    list_filter = ['status', 'created_at', 'completion_date']
    search_fields = ['request__temporary_cc_number', 'assigned_to__username']
    readonly_fields = ['created_at', 'completion_date']
    raw_id_fields = ['request', 'assigned_to']
    fieldsets = (
        ('Basic Information', {
            'fields': ('request', 'assigned_to', 'status')
        }),
        ('Assessment Details', {
            'fields': ('findings', 'recommendations')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completion_date')
        }),
    )


@admin.register(DocumentRevision)
class DocumentRevisionAdmin(admin.ModelAdmin):
    list_display = [
        'request', 'document_name', 'document_code', 'assigned_department',
        'status', 'revision_date'
    ]
    list_filter = ['status', 'assigned_department', 'revision_date']
    search_fields = [
        'request__temporary_cc_number', 'document_name', 'document_code'
    ]
    readonly_fields = ['revision_date', 'revised_by']
    raw_id_fields = ['request', 'assigned_department', 'revised_by']


@admin.register(ActionPlan)
class ActionPlanAdmin(admin.ModelAdmin):
    list_display = [
        'request', 'description', 'responsible_person', 'expected_timeline',
        'status', 'completion_date'
    ]
    list_filter = ['status', 'expected_timeline', 'completion_date']
    search_fields = [
        'request__temporary_cc_number', 'description',
        'responsible_person__username'
    ]
    readonly_fields = ['created_at', 'updated_at', 'completion_date']
    raw_id_fields = ['request', 'responsible_person']


@admin.register(ActionPlanEvidence)
class ActionPlanEvidenceAdmin(admin.ModelAdmin):
    list_display = ['action_plan', 'description', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = [
        'action_plan__request__temporary_cc_number', 'description'
    ]
    readonly_fields = ['uploaded_at']
    raw_id_fields = ['action_plan', 'uploaded_by']


@admin.register(WorkflowHistory)
class WorkflowHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'request', 'step', 'step_name', 'actor', 'action', 'timestamp'
    ]
    list_filter = ['step', 'step_name', 'timestamp']
    search_fields = [
        'request__temporary_cc_number', 'actor__username', 'action'
    ]
    readonly_fields = ['timestamp']
    raw_id_fields = ['request', 'actor']
    date_hierarchy = 'timestamp'

