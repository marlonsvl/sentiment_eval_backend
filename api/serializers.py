from rest_framework import serializers
from django.contrib.auth import authenticate
from core.models import (
    User, Review, ReviewSentence, ModelPrediction, 
    HumanEvaluation, EvaluationSession, DataUploadLog
)

class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'created_at']
        read_only_fields = ['id', 'created_at']

class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user creation"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name', 'role']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    """Serializer for user authentication"""
    username = serializers.CharField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include username and password')

class ModelPredictionSerializer(serializers.ModelSerializer):
    """Serializer for model predictions"""
    class Meta:
        model = ModelPrediction
        fields = ['id', 'model_name', 'prediction_text', 'confidence_score', 'created_at']
        read_only_fields = ['id', 'created_at']

class ReviewSentenceSerializer(serializers.ModelSerializer):
    """Serializer for review sentences with predictions"""
    predictions = ModelPredictionSerializer(many=True, read_only=True)
    gpt4_prediction = serializers.CharField(read_only=True)
    gemini_prediction = serializers.CharField(read_only=True)
    perplexity_prediction = serializers.CharField(read_only=True)
    
    class Meta:
        model = ReviewSentence
        fields = [
            'id', 'sentence_id', 'review_sentence', 
            'gpt4_prediction', 'gemini_prediction', 'perplexity_prediction',
            'predictions', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for reviews with sentences"""
    sentences = ReviewSentenceSerializer(many=True, read_only=True)
    sentences_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = ['id', 'review_id', 'review_text', 'sentences', 'sentences_count', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_sentences_count(self, obj):
        return obj.sentences.count()

class HumanEvaluationSerializer(serializers.ModelSerializer):
    """Serializer for human evaluations"""
    evaluator_name = serializers.CharField(source='evaluator.username', read_only=True)
    sentence_text = serializers.CharField(source='sentence.review_sentence', read_only=True)
    
    class Meta:
        model = HumanEvaluation
        fields = [
            'id', 'sentence', 'evaluator', 'evaluator_name', 'sentence_text',
            'best_model', 'alternative_solution', 'notes', 
            'evaluation_time_seconds', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'evaluator', 'created_at', 'updated_at']

class HumanEvaluationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating human evaluations"""
    class Meta:
        model = HumanEvaluation
        fields = ['id','sentence', 'evaluator', 'best_model', 'alternative_solution',
                  'notes', 'evaluation_time_seconds',
                  'created_at', 'updated_at'
                  ]
    
    def validate(self, attrs):
        # If best_model is 'none', alternative_solution is required
        if attrs.get('best_model') == 'none' and not attrs.get('alternative_solution'):
            raise serializers.ValidationError({
                'alternative_solution': 'Alternative solution is required when no model is selected as best.'
            })
        return attrs

class EvaluationSessionSerializer(serializers.ModelSerializer):
    """Serializer for evaluation sessions"""
    evaluator_name = serializers.CharField(source='evaluator.username', read_only=True)
    completion_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = EvaluationSession
        fields = [
            'id', 'evaluator', 'evaluator_name', 'total_sentences', 'completed_sentences',
            'completion_percentage', 'started_at', 'last_activity', 'completed_at', 'is_active'
        ]
        read_only_fields = ['id', 'evaluator', 'started_at', 'last_activity', 'completed_at']

class DataUploadLogSerializer(serializers.ModelSerializer):
    """Serializer for data upload logs"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = DataUploadLog
        fields = [
            'id', 'uploaded_by', 'uploaded_by_name', 'filename', 'file_size_bytes',
            'status', 'total_rows', 'successful_rows', 'failed_rows', 'success_rate',
            'error_message', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'uploaded_by', 'created_at', 'completed_at']
    
    def get_success_rate(self, obj):
        if obj.total_rows == 0:
            return 0
        return round((obj.successful_rows / obj.total_rows) * 100, 2)

class CSVUploadSerializer(serializers.Serializer):
    """Serializer for CSV file upload"""
    file = serializers.FileField()
    
    def validate_file(self, value):
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError('File must be a CSV file.')
        
        # Check file size (50MB limit)
        if value.size > 52428800:
            raise serializers.ValidationError('File size must be less than 50MB.')
        
        return value

class SentenceEvaluationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for sentence evaluation view"""
    review_text = serializers.CharField(source='review.review_text', read_only=True)
    review_id = serializers.CharField(source='review.review_id', read_only=True)
    evaluations = HumanEvaluationSerializer(many=True, read_only=True)
    my_evaluation = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewSentence
        fields = [
            'id', 'sentence_id', 'review_sentence', 'review_text', 'review_id',
            'gpt4_prediction', 'gemini_prediction', 'perplexity_prediction',
            'evaluations', 'my_evaluation', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_my_evaluation(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                evaluation = obj.evaluations.get(evaluator=request.user)
                return HumanEvaluationSerializer(evaluation).data
            except HumanEvaluation.DoesNotExist:
                return None
        return None

class ModelPerformanceStatsSerializer(serializers.Serializer):
    """Serializer for model performance statistics"""
    model_name = serializers.CharField()
    total_evaluations = serializers.IntegerField()
    times_selected_best = serializers.IntegerField()
    percentage_best = serializers.FloatField()
    avg_confidence = serializers.FloatField(allow_null=True)

class EvaluatorAgreementSerializer(serializers.Serializer):
    """Serializer for evaluator agreement statistics"""
    sentence_id = serializers.CharField()
    evaluator_1_choice = serializers.CharField()
    evaluator_2_choice = serializers.CharField()
    agreement = serializers.BooleanField()
    sentence_text = serializers.CharField()