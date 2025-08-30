from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample users for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip creating users that already exist',
        )

    def handle(self, *args, **options):
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@example.com',
                'password': 'admin123',
                'role': 'admin',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True
            },
            {
                'username': 'researcher1',
                'email': 'researcher1@example.com',
                'password': 'researcher123',
                'role': 'researcher',
                'first_name': 'Research',
                'last_name': 'User'
            },
            {
                'username': 'evaluator1',
                'email': 'evaluator1@example.com',
                'password': 'evaluator123',
                'role': 'evaluator',
                'first_name': 'Evaluator',
                'last_name': 'One'
            },
            {
                'username': 'evaluator2',
                'email': 'evaluator2@example.com',
                'password': 'evaluator123',
                'role': 'evaluator',
                'first_name': 'Evaluator',
                'last_name': 'Two'
            }
        ]

        created_count = 0
        for user_data in users_data:
            username = user_data['username']
            
            if User.objects.filter(username=username).exists():
                if options['skip_existing']:
                    self.stdout.write(
                        self.style.WARNING(f'User {username} already exists, skipping...')
                    )
                    continue
                else:
                    self.stdout.write(
                        self.style.ERROR(f'User {username} already exists!')
                    )
                    continue
            
            password = user_data.pop('password')
            user = User.objects.create_user(**user_data)
            user.set_password(password)
            user.save()
            
            # Create auth token
            Token.objects.create(user=user)
            
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created user: {username} ({user.role})')
            )

        self.stdout.write(
            self.style.SUCCESS(f'\nCreated {created_count} users successfully!')
        )