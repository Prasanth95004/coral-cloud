from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


class Department(models.Model):
    """Department model with department head assignment."""
    code = models.CharField(max_length=10, unique=True, help_text="Department code (e.g., QA, PD, RA)")
    name = models.CharField(max_length=100, help_text="Department name")
    head = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
        help_text="Department head user"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.code} - {self.name}"


class ChangeControlRequest(models.Model):
    """Main Change Control Request model."""
    
    class StatusChoices(models.TextChoices):
        DRAFT = 'Draft', 'Draft'
        PENDING_DEPT_HEAD = 'Pending_Dept_Head', 'Pending Department Head'
        PENDING_QA_REGISTRATION = 'Pending_QA_Registration', 'Pending QA Registration'
        PENDING_CFT_EVALUATION = 'Pending_CFT_Evaluation', 'Pending CFT Evaluation'
        PENDING_RISK_ASSESSMENT = 'Pending_Risk_Assessment', 'Pending Risk Assessment'
        PENDING_DOCUMENT_UPDATE = 'Pending_Document_Update', 'Pending Document Update'
        PENDING_ACTION_PLAN = 'Pending_Action_Plan', 'Pending Action Plan'
        PENDING_QA_EVALUATION = 'Pending_QA_Evaluation', 'Pending QA Evaluation'
        PENDING_QA_HEAD_APPROVAL = 'Pending_QA_Head_Approval', 'Pending QA Head Approval'
        PENDING_VERIFICATION = 'Pending_Verification', 'Pending Verification'
        CLOSED = 'Closed', 'Closed'
        REJECTED = 'Rejected', 'Rejected'

    class ImpactLevelChoices(models.TextChoices):
        MINOR = 'Minor', 'Minor'
        MAJOR = 'Major', 'Major'
        CRITICAL = 'Critical', 'Critical'

    # Step 1: Initiation
    temporary_cc_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Temporary CC number: REQ/CC/YY/DeptCode/00001"
    )
    final_cc_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text="Final CC number assigned by QA"
    )
    initiator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='initiated_cc_requests',
        help_text="User who initiated the request"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='cc_requests',
        help_text="Department of the initiator"
    )
    
    # Request details
    title = models.CharField(max_length=200, help_text="Change control request title")
    description = models.TextField(help_text="Detailed description of the change")
    
    # Step 3: QA Registration
    impact_level = models.CharField(
        max_length=20,
        choices=ImpactLevelChoices.choices,
        blank=True,
        null=True,
        help_text="Impact level assigned by QA"
    )
    target_completion_time = models.DateField(
        blank=True,
        null=True,
        help_text="Target completion time assigned by QA"
    )
    qa_registered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qa_registered_cc_requests',
        help_text="QA user who registered the request"
    )
    qa_registration_date = models.DateTimeField(blank=True, null=True)
    
    # Workflow state
    status = models.CharField(
        max_length=30,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
        help_text="Current workflow status"
    )
    current_step = models.IntegerField(default=1, help_text="Current workflow step (1-11)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    
    # Rejection
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection if rejected")
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_cc_requests',
        help_text="User who rejected the request"
    )
    rejected_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Change Control Request"
        verbose_name_plural = "Change Control Requests"

    def __str__(self):
        return f"{self.temporary_cc_number} - {self.title}"

    def clean(self):
        """Validate the model."""
        if self.status == self.StatusChoices.REJECTED and not self.rejection_reason:
            raise ValidationError("Rejection reason is required when status is Rejected")


class CFTEvaluator(models.Model):
    """Cross-functional team evaluators assigned to a request."""
    request = models.ForeignKey(
        ChangeControlRequest,
        on_delete=models.CASCADE,
        related_name='cft_evaluators',
        help_text="Change control request"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='cft_evaluations',
        help_text="Department of the evaluator"
    )
    evaluator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cft_evaluations',
        help_text="User assigned as evaluator"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['request', 'department']
        verbose_name = "CFT Evaluator"
        verbose_name_plural = "CFT Evaluators"

    def __str__(self):
        return f"{self.request.temporary_cc_number} - {self.department.code} - {self.evaluator.username}"


class CFTEvaluation(models.Model):
    """Cross-functional team evaluation form."""
    
    class ImpactTypeChoices(models.TextChoices):
        OPERATIONAL = 'Operational', 'Operational'
        QUALITY = 'Quality', 'Quality'
        REGULATORY = 'Regulatory', 'Regulatory'
        FINANCIAL = 'Financial', 'Financial'
        TECHNICAL = 'Technical', 'Technical'
        OTHER = 'Other', 'Other'

    class DecisionChoices(models.TextChoices):
        APPROVED = 'Approved', 'Approved'
        APPROVED_WITH_CONDITIONS = 'Approved_with_Conditions', 'Approved with Conditions'
        REJECTED = 'Rejected', 'Rejected'
        PENDING = 'Pending', 'Pending'

    class RiskLevelChoices(models.TextChoices):
        LOW = 'Low', 'Low'
        MEDIUM = 'Medium', 'Medium'
        HIGH = 'High', 'High'
        CRITICAL = 'Critical', 'Critical'

    request = models.ForeignKey(
        ChangeControlRequest,
        on_delete=models.CASCADE,
        related_name='cft_evaluations',
        help_text="Change control request"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        help_text="Department performing the evaluation"
    )
    evaluator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='evaluations',
        help_text="User who completed the evaluation"
    )
    impact_type = models.CharField(
        max_length=30,
        choices=ImpactTypeChoices.choices,
        help_text="Type of impact"
    )
    decision = models.CharField(
        max_length=30,
        choices=DecisionChoices.choices,
        default=DecisionChoices.PENDING,
        help_text="Evaluation decision"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevelChoices.choices,
        help_text="Risk level assessment"
    )
    evaluation_notes = models.TextField(blank=True, help_text="Evaluation notes and comments")
    evaluation_date = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ['request', 'department']
        verbose_name = "CFT Evaluation"
        verbose_name_plural = "CFT Evaluations"

    def __str__(self):
        return f"{self.request.temporary_cc_number} - {self.department.code} Evaluation"


class CFTEvaluationDocument(models.Model):
    """Documents uploaded during CFT evaluation."""
    evaluation = models.ForeignKey(
        CFTEvaluation,
        on_delete=models.CASCADE,
        related_name='documents',
        help_text="CFT evaluation"
    )
    document = models.FileField(upload_to='cft_evaluations/%Y/%m/%d/', help_text="Uploaded document")
    description = models.CharField(max_length=200, blank=True, help_text="Document description")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "CFT Evaluation Document"
        verbose_name_plural = "CFT Evaluation Documents"

    def __str__(self):
        return f"{self.evaluation} - {self.description or self.document.name}"


class RiskAssessment(models.Model):
    """Risk assessment task (auto-created for Major/Critical impact)."""
    
    class StatusChoices(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        IN_PROGRESS = 'In_Progress', 'In Progress'
        COMPLETED = 'Completed', 'Completed'
        CANCELLED = 'Cancelled', 'Cancelled'

    request = models.OneToOneField(
        ChangeControlRequest,
        on_delete=models.CASCADE,
        related_name='risk_assessment',
        help_text="Change control request"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='risk_assessments',
        help_text="User assigned to perform risk assessment"
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        help_text="Risk assessment status"
    )
    findings = models.TextField(blank=True, help_text="Risk assessment findings")
    recommendations = models.TextField(blank=True, help_text="Recommendations from risk assessment")
    created_at = models.DateTimeField(auto_now_add=True)
    completion_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Risk Assessment"
        verbose_name_plural = "Risk Assessments"

    def __str__(self):
        return f"Risk Assessment - {self.request.temporary_cc_number}"


class DocumentRevision(models.Model):
    """Document management - documents needing revision."""
    
    class StatusChoices(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        IN_PROGRESS = 'In_Progress', 'In Progress'
        COMPLETED = 'Completed', 'Completed'
        NOT_REQUIRED = 'Not_Required', 'Not Required'

    request = models.ForeignKey(
        ChangeControlRequest,
        on_delete=models.CASCADE,
        related_name='document_revisions',
        help_text="Change control request"
    )
    document_name = models.CharField(max_length=200, help_text="Name of the document")
    document_code = models.CharField(max_length=50, blank=True, help_text="Document code/reference")
    assigned_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='document_revisions',
        help_text="Department responsible for revision"
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        help_text="Revision status"
    )
    revision_notes = models.TextField(blank=True, help_text="Notes about the revision")
    revision_date = models.DateTimeField(blank=True, null=True, help_text="Date when revision was completed")
    revised_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revised_documents',
        help_text="User who completed the revision"
    )

    class Meta:
        verbose_name = "Document Revision"
        verbose_name_plural = "Document Revisions"

    def __str__(self):
        return f"{self.document_name} - {self.request.temporary_cc_number}"


class ActionPlan(models.Model):
    """Implementation action plan items."""
    
    class StatusChoices(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        IN_PROGRESS = 'In_Progress', 'In Progress'
        COMPLETED = 'Completed', 'Completed'
        CANCELLED = 'Cancelled', 'Cancelled'

    request = models.ForeignKey(
        ChangeControlRequest,
        on_delete=models.CASCADE,
        related_name='action_plans',
        help_text="Change control request"
    )
    description = models.TextField(help_text="Action description")
    responsible_person = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='action_plans',
        help_text="Person responsible for the action"
    )
    expected_timeline = models.DateField(help_text="Expected completion date")
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        help_text="Action status"
    )
    completion_date = models.DateTimeField(blank=True, null=True, help_text="Actual completion date")
    notes = models.TextField(blank=True, help_text="Additional notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expected_timeline']
        verbose_name = "Action Plan"
        verbose_name_plural = "Action Plans"

    def __str__(self):
        return f"{self.request.temporary_cc_number} - {self.description[:50]}"


class ActionPlanEvidence(models.Model):
    """Evidence uploads for action plan items."""
    action_plan = models.ForeignKey(
        ActionPlan,
        on_delete=models.CASCADE,
        related_name='evidence',
        help_text="Action plan item"
    )
    evidence_file = models.FileField(upload_to='action_plan_evidence/%Y/%m/%d/', help_text="Evidence file")
    description = models.CharField(max_length=200, blank=True, help_text="Evidence description")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_evidence'
    )

    class Meta:
        verbose_name = "Action Plan Evidence"
        verbose_name_plural = "Action Plan Evidence"

    def __str__(self):
        return f"{self.action_plan} - {self.description or self.evidence_file.name}"


class WorkflowHistory(models.Model):
    """Audit trail for workflow steps."""
    request = models.ForeignKey(
        ChangeControlRequest,
        on_delete=models.CASCADE,
        related_name='workflow_history',
        help_text="Change control request"
    )
    step = models.IntegerField(help_text="Workflow step number")
    step_name = models.CharField(max_length=100, help_text="Name of the workflow step")
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='workflow_actions',
        help_text="User who performed the action"
    )
    action = models.CharField(max_length=100, help_text="Action performed")
    comments = models.TextField(blank=True, help_text="Additional comments")
    timestamp = models.DateTimeField(auto_now_add=True)
    previous_status = models.CharField(max_length=30, blank=True, help_text="Previous status")
    new_status = models.CharField(max_length=30, blank=True, help_text="New status")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Workflow History"
        verbose_name_plural = "Workflow History"

    def __str__(self):
        return f"{self.request.temporary_cc_number} - Step {self.step} - {self.action}"
