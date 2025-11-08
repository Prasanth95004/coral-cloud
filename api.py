from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from .models import (
    ChangeControlRequest,
    Department,
    CFTEvaluation,
    RiskAssessment,
    DocumentRevision,
    ActionPlan,
    WorkflowHistory,
)
from .serializers import (
    ChangeControlRequestSerializer,
    DepartmentSerializer,
    CFTEvaluationSerializer,
    RiskAssessmentSerializer,
    DocumentRevisionSerializer,
    ActionPlanSerializer,
    WorkflowHistorySerializer,
    InitiateRequestSerializer,
    DeptHeadDecisionSerializer,
    QARegistrationSerializer,
    CFTEvaluationSubmitSerializer,
    RiskAssessmentCompleteSerializer,
    DocumentRevisionCompleteSerializer,
    ActionPlanCreateSerializer,
    ActionPlanCompleteSerializer,
    QAFinalEvaluationSerializer,
    QAHeadApprovalSerializer,
    VerificationSerializer,
)
from .workflow import (
    initiate_request,
    dept_head_decision,
    qa_registration,
    cft_evaluation,
    complete_risk_assessment,
    complete_document_revision,
    action_plan_management,
    complete_action_plan,
    qa_final_evaluation,
    qa_head_approval,
    post_implementation_verification,
)
from .permissions import (
    can_view_request,
    can_initiate_request,
    can_approve_dept_head,
    can_register_qa,
    can_evaluate_cft,
    can_perform_risk_assessment,
    can_manage_documents,
    can_manage_action_plan,
    can_perform_qa_evaluation,
    can_approve_qa_head,
    can_perform_verification,
)
from .utils import get_user_department


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Department model."""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


class ChangeControlRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for Change Control Request with workflow actions."""
    queryset = ChangeControlRequest.objects.all()
    serializer_class = ChangeControlRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filter based on user's role and permissions
        # Show requests where user is:
        # - Initiator
        # - Department head
        # - QA user
        # - CFT evaluator
        # - Risk assessment assignee
        # - Action plan responsible person
        
        filtered_ids = []
        for request in queryset:
            if can_view_request(user, request):
                filtered_ids.append(request.id)
        
        return queryset.filter(id__in=filtered_ids)
    
    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Step 1: Initiate a new change control request."""
        if not can_initiate_request(request.user):
            return Response(
                {"error": "You do not have permission to initiate requests"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = InitiateRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                department = serializer.validated_data['department_id']
                title = serializer.validated_data['title']
                description = serializer.validated_data['description']
                
                # Auto-determine department from user if not provided
                if not department:
                    department = get_user_department(request.user)
                    if not department:
                        return Response(
                            {"error": "Department not found for user"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                cc_request = initiate_request(
                    user=request.user,
                    department=department,
                    title=title,
                    description=description
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def dept_head_decision(self, request, pk=None):
        """Step 2: Department head approval/rejection."""
        cc_request = self.get_object()
        
        if not can_approve_dept_head(request.user, cc_request):
            return Response(
                {"error": "Only the department head can make this decision"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DeptHeadDecisionSerializer(data=request.data)
        if serializer.is_valid():
            try:
                approved = serializer.validated_data['approved']
                rejection_reason = serializer.validated_data.get('rejection_reason', '')
                
                dept_head_decision(
                    request=cc_request,
                    actor=request.user,
                    approved=approved,
                    rejection_reason=rejection_reason
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def qa_registration(self, request, pk=None):
        """Step 3: QA registration and categorization."""
        cc_request = self.get_object()
        
        if not can_register_qa(request.user):
            return Response(
                {"error": "Only QA users can perform registration"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = QARegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                final_cc_number = serializer.validated_data.get('final_cc_number', '')
                impact_level = serializer.validated_data['impact_level']
                target_completion_time = serializer.validated_data['target_completion_time']
                cft_evaluators_data = serializer.validated_data['cft_evaluators']
                
                # Convert evaluator data to proper format
                cft_evaluators = []
                for eval_data in cft_evaluators_data:
                    from .models import Department
                    department = Department.objects.get(id=eval_data['department_id'])
                    from django.contrib.auth.models import User
                    evaluator = User.objects.get(id=eval_data['evaluator_id'])
                    cft_evaluators.append({
                        'department': department,
                        'evaluator': evaluator
                    })
                
                qa_registration(
                    request=cc_request,
                    actor=request.user,
                    final_cc_number=final_cc_number or None,
                    impact_level=impact_level,
                    cft_evaluators=cft_evaluators,
                    target_completion_time=target_completion_time
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cft_evaluation(self, request, pk=None):
        """Step 4: CFT evaluation submission."""
        cc_request = self.get_object()
        
        serializer = CFTEvaluationSubmitSerializer(data=request.data)
        if serializer.is_valid():
            try:
                department = serializer.validated_data['department_id']
                
                if not can_evaluate_cft(request.user, cc_request, department):
                    return Response(
                        {"error": "You are not assigned as a CFT evaluator for this department"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                impact_type = serializer.validated_data['impact_type']
                decision = serializer.validated_data['decision']
                risk_level = serializer.validated_data['risk_level']
                evaluation_notes = serializer.validated_data.get('evaluation_notes', '')
                
                cft_evaluation(
                    request=cc_request,
                    actor=request.user,
                    department=department,
                    impact_type=impact_type,
                    decision=decision,
                    risk_level=risk_level,
                    evaluation_notes=evaluation_notes
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def complete_risk_assessment(self, request, pk=None):
        """Step 5: Complete risk assessment."""
        cc_request = self.get_object()
        
        if not can_perform_risk_assessment(request.user, cc_request):
            return Response(
                {"error": "You are not assigned to perform this risk assessment"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = RiskAssessmentCompleteSerializer(data=request.data)
        if serializer.is_valid():
            try:
                findings = serializer.validated_data['findings']
                recommendations = serializer.validated_data.get('recommendations', '')
                
                complete_risk_assessment(
                    request=cc_request,
                    actor=request.user,
                    findings=findings,
                    recommendations=recommendations
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def complete_document_revision(self, request, pk=None):
        """Step 6: Complete document revision."""
        cc_request = self.get_object()
        
        revision_id = request.data.get('revision_id')
        if not revision_id:
            return Response(
                {"error": "revision_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        document_revision = get_object_or_404(DocumentRevision, id=revision_id, request=cc_request)
        
        if not can_manage_documents(request.user, cc_request, document_revision):
            return Response(
                {"error": "You do not have permission to complete this document revision"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DocumentRevisionCompleteSerializer(data=request.data)
        if serializer.is_valid():
            try:
                revision_notes = serializer.validated_data.get('revision_notes', '')
                
                complete_document_revision(
                    request=cc_request,
                    actor=request.user,
                    document_revision=document_revision,
                    revision_notes=revision_notes
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def create_action_plan(self, request, pk=None):
        """Step 7: Create action plan."""
        cc_request = self.get_object()
        
        if not can_manage_action_plan(request.user, cc_request):
            return Response(
                {"error": "You do not have permission to create action plans"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ActionPlanCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                action_plans_data = serializer.validated_data['action_plans']
                
                # Convert to proper format
                action_plans = []
                for plan_data in action_plans_data:
                    from django.contrib.auth.models import User
                    responsible_person = User.objects.get(id=plan_data['responsible_person_id'])
                    action_plans.append({
                        'description': plan_data['description'],
                        'responsible_person': responsible_person,
                        'expected_timeline': plan_data['expected_timeline']
                    })
                
                action_plan_management(
                    request=cc_request,
                    actor=request.user,
                    action_plans=action_plans
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def complete_action_plan_item(self, request, pk=None):
        """Step 7: Complete an action plan item."""
        cc_request = self.get_object()
        
        action_plan_id = request.data.get('action_plan_id')
        if not action_plan_id:
            return Response(
                {"error": "action_plan_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action_plan = get_object_or_404(ActionPlan, id=action_plan_id, request=cc_request)
        
        if not can_manage_action_plan(request.user, cc_request, action_plan):
            return Response(
                {"error": "You do not have permission to complete this action plan"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ActionPlanCompleteSerializer(data=request.data)
        if serializer.is_valid():
            try:
                notes = serializer.validated_data.get('notes', '')
                
                complete_action_plan(
                    request=cc_request,
                    actor=request.user,
                    action_plan=action_plan,
                    notes=notes
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def qa_evaluation(self, request, pk=None):
        """Step 8: QA final evaluation."""
        cc_request = self.get_object()
        
        if not can_perform_qa_evaluation(request.user):
            return Response(
                {"error": "Only QA users can perform final evaluation"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = QAFinalEvaluationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                qa_final_evaluation(
                    request=cc_request,
                    actor=request.user,
                    cft_complete=serializer.validated_data['cft_complete'],
                    document_updates_complete=serializer.validated_data['document_updates_complete'],
                    risk_assessment_closed=serializer.validated_data['risk_assessment_closed'],
                    regulatory_filings_complete=serializer.validated_data['regulatory_filings_complete'],
                    comments=serializer.validated_data.get('comments', '')
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def qa_head_approval(self, request, pk=None):
        """Step 9: QA head approval."""
        cc_request = self.get_object()
        
        if not can_approve_qa_head(request.user):
            return Response(
                {"error": "Only QA head can perform this action"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = QAHeadApprovalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                approved = serializer.validated_data['approved']
                rejection_reason = serializer.validated_data.get('rejection_reason', '')
                
                qa_head_approval(
                    request=cc_request,
                    actor=request.user,
                    approved=approved,
                    rejection_reason=rejection_reason
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def verification(self, request, pk=None):
        """Step 10: Post-implementation verification."""
        cc_request = self.get_object()
        
        if not can_perform_verification(request.user):
            return Response(
                {"error": "Only QA users can perform verification"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = VerificationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                post_implementation_verification(
                    request=cc_request,
                    actor=request.user,
                    change_implemented=serializer.validated_data['change_implemented'],
                    training_conducted=serializer.validated_data['training_conducted'],
                    no_adverse_impact=serializer.validated_data['no_adverse_impact'],
                    comments=serializer.validated_data.get('comments', '')
                )
                
                response_serializer = ChangeControlRequestSerializer(cc_request)
                return Response(response_serializer.data)
            except ValidationError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CFTEvaluationViewSet(viewsets.ModelViewSet):
    """ViewSet for CFT Evaluation."""
    queryset = CFTEvaluation.objects.all()
    serializer_class = CFTEvaluationSerializer
    permission_classes = [IsAuthenticated]


class RiskAssessmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Risk Assessment."""
    queryset = RiskAssessment.objects.all()
    serializer_class = RiskAssessmentSerializer
    permission_classes = [IsAuthenticated]


class DocumentRevisionViewSet(viewsets.ModelViewSet):
    """ViewSet for Document Revision."""
    queryset = DocumentRevision.objects.all()
    serializer_class = DocumentRevisionSerializer
    permission_classes = [IsAuthenticated]


class ActionPlanViewSet(viewsets.ModelViewSet):
    """ViewSet for Action Plan."""
    queryset = ActionPlan.objects.all()
    serializer_class = ActionPlanSerializer
    permission_classes = [IsAuthenticated]


class WorkflowHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Workflow History (read-only)."""
    queryset = WorkflowHistory.objects.all()
    serializer_class = WorkflowHistorySerializer
    permission_classes = [IsAuthenticated]

