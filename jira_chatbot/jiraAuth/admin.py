from django.contrib import admin
from .models import UserJiraProfile

@admin.register(UserJiraProfile)
class UserJiraProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'jira_username', 'jira_server', 'is_active', 'last_login_jira')
    list_filter = ('is_active', 'jira_server', 'created_at')
    search_fields = ('user__username', 'user__email', 'jira_username')
    readonly_fields = ('created_at', 'last_login_jira')
