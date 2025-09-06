from django.db import models
from django.contrib.auth.models import User

class UserJiraProfile(models.Model):
    """Store user-specific JIRA information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    jira_username = models.EmailField()
    jira_server = models.URLField()
    last_login_jira = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.jira_username}"
