from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Count
from core.models import (
    User, Review, ReviewSentence, ModelPrediction, 
    HumanEvaluation, EvaluationSession, DataUploadLog
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""
    list_display = ['username', 'email', 'role', 'first_name', 'last_name', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role',)}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'email', 'first_name', 'last_name')}),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            evaluation_count=Count('evaluations')
        )

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin interface for Review model"""
    list_display = ['review_id', 'truncated_text', 'sentences_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review_id', 'review_text']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    def truncated_text(self, obj):
        """Show truncated review text"""
        if len(obj.review_text) > 50:
            return obj.review_text[:50] + "..."
        return obj.review_text
    truncated_text.short_description = 'Reviewer Text'
    
    def sentences_count(self, obj):
        """Show count of sentences"""
        return obj.sentences.count()
    sentences_count.short_description = 'Sentences'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('sentences')

class ModelPredictionInline(admin.TabularInline):
    """Inline admin for model predictions"""
    model = ModelPrediction
    extra = 0
    readonly_fields = ['created_at']

class HumanEvaluationInline(admin.TabularInline):
    """Inline admin for human evaluations"""
    model = HumanEvaluation
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = ['evaluator', 'best_model', 'alternative_solution', 'notes']

@admin.register(ReviewSentence)
class ReviewSentenceAdmin(admin.ModelAdmin):
    """Admin interface for ReviewSentence model"""
    list_display = [
        'sentence_id', 'review_review_id', 'truncated_sentence', 
        'has_gpt4', 'has_gemini', 'has_perplexity', 'evaluations_count', 'created_at'
    ]
    list_filter = ['created_at', 'review__review_id']
    search_fields = ['sentence_id', 'review_sentence', 'review__review_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ModelPredictionInline, HumanEvaluationInline]
    
    fieldsets = [
        (None, {
            'fields': ['review', 'sentence_id', 'review_sentence']
        }),
        ('Model Predictions', {
            'fields': ['gpt4_prediction', 'gemini_prediction', 'perplexity_prediction'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def review_review_id(self, obj):
        """Show reviewer ID from related review"""
        return obj.review.review_id
    review_review_id.short_description = 'Reviewer ID'
    review_review_id.admin_order_field = 'review__review_id'
    
    def truncated_sentence(self, obj):
        """Show truncated sentence text"""
        if len(obj.review_sentence) > 60:
            return obj.review_sentence[:60] + "..."
        return obj.review_sentence
    truncated_sentence.short_description = 'Sentence'
    
    def has_gpt4(self, obj):
        """Check if GPT-4 prediction exists"""
        return bool(obj.gpt4_prediction)
    has_gpt4.boolean = True
    has_gpt4.short_description = 'GPT-4'
    
    def has_gemini(self, obj):
        """Check if Gemini prediction exists"""
        return bool(obj.gemini_prediction)
    has_gemini.boolean = True
    has_gemini.short_description = 'Gemini'
    
    def has_perplexity(self, obj):
        """Check if Perplexity prediction exists"""
        return bool(obj.perplexity_prediction)
    has_perplexity.boolean = True
    has_perplexity.short_description = 'Perplexity'
    
    def evaluations_count(self, obj):
        """Show count of evaluations"""
        return obj.evaluations.count()
    evaluations_count.short_description = 'Evaluations'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('review').prefetch_related('evaluations')

@admin.register(ModelPrediction)
class ModelPredictionAdmin(admin.ModelAdmin):
    """Admin interface for ModelPrediction model"""
    list_display = ['sentence_id_display', 'model_name', 'truncated_prediction', 'confidence_score', 'created_at']
    list_filter = ['model_name', 'created_at']
    search_fields = ['sentence__sentence_id', 'prediction_text']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def sentence_id_display(self, obj):
        """Show sentence ID"""
        return obj.sentence.sentence_id
    sentence_id_display.short_description = 'Sentence ID'
    sentence_id_display.admin_order_field = 'sentence__sentence_id'
    
    def truncated_prediction(self, obj):
        """Show truncated prediction text"""
        if len(obj.prediction_text) > 50:
            return obj.prediction_text[:50] + "..."
        return obj.prediction_text
    truncated_prediction.short_description = 'Prediction'

@admin.register(HumanEvaluation)
class HumanEvaluationAdmin(admin.ModelAdmin):
    """Admin interface for HumanEvaluation model"""
    list_display = [
        'sentence_id_display', 'evaluator', 'best_model', 'has_alternative', 
        'evaluation_time_seconds', 'created_at'
    ]
    list_filter = ['best_model', 'evaluator', 'created_at']
    search_fields = ['sentence__sentence_id', 'evaluator__username', 'alternative_solution']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        (None, {
            'fields': ['sentence', 'evaluator', 'best_model']
        }),
        ('Additional Information', {
            'fields': ['alternative_solution', 'notes', 'evaluation_time_seconds']
        }),
        ('Metadata', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def sentence_id_display(self, obj):
        """Show sentence ID"""
        return obj.sentence.sentence_id
    sentence_id_display.short_description = 'Sentence ID'
    sentence_id_display.admin_order_field = 'sentence__sentence_id'
    
    def has_alternative(self, obj):
        """Check if alternative solution exists"""
        return bool(obj.alternative_solution)
    has_alternative.boolean = True
    has_alternative.short_description = 'Has Alternative'

@admin.register(EvaluationSession)
class EvaluationSessionAdmin(admin.ModelAdmin):
    """Admin interface for EvaluationSession model"""
    list_display = [
        'evaluator', 'completion_percentage_display', 'total_sentences', 
        'completed_sentences', 'is_active', 'started_at', 'duration'
    ]
    list_filter = ['is_active', 'started_at', 'completed_at']
    search_fields = ['evaluator__username']
    ordering = ['-started_at']
    readonly_fields = ['started_at', 'last_activity', 'completed_at', 'completion_percentage']
    
    def completion_percentage_display(self, obj):
        """Show completion percentage with progress bar"""
        percentage = obj.completion_percentage
        color = 'green' if percentage == 100 else 'orange' if percentage >= 50 else 'red'
        return format_html(
            '<div style="width: 100px; background: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background: {}; height: 20px; border-radius: 3px; text-align: center; color: white;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    completion_percentage_display.short_description = 'Progress'
    
    def duration(self, obj):
        """Show session duration"""
        if obj.completed_at:
            duration = obj.completed_at - obj.started_at
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            from django.utils import timezone
            duration = timezone.now() - obj.started_at
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d} (ongoing)"
    duration.short_description = 'Duration'

@admin.register(DataUploadLog)
class DataUploadLogAdmin(admin.ModelAdmin):
    """Admin interface for DataUploadLog model"""
    list_display = [
        'filename', 'uploaded_by', 'status', 'success_rate_display', 
        'total_rows', 'file_size_mb', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'uploaded_by']
    search_fields = ['filename', 'uploaded_by__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'completed_at', 'processing_log']
    
    fieldsets = [
        ('File Information', {
            'fields': ['uploaded_by', 'filename', 'file_size_bytes']
        }),
        ('Processing Status', {
            'fields': ['status', 'total_rows', 'successful_rows', 'failed_rows']
        }),
        ('Error Information', {
            'fields': ['error_message'],
            'classes': ['collapse']
        }),
        ('Processing Log', {
            'fields': ['processing_log'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'completed_at'],
            'classes': ['collapse']
        })
    ]
    
    def success_rate_display(self, obj):
        """Show success rate with color coding"""
        if obj.total_rows == 0:
            return "N/A"
        
        success_rate = (obj.successful_rows / obj.total_rows) * 100
        color = 'green' if success_rate == 100 else 'orange' if success_rate >= 80 else 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, success_rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def file_size_mb(self, obj):
        """Show file size in MB"""
        return f"{obj.file_size_bytes / (1024 * 1024):.2f} MB"
    file_size_mb.short_description = 'File Size'

# Customize admin site
admin.site.site_header = "Sentiment Analysis Evaluation Admin"
admin.site.site_title = "Sentiment Eval Admin"
admin.site.index_title = "Administration Dashboard"