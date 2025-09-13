import os
import tempfile
from django.contrib.auth import login, logout
from django.db.models import Count, Q, Avg
from django.http import HttpResponse
from django.conf import settings
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication  # Added import
from rest_framework.permissions import IsAuthenticated  # Added import
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
import pandas as pd
import logging
from django.utils import timezone

from core.models import (
    User, Review, ReviewSentence, ModelPrediction, 
    HumanEvaluation, EvaluationSession, DataUploadLog
)
from api.serializers import (
    UserSerializer, UserCreateSerializer, LoginSerializer,
    ReviewSerializer, ReviewSentenceSerializer, HumanEvaluationSerializer,
    HumanEvaluationCreateSerializer, EvaluationSessionSerializer,
    DataUploadLogSerializer, CSVUploadSerializer, SentenceEvaluationDetailSerializer,
    ModelPerformanceStatsSerializer, EvaluatorAgreementSerializer
)
from services.csv_processor import CSVProcessor, CSVValidator, DataExporter

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

# API Root View
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def api_root(request, format=None):
    """
    API Root - Shows all available endpoints
    """
    return Response({
        'message': 'Sentiment Evaluation API',
        'version': '1.0',
        'endpoints': {
            'authentication': {
                'register': reverse('register', request=request, format=format),
                'login': reverse('login', request=request, format=format),
                'logout': reverse('logout', request=request, format=format),
                'current_user': reverse('current-user', request=request, format=format),
            },
            'data_management': {
                'upload_csv': reverse('upload-csv', request=request, format=format),
                'validate_csv': reverse('validate-csv', request=request, format=format),
                'export_evaluations': reverse('export-evaluations', request=request, format=format),
            },
            'analytics': {
                'model_performance': reverse('model-performance', request=request, format=format),
                'evaluator_agreement': reverse('evaluator-agreement', request=request, format=format),
                'dashboard_stats': reverse('dashboard-stats', request=request, format=format),
            },
            'resources': {
                'reviews': reverse('review-list', request=request, format=format),
                'sentences': reverse('reviewsentence-list', request=request, format=format),
                'evaluations': reverse('evaluation-list', request=request, format=format),
                'sessions': reverse('session-list', request=request, format=format),
                'upload_logs': reverse('datauploadlog-list', request=request, format=format),
            }
        },
        'documentation': {
            'description': 'This API provides endpoints for sentiment evaluation tasks including data upload, human evaluations, and analytics.',
            'authentication': 'Token-based authentication required for most endpoints',
            'pagination': 'Most list endpoints support pagination with page_size parameter (default: 20, max: 100)'
        }
    })

# Authentication Views
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    """Register a new user"""
    serializer = UserCreateSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    """User login"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Changed from default to explicit
def logout_user(request):
    """User logout"""
    try:
        # Delete the user's token
        Token.objects.filter(user=request.user).delete()
        logout(request)
        return Response({'message': 'Successfully logged out'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Changed from default to explicit
def current_user(request):
    """Get current user data"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

# Main ViewSets
class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for reviews"""
    queryset = Review.objects.all().prefetch_related('sentences')
    serializer_class = ReviewSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['review_id']
    search_fields = ['review_id', 'review_text']
    ordering_fields = ['created_at', 'review_id']
    ordering = ['-created_at']
    
    # Added authentication classes
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['get'])
    def sentences(self, request, pk=None):
        """Get all sentences for a specific review"""
        review = self.get_object()
        sentences = review.sentences.all()
        serializer = ReviewSentenceSerializer(sentences, many=True)
        return Response(serializer.data)

class ReviewSentenceViewSet(viewsets.ModelViewSet):
    """ViewSet for review sentences"""
    #queryset = ReviewSentence.objects.all().select_related('review')
    queryset = ReviewSentence.objects.all()
    serializer_class = SentenceEvaluationDetailSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['review__review_id', 'sentence_id']
    search_fields = ['review_sentence', 'sentence_id']
    ordering_fields = ['created_at', 'sentence_id']
    ordering = ['created_at']
    
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter for unevaluated sentences by current user
        unevaluated_only = self.request.query_params.get('unevaluated_only', None)
        if unevaluated_only and unevaluated_only.lower() == 'true':
            # Exclude sentences that have been evaluated by the current user
            queryset = queryset.exclude(
                evaluations__evaluator=self.request.user
            )
        
        return queryset
    
    
    
    # Added authentication classes
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'])
    def unevaluated(self, request):
        """Get sentences that haven't been evaluated by the current user"""
        queryset = self.get_queryset().exclude(
            evaluations__evaluator=request.user
        ).order_by('?')  # Random order to prevent bias
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def next_for_evaluation(self, request):
        """Get next sentence for evaluation"""
        evaluated_sentence_ids = HumanEvaluation.objects.filter(
            evaluator=request.user
        ).values_list('sentence_id', flat=True)
        
        next_sentence = self.queryset.exclude(id__in=evaluated_sentence_ids).first()
        
        if next_sentence:
            serializer = self.get_serializer(next_sentence)
            return Response(serializer.data)
        else:
            return Response({'message': 'No more sentences to evaluate'}, status=status.HTTP_204_NO_CONTENT)

class HumanEvaluationViewSet(viewsets.ModelViewSet):
    """ViewSet for human evaluations"""
    serializer_class = HumanEvaluationSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['best_model', 'evaluator']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    # Added authentication classes
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return HumanEvaluation.objects.filter(evaluator=self.request.user).select_related(
            'sentence__review', 'evaluator'
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return HumanEvaluationCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return HumanEvaluationUpdateSerializer  # Use the new update serializer
        elif self.action in ['list', 'retrieve', 'my_evaluations']:
            return HumanEvaluationDetailSerializer
        return HumanEvaluationSerializer

    def perform_create(self, serializer):
        serializer.save(evaluator=self.request.user)
        # 🔹 Update active session for this user
        try:
            session = EvaluationSession.objects.filter(
                evaluator=self.request.user,
                is_active=True
            ).latest('started_at')  # get most recent active session

            # Update completed_sentences count
            session.completed_sentences = HumanEvaluation.objects.filter(
                evaluator=self.request.user
            ).count()

            # Update last_activity timestamp
            session.last_activity = timezone.now()

            # Mark as complete if done
            if session.completed_sentences >= session.total_sentences:
                session.is_active = False
                session.completed_at = timezone.now()

            session.save()
        except EvaluationSession.DoesNotExist:
            # No active session — you can decide to ignore or auto-create
            pass

    @action(detail=False, methods=['get'])
    def my_stats(self, request):
        """Get current user's evaluation statistics"""
        user = request.user
        user_evaluations = self.get_queryset()
        
        # Count unevaluated sentences
        unevaluated_count = ReviewSentence.objects.exclude(
            evaluations__evaluator=user
        ).count()
        
        # Count evaluations by this user
        total_evaluations = HumanEvaluation.objects.filter(
            evaluator=user
        ).count()
        
        # Count active sessions
        active_sessions = EvaluationSession.objects.filter(
            evaluator=user,
            is_active=True
        ).count() if hasattr(request, 'evaluation_sessions') else 0
        
        #total_evaluations = user_evaluations.count()
        model_choices = user_evaluations.values('best_model').annotate(count=Count('best_model'))
        
        stats = {
            'unevaluated_sentences': unevaluated_count,
            'active_sessions': active_sessions,
            'total_evaluations': total_evaluations,
            'model_choices': list(model_choices),
            'completion_rate': self._calculate_completion_rate(request.user)
        }
        
        return Response(stats)

    def _calculate_completion_rate(self, user):
        total_sentences = ReviewSentence.objects.count()
        user_evaluations = HumanEvaluation.objects.filter(evaluator=user).count()
        
        if total_sentences == 0:
            return 0
        
        return round((user_evaluations / total_sentences) * 100, 2)
    
    def perform_update(self, serializer):
        # Ensure user can only update their own evaluations
        if serializer.instance.evaluator != self.request.user:
            raise Response({'error': 'You can only update your own evaluations'}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer.save()
        # Update session activity timestamp
        try:
            session = EvaluationSession.objects.filter(
                evaluator=self.request.user,
                is_active=True
            ).latest('started_at')
            session.last_activity = timezone.now()
            session.save()
        except EvaluationSession.DoesNotExist:
            pass
    
    @action(detail=False, methods=['get'])
    def my_evaluations(self, request):
        """Get all evaluations made by the current user for editing"""
        user_evaluations = self.get_queryset().select_related(
            'sentence__review'
        ).order_by('-created_at')
        
        page = self.paginate_queryset(user_evaluations)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(user_evaluations, many=True)
        return Response(serializer.data)

class HumanEvaluationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for human evaluations with nested sentence data"""
    sentence = SentenceEvaluationDetailSerializer(read_only=True)
    evaluator_name = serializers.CharField(source='evaluator.username', read_only=True)
    
    class Meta:
        model = HumanEvaluation
        fields = [
            'id', 'sentence', 'evaluator', 'evaluator_name',
            'best_model', 'alternative_solution', 'notes',
            'evaluation_time_seconds', 'created_at', 'updated_at'
        ]

class HumanEvaluationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating evaluations - accepts update data, returns detailed response"""
    
    class Meta:
        model = HumanEvaluation
        fields = [
            'best_model', 'alternative_solution', 'notes', 'evaluation_time_seconds'
        ]
    
    def to_representation(self, instance):
        """Use detailed serializer for the response"""
        return HumanEvaluationDetailSerializer(instance, context=self.context).data



class EvaluationSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for evaluation sessions"""
    serializer_class = EvaluationSessionSerializer
    pagination_class = StandardResultsSetPagination
    
    # Added authentication classes
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EvaluationSession.objects.filter(evaluator=self.request.user)

    @action(detail=False, methods=['post'])
    def start_session(self, request):
        """Start a new evaluation session"""
        # End any active sessions
        EvaluationSession.objects.filter(evaluator=request.user, is_active=True).update(is_active=False)
        
        total_sentences = ReviewSentence.objects.count()
        completed_sentences = HumanEvaluation.objects.filter(evaluator=request.user).count()
        
        session = EvaluationSession.objects.create(
            evaluator=request.user,
            total_sentences=total_sentences,
            completed_sentences=completed_sentences
        )
        
        serializer = self.get_serializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Update session progress"""
        session = self.get_object()
        
        if not session.is_active:
            return Response({'error': 'Session is not active'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Recalculate progress
        completed_sentences = HumanEvaluation.objects.filter(evaluator=request.user).count()
        session.completed_sentences = completed_sentences
        
        # Check if session is complete
        if completed_sentences >= session.total_sentences:
            session.is_active = False
            from django.utils import timezone
            session.completed_at = timezone.now()
        
        session.save()
        
        serializer = self.get_serializer(session)
        return Response(serializer.data)

# Data Management Views
class DataUploadLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for data upload logs"""
    queryset = DataUploadLog.objects.all().select_related('uploaded_by')
    serializer_class = DataUploadLogSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'uploaded_by']
    ordering = ['-created_at']
    
    # Added authentication classes
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Changed to explicit
def upload_csv(request):
    """Upload and process CSV file"""
    if not request.user.role in ['admin', 'researcher']:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = CSVUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    uploaded_file = serializer.validated_data['file']
    
    # Create upload log
    upload_log = DataUploadLog.objects.create(
        uploaded_by=request.user,
        filename=uploaded_file.name,
        file_size_bytes=uploaded_file.size,
        status='pending'
    )
    
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # Validate CSV structure first
        validation_result = CSVValidator.validate_csv_file(temp_file_path)
        if not validation_result['valid']:
            upload_log.status = 'failed'
            upload_log.error_message = f"Invalid CSV structure: {', '.join(validation_result['missing_columns'])}"
            upload_log.save()
            os.unlink(temp_file_path)
            return Response({'error': upload_log.error_message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Process CSV
        processor = CSVProcessor(upload_log)
        result = processor.process_csv_file(temp_file_path)
        
        # Cleanup
        os.unlink(temp_file_path)
        
        if result['success']:
            return Response({
                'message': 'CSV processed successfully',
                'upload_log_id': upload_log.id,
                'summary': {
                    'total_rows': result['total_rows'],
                    'successful_rows': result['successful_rows'],
                    'failed_rows': result['failed_rows']
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        upload_log.status = 'failed'
        upload_log.error_message = str(e)
        upload_log.save()
        
        # Cleanup temp file if it exists
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Changed to explicit
def validate_csv(request):
    """Validate CSV structure without processing"""
    serializer = CSVUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    uploaded_file = serializer.validated_data['file']
    
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # Validate CSV structure
        validation_result = CSVValidator.validate_csv_file(temp_file_path)
        
        # Cleanup
        os.unlink(temp_file_path)
        
        return Response(validation_result)
    
    except Exception as e:
        logger.error(f"CSV validation error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Analytics and Reporting Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Changed to explicit
def model_performance_stats(request):
    """Get model performance statistics"""
    stats = []
    models = ['gpt4', 'gemini', 'perplexity']
    
    total_evaluations = HumanEvaluation.objects.count()
    
    for model in models:
        times_selected = HumanEvaluation.objects.filter(best_model=model).count()
        percentage = (times_selected / total_evaluations * 100) if total_evaluations > 0 else 0
        
        # Get average confidence if available
        avg_confidence = ModelPrediction.objects.filter(model_name=model).aggregate(
            avg_conf=Avg('confidence_score')
        )['avg_conf']
        
        stats.append({
            'model_name': model,
            'total_evaluations': total_evaluations,
            'times_selected_best': times_selected,
            'percentage_best': round(percentage, 2),
            'avg_confidence': round(avg_confidence, 2) if avg_confidence else None
        })
    
    serializer = ModelPerformanceStatsSerializer(stats, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Changed to explicit
def evaluator_agreement(request):
    """Get evaluator agreement statistics"""
    evaluators = User.objects.filter(role='evaluator', evaluations__isnull=False).distinct()
    
    if evaluators.count() < 2:
        return Response({'error': 'Need at least 2 evaluators with evaluations'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get sentences evaluated by multiple evaluators
    sentences_with_multiple_evals = ReviewSentence.objects.annotate(
        eval_count=Count('evaluations')
    ).filter(eval_count__gte=2)
    
    agreement_data = []
    total_compared = 0
    agreements = 0
    
    for sentence in sentences_with_multiple_evals:
        evaluations = list(sentence.evaluations.all()[:2])  # Compare first 2 evaluators
        
        if len(evaluations) == 2:
            eval1, eval2 = evaluations
            agreement = eval1.best_model == eval2.best_model
            
            if agreement:
                agreements += 1
            
            total_compared += 1
            
            agreement_data.append({
                'sentence_id': sentence.sentence_id,
                'evaluator_1_choice': eval1.best_model,
                'evaluator_2_choice': eval2.best_model,
                'agreement': agreement,
                'sentence_text': sentence.review_sentence[:100] + '...' if len(sentence.review_sentence) > 100 else sentence.review_sentence
            })
    
    agreement_percentage = (agreements / total_compared * 100) if total_compared > 0 else 0
    
    return Response({
        'overall_agreement_percentage': round(agreement_percentage, 2),
        'total_compared': total_compared,
        'agreements': agreements,
        'disagreements': total_compared - agreements,
        'detailed_comparisons': agreement_data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Changed to explicit
def export_evaluations(request):
    """Export evaluations to CSV"""
    if not request.user.role in ['admin', 'researcher']:
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        df = DataExporter.export_evaluations_to_csv()
        
        # Create HTTP response with CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="evaluations_export.csv"'
        
        df.to_csv(response, index=False)
        return response
    
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Changed to explicit
def dashboard_stats(request):
    """Get dashboard statistics"""
    total_reviews = Review.objects.count()
    total_sentences = ReviewSentence.objects.count()
    total_evaluations = HumanEvaluation.objects.count()
    total_evaluators = User.objects.filter(role='evaluator').count()
    
    # Progress by evaluator
    evaluator_progress = []
    for evaluator in User.objects.filter(role='evaluator'):
        user_evaluations = HumanEvaluation.objects.filter(evaluator=evaluator).count()
        progress_percentage = (user_evaluations / total_sentences * 100) if total_sentences > 0 else 0
        
        evaluator_progress.append({
            'evaluator': evaluator.username,
            'evaluations_completed': user_evaluations,
            'progress_percentage': round(progress_percentage, 2)
        })
    
    return Response({
        'total_reviews': total_reviews,
        'total_sentences': total_sentences,
        'total_evaluations': total_evaluations,
        'total_evaluators': total_evaluators,
        'evaluator_progress': evaluator_progress,
        'completion_rate': round((total_evaluations / (total_sentences * total_evaluators) * 100), 2) if total_sentences > 0 and total_evaluators > 0 else 0
    })