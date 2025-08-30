from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from core.models import DataUploadLog
from services.csv_processor import CSVProcessor, CSVValidator
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Process CSV file and load data into database'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file_path',
            type=str,
            help='Path to the CSV file to process'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for the upload log (defaults to first superuser)',
            default=None
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate the CSV structure without processing'
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file_path']
        user_id = options.get('user_id')
        validate_only = options.get('validate_only', False)

        # Check if file exists
        if not os.path.exists(csv_file_path):
            raise CommandError(f'File "{csv_file_path}" does not exist.')

        # Get user for upload log
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise CommandError(f'User with ID {user_id} does not exist.')
        else:
            # Use first superuser
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                raise CommandError('No superuser found. Please create one or specify --user-id')

        self.stdout.write(f'Processing CSV file: {csv_file_path}')

        if validate_only:
            # Just validate the file
            self.stdout.write('Validating CSV structure...')
            validation_result = CSVValidator.validate_csv_file(csv_file_path)
            
            if validation_result['valid']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ CSV is valid! Found {validation_result["total_rows"]} rows '
                        f'with {validation_result["total_columns"]} columns'
                    )
                )
                self.stdout.write('Sample data:')
                for i, sample in enumerate(validation_result['sample_data'], 1):
                    self.stdout.write(f'  Row {i}: {sample}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ CSV validation failed: {validation_result.get("error", "Unknown error")}')
                )
                if validation_result['missing_columns']:
                    self.stdout.write(f'Missing columns: {", ".join(validation_result["missing_columns"])}')
            return

        # Create upload log entry
        upload_log = DataUploadLog.objects.create(
            uploaded_by=user,
            filename=os.path.basename(csv_file_path),
            #file_path=csv_file_path,
            status='pending'
        )

        self.stdout.write(f'Created upload log with ID: {upload_log.id}')

        # Process the CSV
        processor = CSVProcessor(upload_log)
        result = processor.process_csv_file(csv_file_path)

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Successfully processed CSV!\n'
                    f'  Total rows: {result["total_rows"]}\n'
                    f'  Successful: {result["successful_rows"]}\n'
                    f'  Failed: {result["failed_rows"]}'
                )
            )
            
            if result['failed_rows'] > 0:
                self.stdout.write(
                    self.style.WARNING(f'⚠ {result["failed_rows"]} rows failed to process')
                )
                # Show some error logs
                error_logs = [log for log in result['processing_log'] 
                             if 'Row' in log.get('message', '')][:5]
                for log in error_logs:
                    self.stdout.write(f'  {log["message"]}')
        else:
            self.stdout.write(
                self.style.ERROR(f'✗ CSV processing failed: {result["error"]}')
            )
            raise CommandError('CSV processing failed')