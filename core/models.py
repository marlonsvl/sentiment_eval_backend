from django.db import models
from django.contrib.auth.models import AbstractUser, User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from django.utils import timezone

class User(AbstractUser):
    """Extended user model for evaluators and researchers"""
    ROLE_CHOICES = [
        ('evaluator', 'Evaluator'),
        ('researcher', 'Researcher'),
        ('admin', 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='evaluator')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

class Review(models.Model):
    """Main review data from CSV"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review_id = models.CharField(max_length=100, db_index=True)
    review_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reviews'
        indexes = [
            models.Index(fields=['review_id']),
        ]

    def __str__(self):
        return f"Review {self.review_id}"

class ReviewSentence(models.Model):
    """Individual sentences from reviews with model predictions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='sentences')
    sentence_id = models.CharField(max_length=100, db_index=True)
    review_sentence = models.TextField()
    
    # Model predictions
    gpt4_prediction = models.TextField(blank=True, null=True)
    gemini_prediction = models.TextField(blank=True, null=True)
    perplexity_prediction = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'review_sentences'
        indexes = [
            models.Index(fields=['sentence_id']),
            models.Index(fields=['review']),
        ]
        unique_together = ['review', 'sentence_id']

    def __str__(self):
        return f"Sentence {self.sentence_id} from Review {self.review.review_id}"

class ModelPrediction(models.Model):
    """Detailed model predictions with metadata"""
    MODEL_CHOICES = [
        ('gpt4', 'GPT-4'),
        ('gemini', 'Gemini Flash 2.5'),
        ('perplexity', 'Perplexity'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sentence = models.ForeignKey(ReviewSentence, on_delete=models.CASCADE, related_name='predictions')
    model_name = models.CharField(max_length=20, choices=MODEL_CHOICES)
    prediction_text = models.TextField()
    confidence_score = models.FloatField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'model_predictions'
        indexes = [
            models.Index(fields=['sentence', 'model_name']),
            models.Index(fields=['model_name']),
        ]
        unique_together = ['sentence', 'model_name']

    def __str__(self):
        return f"{self.model_name} prediction for {self.sentence.sentence_id}"

class HumanEvaluation(models.Model):
    """Human evaluator assessments"""
    CHOICE_OPTIONS = [
        ('gpt4', 'GPT-4'),
        ('gemini', 'Gemini Flash 2.5'),
        ('perplexity', 'Perplexity'),
        ('none', 'None (Alternative Provided)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sentence = models.ForeignKey(ReviewSentence, on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='evaluations')
    
    best_model = models.CharField(max_length=20, choices=CHOICE_OPTIONS)
    alternative_solution = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Metadata
    evaluation_time_seconds = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'human_evaluations'
        indexes = [
            models.Index(fields=['sentence', 'evaluator']),
            models.Index(fields=['evaluator']),
            models.Index(fields=['best_model']),
        ]
        unique_together = ['sentence', 'evaluator']

    def __str__(self):
        return f"Evaluation by {self.evaluator.username} for {self.sentence.sentence_id}"

class EvaluationSession(models.Model):
    """Track evaluation sessions for progress monitoring"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    
    total_sentences = models.IntegerField(default=0)
    completed_sentences = models.IntegerField(default=0)
    
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'evaluation_sessions'
        indexes = [
            models.Index(fields=['evaluator', 'is_active']),
        ]

    @property
    def completion_percentage(self):
        if self.total_sentences == 0:
            return 0
        return round((self.completed_sentences / self.total_sentences) * 100, 2)

    def __str__(self):
        return f"Session for {self.evaluator.username} - {self.completion_percentage}%"

class DataUploadLog(models.Model):
    """Log CSV uploads and processing status"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploads')
    
    filename = models.CharField(max_length=255)
    #file_size_bytes = models.BigIntegerField()
    
    # Processing status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Results
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    
    error_message = models.TextField(blank=True, null=True)
    processing_log = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'data_upload_logs'
        indexes = [
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Upload: {self.filename} - {self.status}"
    