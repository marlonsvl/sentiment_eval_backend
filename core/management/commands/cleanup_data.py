from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import ReviewSentence, HumanEvaluation, EvaluationSession

class Command(BaseCommand):
    help = 'Clean up incomplete or orphaned data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        with transaction.atomic():
            # Find sentences without any model predictions
            empty_sentences = ReviewSentence.objects.filter(
                gpt4_prediction__isnull=True,
                gemini_prediction__isnull=True,
                perplexity_prediction__isnull=True
            )

            # Find inactive sessions older than 7 days
            from django.utils import timezone
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=7)
            old_sessions = EvaluationSession.objects.filter(
                is_active=False,
                completed_at__lt=cutoff_date
            )

            if dry_run:
                self.stdout.write(
                    f'Would delete {empty_sentences.count()} empty sentences'
                )
                self.stdout.write(
                    f'Would delete {old_sessions.count()} old sessions'
                )
            else:
                # Delete empty sentences
                deleted_sentences = empty_sentences.count()
                empty_sentences.delete()
                
                # Delete old sessions
                deleted_sessions = old_sessions.count()
                old_sessions.delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Cleaned up:\n'
                        f'- {deleted_sentences} empty sentences\n'
                        f'- {deleted_sessions} old sessions'
                    )
                )