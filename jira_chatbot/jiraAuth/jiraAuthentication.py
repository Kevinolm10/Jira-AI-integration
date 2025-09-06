# ai_chat/authentication.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.conf import settings
from atlassian import Jira
from .models import UserJiraProfile
import logging

logger = logging.getLogger(__name__)

class JiraAuthenticationBackend(BaseBackend):
    """
    Authenticate users against Jira API
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user against Jira
        """
        if not username or not password:
            return None
            
        try:
            # Try to authenticate with Jira
            jira = Jira(
                url=settings.JIRA_URL,
                username=username,
                password=password,  # User's actual password or API token
                cloud=True
            )
            
            # Test the connection by getting user info
            user_info = jira.myself()
            
            if user_info:
                # Authentication successful, get or create Django user
                django_user = self.get_or_create_user(user_info, username)
                # Create or update JIRA profile
                self.update_jira_profile(django_user, username)
                return django_user
                
        except Exception as e:
            logger.warning(f"Jira authentication failed for {username}: {e}")
            return None
        
        return None
    
    def get_or_create_user(self, jira_user_info, username):
        """
        Get or create Django user based on Jira user info
        """
        try:
            # Try to get existing user
            user = User.objects.get(username=username)
            
            # Update user info from Jira
            user.email = jira_user_info.get('emailAddress', '')
            user.first_name = jira_user_info.get('displayName', '').split(' ')[0]
            user.last_name = ' '.join(jira_user_info.get('displayName', '').split(' ')[1:])
            user.is_active = jira_user_info.get('active', True)
            user.save()
            
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=jira_user_info.get('emailAddress', ''),
                first_name=jira_user_info.get('displayName', '').split(' ')[0],
                last_name=' '.join(jira_user_info.get('displayName', '').split(' ')[1:]),
                is_active=jira_user_info.get('active', True)
            )
            
            logger.info(f"Created new user from Jira: {username}")
        
        return user

    def update_jira_profile(self, user, jira_username):
        """Create or update user's JIRA profile"""
        try:
            profile, created = UserJiraProfile.objects.get_or_create(
                user=user,
                defaults={
                    'jira_username': jira_username,
                    'jira_server': settings.JIRA_URL,
                }
            )
            if not created:
                # Update existing profile
                profile.jira_username = jira_username
                profile.jira_server = settings.JIRA_URL
                profile.save()

            logger.info(f"Updated JIRA profile for user: {user.username}")
        except Exception as e:
            logger.warning(f"Failed to update JIRA profile for {user.username}: {e}")

    def get_user(self, user_id):
        """
        Get user by ID (required by Django)
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None