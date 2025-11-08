from rest_framework import serializers
from django.contrib.auth.models import User
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


class UserSerializer(serializers.ModelSerializer):
    """User serializer for nested representations."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class DepartmentSerializer(serializers.ModelSerializer):
    """Department serializer."""
    head = UserSerializer(read_only=True)
    head_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='head',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Department
        fields = ['id', 'code', 'name', 'head', 'head_id', 'created_at', 'updated_at']


class CFTEvaluatorSerializer(serializers.ModelSerializer):
    """CFT Evaluator serializer."""
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True
    )
    evaluator = UserSerializer(read_only=True)
    evaluator_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='evaluator',
        write_only=True
    )
    
    class Meta:
        model = CFTEvaluator
        fields = ['id', 'request', 'department', 'department_id', 'evaluator', 'evaluator_id', 'assigned_at']


class CFTEvaluationDocumentSerializer(serializers.ModelSerializer):
    """CFT Evaluation Document serializer."""
    class Meta:
        model = CFTEvaluationDocument
        fields = ['id', 'evaluation', 'document', 'description', 'uploaded_at']


class CFTEvaluationSerializer(serializers.ModelSerializer):
    """CFT Evaluation serializer."""
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True
    )
    evaluator = UserSerializer(read_only=True)
    documents = CFTEvaluationDocumentSerializer(many=True, read_only=True)
    
    class Meta:
        model = CFTEvaluation
        fields = [
            'id', 'request', 'department', 'department_id', 'evaluator',
            'impact_type', 'decision', 'risk_level', 'evaluation_notes',
            'evaluation_date', 'completed_at', 'documents'
        ]
        read_only_fields = ['evaluator', 'evaluation_date', 'completed_at']


class RiskAssessmentSerializer(serializers.ModelSerializer):
    """Risk Assessment serializer."""
    assigned_to = UserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='assigned_to',
        write_only=True
    )
    
    class Meta:
        model = RiskAssessment
        fields = [
            'id', 'request', 'assigned_to', 'assigned_to_id', 'status',
            'findings', 'recommendations', 'created_at', 'completion_date'
        ]
        read_only_fields = ['created_at', 'completion_date']


class DocumentRevisionSerializer(serializers.ModelSerializer):
    """Document Revision serializer."""
    assigned_department = DepartmentSerializer(read_only=True)
    assigned_department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='assigned_department',
        write_only=True
    )
    revised_by = UserSerializer(read_only=True)
    
    class Meta:
        model = DocumentRevision
        fields = [
            'id', 'request', 'document_name', 'document_code',
            'assigned_department', 'assigned_department_id', 'status',
            'revision_notes', 'revision_date', 'revised_by'
        ]
        read_only_fields = ['revision_date', 'revised_by']


class ActionPlanEvidenceSerializer(serializers.ModelSerializer):
    """Action Plan Evidence serializer."""
    uploaded_by = UserSerializer(read_only=True)
    
    class Meta:
        model = ActionPlanEvidence
        fields = ['id', 'action_plan', 'evidence_file', 'description', 'uploaded_at', 'uploaded_by']
        read_only_fields = ['uploaded_at', 'uploaded_by']


class ActionPlanSerializer(serializers.ModelSerializer):
    """Action Plan serializer."""
    responsible_person = UserSerializer(read_only=True)
    responsible_person_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='responsible_person',
        write_only=True
    )
    evidence = ActionPlanEvidenceSerializer(many=True, read_only=True)
    
    class Meta:
        model = ActionPlan
        fields = [
            'id', 'request', 'description', 'responsible_person', 'responsible_person_id',
            'expected_timeline', 'status', 'completion_date', 'notes',
            'created_at', 'updated_at', 'evidence'
        ]
        read_only_fields = ['created_at', 'updated_at', 'completion_date']


class WorkflowHistorySerializer(serializers.ModelSerializer):
    """Workflow History serializer."""
    actor = UserSerializer(read_only=True)
    
    class Meta:
        model = WorkflowHistory
        fields = [
            'id', 'request', 'step', 'step_name', 'actor', 'action',
            'comments', 'timestamp', 'previous_status', 'new_status'
        ]
        read_only_fields = ['timestamp']


class ChangeControlRequestSerializer(serializers.ModelSerializer):
    """Change Control Request serializer."""
    initiator = UserSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True
    )
    qa_registered_by = UserSerializer(read_only=True)
    rejected_by = UserSerializer(read_only=True)
    
    # Related objects
    cft_evaluators = CFTEvaluatorSerializer(many=True, read_only=True)
    cft_evaluations = CFTEvaluationSerializer(many=True, read_only=True)
    risk_assessment = RiskAssessmentSerializer(read_only=True)
    document_revisions = DocumentRevisionSerializer(many=True, read_only=True)
    action_plans = ActionPlanSerializer(many=True, read_only=True)
    workflow_history = WorkflowHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = ChangeControlRequest
        fields = [
            'id', 'temporary_cc_number', 'final_cc_number', 'initiator',
            'department', 'department_id', 'title', 'description',
            'impact_level', 'target_completion_time', 'qa_registered_by',
            'qa_registration_date', 'status', 'current_step',
            'created_at', 'updated_at', 'closed_at',
            'rejection_reason', 'rejected_by', 'rejected_at',
            'cft_evaluators', 'cft_evaluations', 'risk_assessment',
            'document_revisions', 'action_plans', 'workflow_history'
        ]
        read_only_fields = [
            'temporary_cc_number', 'final_cc_number', 'initiator',
            'qa_registered_by', 'qa_registration_date', 'status',
            'current_step', 'created_at', 'updated_at', 'closed_at',
            'rejected_by', 'rejected_at'
        ]


# Serializers for workflow actions
class InitiateRequestSerializer(serializers.Serializer):
    """Serializer for initiating a new request."""
    department_id = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()


class DeptHeadDecisionSerializer(serializers.Serializer):
    """Serializer for department head decision."""
    approved = serializers.BooleanField()
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class QARegistrationSerializer(serializers.Serializer):
    """Serializer for QA registration."""
    final_cc_number = serializers.CharField(required=False, allow_blank=True)
    impact_level = serializers.ChoiceField(choices=ChangeControlRequest.ImpactLevelChoices.choices)
    target_completion_time = serializers.DateField()
    cft_evaluators = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of {department_id, evaluator_id}"
    )


class CFTEvaluationSubmitSerializer(serializers.Serializer):
    """Serializer for submitting CFT evaluation."""
    department_id = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())
    impact_type = serializers.ChoiceField(choices=CFTEvaluation.ImpactTypeChoices.choices)
    decision = serializers.ChoiceField(choices=CFTEvaluation.DecisionChoices.choices)
    risk_level = serializers.ChoiceField(choices=CFTEvaluation.RiskLevelChoices.choices)
    evaluation_notes = serializers.CharField(required=False, allow_blank=True)


class RiskAssessmentCompleteSerializer(serializers.Serializer):
    """Serializer for completing risk assessment."""
    findings = serializers.CharField()
    recommendations = serializers.CharField(required=False, allow_blank=True)


class DocumentRevisionCompleteSerializer(serializers.Serializer):
    """Serializer for completing document revision."""
    revision_notes = serializers.CharField(required=False, allow_blank=True)


class ActionPlanCreateSerializer(serializers.Serializer):
    """Serializer for creating action plans."""
    action_plans = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of {description, responsible_person_id, expected_timeline}"
    )


class ActionPlanCompleteSerializer(serializers.Serializer):
    """Serializer for completing action plan."""
    notes = serializers.CharField(required=False, allow_blank=True)


class QAFinalEvaluationSerializer(serializers.Serializer):
    """Serializer for QA final evaluation."""
    cft_complete = serializers.BooleanField()
    document_updates_complete = serializers.BooleanField()
    risk_assessment_closed = serializers.BooleanField()
    regulatory_filings_complete = serializers.BooleanField()
    comments = serializers.CharField(required=False, allow_blank=True)


class QAHeadApprovalSerializer(serializers.Serializer):
    """Serializer for QA head approval."""
    approved = serializers.BooleanField()
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class VerificationSerializer(serializers.Serializer):
    """Serializer for post-implementation verification."""
    change_implemented = serializers.BooleanField()
    training_conducted = serializers.BooleanField()
    no_adverse_impact = serializers.BooleanField()
    comments = serializers.CharField(required=False, allow_blank=True)

