import os
from django.core.management.base import BaseCommand
from django.conf import settings
from services.csv_processor import DataExporter

class Command(BaseCommand):
    help = 'Export evaluation data to CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='evaluations_export.csv',
            help='Output filename'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['evaluations', 'performance'],
            default='evaluations',
            help='Type of export'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        export_type = options['type']

        try:
            if export_type == 'evaluations':
                df = DataExporter.export_evaluations_to_csv()
                self.stdout.write('Exporting evaluations data...')
            else:
                df = DataExporter.export_model_performance_stats()
                self.stdout.write('Exporting performance stats...')

            # Save to file
            output_path = os.path.join(settings.BASE_DIR, output_file)
            df.to_csv(output_path, index=False)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully exported {len(df)} records to {output_path}'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Export failed: {str(e)}')
            )