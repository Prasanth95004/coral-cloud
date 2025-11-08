from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from .models import (
    ChangeControlRequest,
    Department,
    CFTEvaluator,
    CFTEvaluation,
    RiskAssessment,
    DocumentRevision,
    WorkflowHistory,
)
from .utils import generate_temp_cc_number, generate_final_cc_number


def log_workflow_history(request, step, step_name, actor, action, comments="", previous_status=None, new_status=None):
    """Helper function to log workflow history."""
    WorkflowHistory.objects.create(
        request=request,
        step=step,
        step_name=step_name,
        actor=actor,
        action=action,
        comments=comments,
        previous_status=previous_status or request.status,
        new_status=new_status or request.status
    )


def initiate_request(user, department, title, description):
    """
    Step 1: Initiation
    User = Initiator
    Department = Auto based on user profile
    Temporary CC Request No generated: REQ/CC/YY/DeptCode/00001
    """
    if not department:
        raise ValidationError("Department is required to initiate a request")
    
    # Generate temporary CC number
    temp_cc_number = generate_temp_cc_number(department.code)
    
    # Create the request
    request = ChangeControlRequest.objects.create(
        temporary_cc_number=temp_cc_number,
        initiator=user,
        department=department,
        title=title,
        description=description,
        status=ChangeControlRequest.StatusChoices.DRAFT,
        current_step=1
    )
    
    # Log history
    log_workflow_history(
        request=request,
        step=1,
        step_name="Initiation",
        actor=user,
        action="Request initiated",
        comments=f"Temporary CC number: {temp_cc_number}"
    )
    
    # Auto-route to department head (Step 2)
    route_to_dept_head(request, user)
    
    return request


def route_to_dept_head(request, actor):
    """
    Step 2: Department Head Feasibility
    System routes to Department Head (of initiator's department)
    """
    if request.status != ChangeControlRequest.StatusChoices.DRAFT:
        raise ValidationError("Request must be in Draft status to route to department head")
    
    department = request.department
    if not department.head:
        raise ValidationError(f"Department {department.code} does not have a department head assigned")
    
    # Update status
    previous_status = request.status
    request.status = ChangeControlRequest.StatusChoices.PENDING_DEPT_HEAD
    request.current_step = 2
    request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=2,
        step_name="Department Head Feasibility",
        actor=actor,
        action="Routed to department head",
        comments=f"Routed to {department.head.username}",
        previous_status=previous_status,
        new_status=request.status
    )
    
    return request


def dept_head_decision(request, actor, approved, rejection_reason=""):
    """
    Step 2: Department Head Decision
    If Rejected → Return to Initiator
    If Approved → Sent to QA-QMS Registration
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_DEPT_HEAD:
        raise ValidationError("Request must be pending department head approval")
    
    if request.department.head != actor:
        raise ValidationError("Only the department head can make this decision")
    
    previous_status = request.status
    
    if approved:
        # Route to QA Registration
        request.status = ChangeControlRequest.StatusChoices.PENDING_QA_REGISTRATION
        request.current_step = 3
        
        log_workflow_history(
            request=request,
            step=2,
            step_name="Department Head Feasibility",
            actor=actor,
            action="Approved by department head",
            previous_status=previous_status,
            new_status=request.status
        )
    else:
        # Reject and return to initiator
        request.status = ChangeControlRequest.StatusChoices.REJECTED
        request.rejection_reason = rejection_reason or "Rejected by department head"
        request.rejected_by = actor
        request.rejected_at = timezone.now()
        request.current_step = 2
        
        log_workflow_history(
            request=request,
            step=2,
            step_name="Department Head Feasibility",
            actor=actor,
            action="Rejected by department head",
            comments=rejection_reason,
            previous_status=previous_status,
            new_status=request.status
        )
    
    request.save()
    return request


def qa_registration(request, actor, final_cc_number, impact_level, cft_evaluators, target_completion_time):
    """
    Step 3: QA-QMS Registration & Categorization
    QA assigns:
    - Final CC Number
    - Impact Level (Minor/Major/Critical)
    - CFT Evaluators
    - Target Completion Time
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_QA_REGISTRATION:
        raise ValidationError("Request must be pending QA registration")
    
    # Validate impact level
    if impact_level not in [choice[0] for choice in ChangeControlRequest.ImpactLevelChoices.choices]:
        raise ValidationError(f"Invalid impact level: {impact_level}")
    
    previous_status = request.status
    
    # Assign final CC number if not provided
    if not final_cc_number:
        final_cc_number = generate_final_cc_number(request.department.code)
    
    # Check if final CC number already exists
    if ChangeControlRequest.objects.filter(final_cc_number=final_cc_number).exclude(pk=request.pk).exists():
        raise ValidationError(f"Final CC number {final_cc_number} already exists")
    
    # Update request
    request.final_cc_number = final_cc_number
    request.impact_level = impact_level
    request.target_completion_time = target_completion_time
    request.qa_registered_by = actor
    request.qa_registration_date = timezone.now()
    request.status = ChangeControlRequest.StatusChoices.PENDING_CFT_EVALUATION
    request.current_step = 4
    request.save()
    
    # Assign CFT evaluators
    for evaluator_data in cft_evaluators:
        department = evaluator_data.get('department')
        evaluator = evaluator_data.get('evaluator')
        
        if not department or not evaluator:
            continue
        
        CFTEvaluator.objects.get_or_create(
            request=request,
            department=department,
            evaluator=evaluator
        )
    
    # Log history
    log_workflow_history(
        request=request,
        step=3,
        step_name="QA-QMS Registration",
        actor=actor,
        action="QA registration completed",
        comments=f"Final CC: {final_cc_number}, Impact: {impact_level}",
        previous_status=previous_status,
        new_status=request.status
    )
    
    # Auto-create risk assessment if Major/Critical (Step 5)
    if impact_level in [ChangeControlRequest.ImpactLevelChoices.MAJOR, ChangeControlRequest.ImpactLevelChoices.CRITICAL]:
        create_risk_assessment(request, actor)
    
    return request


def cft_evaluation(request, actor, department, impact_type, decision, risk_level, evaluation_notes="", documents=None):
    """
    Step 4: Cross Functional Team Evaluation
    For each assigned department:
    - Evaluator completes evaluation form
    - Can upload documents
    - Must set: Impact Type, Decision, Risk Level
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_CFT_EVALUATION:
        raise ValidationError("Request must be pending CFT evaluation")
    
    # Check if evaluator is assigned for this department
    if not CFTEvaluator.objects.filter(request=request, department=department, evaluator=actor).exists():
        raise ValidationError(f"User {actor.username} is not assigned as evaluator for {department.code}")
    
    # Create or update evaluation
    evaluation, created = CFTEvaluation.objects.get_or_create(
        request=request,
        department=department,
        defaults={
            'evaluator': actor,
            'impact_type': impact_type,
            'decision': decision,
            'risk_level': risk_level,
            'evaluation_notes': evaluation_notes,
            'completed_at': timezone.now() if decision != CFTEvaluation.DecisionChoices.PENDING else None
        }
    )
    
    if not created:
        evaluation.impact_type = impact_type
        evaluation.decision = decision
        evaluation.risk_level = risk_level
        evaluation.evaluation_notes = evaluation_notes
        if decision != CFTEvaluation.DecisionChoices.PENDING:
            evaluation.completed_at = timezone.now()
        evaluation.save()
    
    # Handle document uploads if provided
    if documents:
        from .models import CFTEvaluationDocument
        for doc in documents:
            CFTEvaluationDocument.objects.create(
                evaluation=evaluation,
                document=doc.get('file'),
                description=doc.get('description', '')
            )
    
    # Log history
    log_workflow_history(
        request=request,
        step=4,
        step_name="CFT Evaluation",
        actor=actor,
        action=f"CFT evaluation completed for {department.code}",
        comments=f"Decision: {decision}, Risk: {risk_level}",
    )
    
    # Check if all CFT evaluations are complete
    all_evaluators = CFTEvaluator.objects.filter(request=request)
    all_evaluations = CFTEvaluation.objects.filter(request=request)
    
    if all_evaluators.count() == all_evaluations.count():
        # All evaluations complete, check if any are rejected
        rejected = all_evaluations.filter(decision=CFTEvaluation.DecisionChoices.REJECTED).exists()
        
        if rejected:
            request.status = ChangeControlRequest.StatusChoices.REJECTED
            request.rejection_reason = "Rejected during CFT evaluation"
            request.rejected_by = actor
            request.rejected_at = timezone.now()
        else:
            # Move to next step based on impact level
            if request.impact_level == ChangeControlRequest.ImpactLevelChoices.MINOR:
                # Skip risk assessment for minor
                request.status = ChangeControlRequest.StatusChoices.PENDING_DOCUMENT_UPDATE
                request.current_step = 6
            else:
                # Major/Critical - check risk assessment status
                if hasattr(request, 'risk_assessment'):
                    if request.risk_assessment.status == RiskAssessment.StatusChoices.COMPLETED:
                        request.status = ChangeControlRequest.StatusChoices.PENDING_DOCUMENT_UPDATE
                        request.current_step = 6
                    else:
                        request.status = ChangeControlRequest.StatusChoices.PENDING_RISK_ASSESSMENT
                        request.current_step = 5
                else:
                    request.status = ChangeControlRequest.StatusChoices.PENDING_RISK_ASSESSMENT
                    request.current_step = 5
        
        request.save()
    
    return request


def create_risk_assessment(request, actor, assigned_to=None):
    """
    Step 5: Risk Assessment (If Impact = Major / Critical)
    Auto-create Risk Assessment Task
    Assigned to QA/QC/PD/RA etc.
    """
    if hasattr(request, 'risk_assessment'):
        return request.risk_assessment
    
    if not assigned_to:
        # Default to QA registered by user, or find a suitable user
        assigned_to = request.qa_registered_by or actor
    
    risk_assessment = RiskAssessment.objects.create(
        request=request,
        assigned_to=assigned_to,
        status=RiskAssessment.StatusChoices.PENDING
    )
    
    # Update request status if needed
    if request.status == ChangeControlRequest.StatusChoices.PENDING_CFT_EVALUATION:
        # Check if all CFT evaluations are done
        all_evaluators = CFTEvaluator.objects.filter(request=request)
        all_evaluations = CFTEvaluation.objects.filter(request=request)
        if all_evaluators.count() == all_evaluations.count():
            request.status = ChangeControlRequest.StatusChoices.PENDING_RISK_ASSESSMENT
            request.current_step = 5
            request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=5,
        step_name="Risk Assessment",
        actor=actor,
        action="Risk assessment task created",
        comments=f"Assigned to {assigned_to.username}"
    )
    
    return risk_assessment


def complete_risk_assessment(request, actor, findings, recommendations):
    """
    Complete the risk assessment task.
    """
    if not hasattr(request, 'risk_assessment'):
        raise ValidationError("Risk assessment does not exist for this request")
    
    risk_assessment = request.risk_assessment
    
    if risk_assessment.assigned_to != actor:
        raise ValidationError("Only the assigned user can complete the risk assessment")
    
    risk_assessment.findings = findings
    risk_assessment.recommendations = recommendations
    risk_assessment.status = RiskAssessment.StatusChoices.COMPLETED
    risk_assessment.completion_date = timezone.now()
    risk_assessment.save()
    
    # Move to document management step
    previous_status = request.status
    request.status = ChangeControlRequest.StatusChoices.PENDING_DOCUMENT_UPDATE
    request.current_step = 6
    request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=5,
        step_name="Risk Assessment",
        actor=actor,
        action="Risk assessment completed",
        previous_status=previous_status,
        new_status=request.status
    )
    
    return risk_assessment


def document_management(request, actor, suggested_documents=None):
    """
    Step 6: Document Management Impact
    System auto-suggest documents needing revision.
    Assigned department prepares revisions.
    """
    if request.status not in [
        ChangeControlRequest.StatusChoices.PENDING_DOCUMENT_UPDATE,
        ChangeControlRequest.StatusChoices.PENDING_ACTION_PLAN
    ]:
        raise ValidationError("Request is not in the correct status for document management")
    
    # Create document revision records if suggested
    if suggested_documents:
        for doc_data in suggested_documents:
            DocumentRevision.objects.get_or_create(
                request=request,
                document_name=doc_data.get('document_name'),
                document_code=doc_data.get('document_code', ''),
                assigned_department=doc_data.get('assigned_department'),
                defaults={
                    'status': DocumentRevision.StatusChoices.PENDING
                }
            )
    
    # Update status if moving from risk assessment
    if request.status == ChangeControlRequest.StatusChoices.PENDING_DOCUMENT_UPDATE:
        request.current_step = 6
        request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=6,
        step_name="Document Management",
        actor=actor,
        action="Document revisions suggested/updated"
    )
    
    return request


def complete_document_revision(request, actor, document_revision, revision_notes=""):
    """
    Complete a document revision.
    """
    if document_revision.assigned_department.head != actor and actor != document_revision.assigned_department.head:
        # Allow if user is in the assigned department or is department head
        pass  # Add more specific permission check if needed
    
    document_revision.status = DocumentRevision.StatusChoices.COMPLETED
    document_revision.revision_date = timezone.now()
    document_revision.revised_by = actor
    document_revision.revision_notes = revision_notes
    document_revision.save()
    
    # Check if all document revisions are complete
    pending_revisions = DocumentRevision.objects.filter(
        request=request,
        status__in=[DocumentRevision.StatusChoices.PENDING, DocumentRevision.StatusChoices.IN_PROGRESS]
    )
    
    if not pending_revisions.exists():
        # All revisions complete, move to action plan
        if request.status == ChangeControlRequest.StatusChoices.PENDING_DOCUMENT_UPDATE:
            previous_status = request.status
            request.status = ChangeControlRequest.StatusChoices.PENDING_ACTION_PLAN
            request.current_step = 7
            request.save()
            
            log_workflow_history(
                request=request,
                step=6,
                step_name="Document Management",
                actor=actor,
                action="All document revisions completed",
                previous_status=previous_status,
                new_status=request.status
            )
    
    return document_revision


def action_plan_management(request, actor, action_plans=None):
    """
    Step 7: Action Plan & Implementation
    Each action has:
    - Responsible person
    - Expected timeline
    - Status
    - Evidence upload
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_ACTION_PLAN:
        raise ValidationError("Request must be pending action plan")
    
    from .models import ActionPlan
    
    # Create action plan items if provided
    if action_plans:
        for action_data in action_plans:
            ActionPlan.objects.create(
                request=request,
                description=action_data.get('description'),
                responsible_person=action_data.get('responsible_person'),
                expected_timeline=action_data.get('expected_timeline'),
                status=ActionPlan.StatusChoices.PENDING
            )
    
    request.current_step = 7
    request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=7,
        step_name="Action Plan & Implementation",
        actor=actor,
        action="Action plan created/updated"
    )
    
    return request


def complete_action_plan(request, actor, action_plan, notes=""):
    """
    Complete an action plan item.
    """
    if action_plan.responsible_person != actor:
        raise ValidationError("Only the responsible person can complete this action")
    
    action_plan.status = ActionPlan.StatusChoices.COMPLETED
    action_plan.completion_date = timezone.now()
    action_plan.notes = notes
    action_plan.save()
    
    # Check if all action plans are complete
    from .models import ActionPlan
    pending_actions = ActionPlan.objects.filter(
        request=request,
        status__in=[ActionPlan.StatusChoices.PENDING, ActionPlan.StatusChoices.IN_PROGRESS]
    )
    
    if not pending_actions.exists():
        # All actions complete, move to QA evaluation
        previous_status = request.status
        request.status = ChangeControlRequest.StatusChoices.PENDING_QA_EVALUATION
        request.current_step = 8
        request.save()
        
        log_workflow_history(
            request=request,
            step=7,
            step_name="Action Plan & Implementation",
            actor=actor,
            action="All action plans completed",
            previous_status=previous_status,
            new_status=request.status
        )
    
    return action_plan


def qa_final_evaluation(request, actor, cft_complete, document_updates_complete, risk_assessment_closed, regulatory_filings_complete, comments=""):
    """
    Step 8: QA Final Evaluation
    QA verifies:
    - CFT evaluation completion
    - Document update completion
    - Risk assessment closure
    - Regulatory filings
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_QA_EVALUATION:
        raise ValidationError("Request must be pending QA evaluation")
    
    # Verify all requirements
    if not cft_complete:
        raise ValidationError("CFT evaluations are not complete")
    
    if not document_updates_complete:
        raise ValidationError("Document updates are not complete")
    
    if request.impact_level in [ChangeControlRequest.ImpactLevelChoices.MAJOR, ChangeControlRequest.ImpactLevelChoices.CRITICAL]:
        if not risk_assessment_closed:
            raise ValidationError("Risk assessment is not closed")
        if not hasattr(request, 'risk_assessment') or request.risk_assessment.status != RiskAssessment.StatusChoices.COMPLETED:
            raise ValidationError("Risk assessment must be completed")
    
    previous_status = request.status
    request.status = ChangeControlRequest.StatusChoices.PENDING_QA_HEAD_APPROVAL
    request.current_step = 9
    request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=8,
        step_name="QA Final Evaluation",
        actor=actor,
        action="QA final evaluation completed",
        comments=comments,
        previous_status=previous_status,
        new_status=request.status
    )
    
    return request


def qa_head_approval(request, actor, approved, rejection_reason=""):
    """
    Step 9: QA Head Approval
    Approves or returns for correction
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_QA_HEAD_APPROVAL:
        raise ValidationError("Request must be pending QA head approval")
    
    # In a real system, you'd check if actor is QA head
    # For now, we'll allow any user with appropriate permissions
    
    previous_status = request.status
    
    if approved:
        request.status = ChangeControlRequest.StatusChoices.PENDING_VERIFICATION
        request.current_step = 10
        
        log_workflow_history(
            request=request,
            step=9,
            step_name="QA Head Approval",
            actor=actor,
            action="Approved by QA head",
            previous_status=previous_status,
            new_status=request.status
        )
    else:
        # Return for correction - go back to action plan
        request.status = ChangeControlRequest.StatusChoices.PENDING_ACTION_PLAN
        request.current_step = 7
        
        log_workflow_history(
            request=request,
            step=9,
            step_name="QA Head Approval",
            actor=actor,
            action="Returned for correction",
            comments=rejection_reason,
            previous_status=previous_status,
            new_status=request.status
        )
    
    request.save()
    return request


def post_implementation_verification(request, actor, change_implemented, training_conducted, no_adverse_impact, comments=""):
    """
    Step 10: Post-Implementation Verification
    QA checks:
    - Change implemented correctly
    - Training conducted
    - No adverse impact
    """
    if request.status != ChangeControlRequest.StatusChoices.PENDING_VERIFICATION:
        raise ValidationError("Request must be pending verification")
    
    if not all([change_implemented, training_conducted, no_adverse_impact]):
        raise ValidationError("All verification checks must pass")
    
    previous_status = request.status
    request.status = ChangeControlRequest.StatusChoices.CLOSED
    request.current_step = 11
    request.closed_at = timezone.now()
    request.save()
    
    # Log history
    log_workflow_history(
        request=request,
        step=10,
        step_name="Post-Implementation Verification",
        actor=actor,
        action="Verification completed",
        comments=comments,
        previous_status=previous_status,
        new_status=request.status
    )
    
    # Auto-close (Step 11)
    qa_closure(request, actor)
    
    return request


def qa_closure(request, actor):
    """
    Step 11: QA Closure
    Final closure of the change control request
    """
    if request.status != ChangeControlRequest.StatusChoices.CLOSED:
        raise ValidationError("Request must be closed before QA closure")
    
    # Log final closure
    log_workflow_history(
        request=request,
        step=11,
        step_name="QA Closure",
        actor=actor,
        action="Change control request closed",
        comments="Request successfully closed"
    )
    
    return request

