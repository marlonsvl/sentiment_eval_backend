import pandas as pd
import logging
from typing import Dict, List, Tuple, Any
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from core.models import Review, ReviewSentence, ModelPrediction, DataUploadLog

logger = logging.getLogger(__name__)

class CSVProcessor:
    """Service for processing CSV uploads and storing data"""
    
    REQUIRED_COLUMNS = [
        'review_id', 'review_text', 'review_sentence', 
        'gpt4', 'Gemini flash 2.5', 'perplexity', 'sentence_id'
    ]
    
    COLUMN_MAPPING = {
        'Gemini flash 2.5': 'gemini_prediction',
        'gpt4': 'gpt4_prediction',
        'perplexity': 'perplexity_prediction'
    }
    
    def __init__(self, upload_log: DataUploadLog):
        self.upload_log = upload_log
        self.processing_log = []
        self.successful_rows = 0
        self.failed_rows = 0
    
    def process_csv_file(self, file_path: str) -> Dict[str, Any]:
        """Main method to process CSV file"""
        try:
            self.upload_log.status = 'processing'
            self.upload_log.save()
            
            # Read and validate CSV
            df = self._read_csv(file_path, sep=';')
            #self._validate_csv_structure(df)
            
            # Clean and prepare data
            df = self._clean_data(df)
            
            # Process data in batches
            total_rows = len(df)
            self.upload_log.total_rows = total_rows
            self.upload_log.save()
            
            batch_size = 1000
            for i in range(0, total_rows, batch_size):
                batch_df = df.iloc[i:i + batch_size]
                self._process_batch(batch_df, i + 1)
            
            # Update final status
            self.upload_log.successful_rows = self.successful_rows
            self.upload_log.failed_rows = self.failed_rows
            self.upload_log.status = 'completed'
            self.upload_log.processing_log = {
                'logs': self.processing_log,
                'summary': {
                    'total_rows': total_rows,
                    'successful_rows': self.successful_rows,
                    'failed_rows': self.failed_rows
                }
            }
            self.upload_log.save()
            
            return {
                'success': True,
                'total_rows': total_rows,
                'successful_rows': self.successful_rows,
                'failed_rows': self.failed_rows,
                'processing_log': self.processing_log
            }
            
        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}")
            self.upload_log.status = 'failed'
            self.upload_log.error_message = str(e)
            self.upload_log.processing_log = {
                'error': str(e),
                'logs': self.processing_log
            }
            self.upload_log.save()
            
            return {
                'success': False,
                'error': str(e),
                'processing_log': self.processing_log
            }
    
    def _read_csv(self, file_path: str, sep:str) -> pd.DataFrame:
        """Read CSV file with error handling"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                    self._add_log(f"Successfully read CSV with {encoding} encoding")
                    return df
                except UnicodeDecodeError:
                    continue
            
            raise ValueError("Could not decode CSV file with common encodings")
            
        except Exception as e:
            raise ValueError(f"Failed to read CSV file: {str(e)}")
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare data for processing"""
        # Remove rows with missing critical data
        initial_count = len(df)
        
        # Drop rows where essential columns are null
        essential_columns = ['review_id', 'review_sentence', 'sentence_id']
        df = df.dropna(subset=essential_columns)
        
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            self._add_log(f"Dropped {dropped_count} rows with missing essential data")
        
        # Clean text fields
        text_columns = ['review_text', 'review_sentence', 'gpt4', 'Gemini flash 2.5', 'perplexity']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace(['nan', 'NaN', 'null', ''], None)
        
        # Clean ID fields
        df['review_id'] = df['review_id'].astype(str).str.strip()
        df['sentence_id'] = df['sentence_id'].astype(str).str.strip()
        
        return df
    
    def _process_batch(self, batch_df: pd.DataFrame, batch_start_row: int) -> None:
        """Process a batch of rows"""
        self._add_log(f"Processing batch starting at row {batch_start_row}")
        
        for index, row in batch_df.iterrows():
            try:
                with transaction.atomic():
                    self._process_single_row(row)
                    self.successful_rows += 1
            except Exception as e:
                self.failed_rows += 1
                error_msg = f"Row {index + 1}: {str(e)}"
                self._add_log(error_msg)
                logger.warning(error_msg)
    
    def _process_single_row(self, row: pd.Series) -> None:
        """Process a single CSV row"""
        # Get or create review
        review, created = Review.objects.get_or_create(
            review_id=row['review_id'],
            defaults={
                'review_text': row.get('review_text', '')
            }
        )
        
        if not created and row.get('review_text'):
            # Update review_text if it's different and not empty
            if review.review_text != row['review_text']:
                review.review_text = row['review_text']
                review.save()
        
        # Create or update review sentence
        sentence, created = ReviewSentence.objects.get_or_create(
            review=review,
            sentence_id=row['sentence_id'],
            defaults={
                'review_sentence': row['review_sentence'],
                'gpt4_prediction': row.get('gpt4'),
                'gemini_prediction': row.get('Gemini flash 2.5'),
                'perplexity_prediction': row.get('perplexity'),
            }
        )
        
        if not created:
            # Update existing sentence if data has changed
            updated = False
            if sentence.review_sentence != row['review_sentence']:
                sentence.review_sentence = row['review_sentence']
                updated = True
            
            if sentence.gpt4_prediction != row.get('gpt4'):
                sentence.gpt4_prediction = row.get('gpt4')
                updated = True
            
            if sentence.gemini_prediction != row.get('Gemini flash 2.5'):
                sentence.gemini_prediction = row.get('Gemini flash 2.5')
                updated = True
            
            if sentence.perplexity_prediction != row.get('perplexity'):
                sentence.perplexity_prediction = row.get('perplexity')
                updated = True
            
            if updated:
                sentence.save()
        
        # Create individual model prediction records for better analytics
        self._create_model_predictions(sentence, row)
    
    def _create_model_predictions(self, sentence: ReviewSentence, row: pd.Series) -> None:
        """Create individual model prediction records"""
        model_data = [
            ('gpt4', row.get('gpt4')),
            ('gemini', row.get('Gemini flash 2.5')),
            ('perplexity', row.get('perplexity')),
        ]
        
        for model_name, prediction_text in model_data:
            if prediction_text and prediction_text.strip():
                ModelPrediction.objects.update_or_create(
                    sentence=sentence,
                    model_name=model_name,
                    defaults={
                        'prediction_text': prediction_text,
                        'confidence_score': None  # Can be added later if available
                    }
                )
    
    def _add_log(self, message: str) -> None:
        """Add message to processing log"""
        self.processing_log.append({
            'timestamp': pd.Timestamp.now().isoformat(),
            'message': message
        })
        logger.info(f"CSV Processing: {message}")

class CSVValidator:
    """Utility class for CSV validation"""
    
    @staticmethod
    def validate_csv_file(file_path: str) -> Dict[str, Any]:
        """Quick validation of CSV file structure"""
        try:
            # Read first few rows to check structure
            df_sample = pd.read_csv(file_path, nrows=5, sep=';', encoding='utf-8')
            required_columns = CSVProcessor.REQUIRED_COLUMNS
            missing_columns = [col for col in required_columns if col not in df_sample.columns]
            
            # Get total row count
            total_rows = sum(1 for line in open(file_path)) - 1  # Subtract header
            
            return {
                'valid': len(missing_columns) == 0,
                'missing_columns': missing_columns,
                'total_columns': len(df_sample.columns),
                'total_rows': total_rows,
                'sample_data': df_sample.head(3).to_dict('records'),
                'columns': list(df_sample.columns)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'missing_columns': [],
                'total_columns': 0,
                'total_rows': 0,
                'sample_data': [],
                'columns': []
            }

class DataExporter:
    """Service for exporting evaluation results"""
    
    @staticmethod
    def export_evaluations_to_csv() -> pd.DataFrame:
        """Export all evaluations to CSV format"""
        from core.models import HumanEvaluation
        
        evaluations = HumanEvaluation.objects.select_related(
            'sentence__review', 'evaluator'
        ).all()
        
        data = []
        for eval_obj in evaluations:
            data.append({
                'sentence_id': eval_obj.sentence.sentence_id,
                'review_id': eval_obj.sentence.review.review_id,
                'review_sentence': eval_obj.sentence.review_sentence,
                'gpt4_prediction': eval_obj.sentence.gpt4_prediction,
                'gemini_prediction': eval_obj.sentence.gemini_prediction,
                'perplexity_prediction': eval_obj.sentence.perplexity_prediction,
                'evaluator': eval_obj.evaluator.username,
                'best_model': eval_obj.best_model,
                'alternative_solution': eval_obj.alternative_solution,
                'notes': eval_obj.notes,
                'evaluation_date': eval_obj.created_at.isoformat(),
            })
        
        return pd.DataFrame(data)
    
    
    
    def _validate_csv_structure(self, df: pd.DataFrame) -> None:
        """Validate CSV has required columns"""
        missing_columns = []
        
        for required_col in self.REQUIRED_COLUMNS:
            if required_col not in df.columns:
                missing_columns.append(required_col)
        
        if missing_columns:
            raise ValidationError(
                f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        if df.empty:
            raise ValidationError("CSV file is empty")
        
        self._add_