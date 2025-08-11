# ai_chat/models.py
from django.db import models
from django.contrib.auth.models import User
import json

class JiraProject(models.Model):
    """Store Jira project information"""
    project_key = models.CharField(max_length=20, unique=True)  # e.g., "PROJ", "BUG"
    project_name = models.CharField(max_length=200)
    project_id = models.CharField(max_length=50)
    lead_email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.project_key} - {self.project_name}"

class JiraUser(models.Model):
    """Store Jira user information"""
    jira_account_id = models.CharField(max_length=100, unique=True)
    email = models.EmailField()
    display_name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.display_name

class ChatSession(models.Model):
    """Enhanced chat session with user context"""
    session_id = models.CharField(max_length=100, unique=True)
    user_email = models.EmailField(blank=True, null=True)  # Who's chatting
    current_project = models.ForeignKey(JiraProject, on_delete=models.SET_NULL, null=True, blank=True)
    conversation_context = models.JSONField(default=dict)  # Store conversation state
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    def set_context(self, key, value):
        """Helper method to set context data"""
        self.conversation_context[key] = value
        self.save()
    
    def get_context(self, key, default=None):
        """Helper method to get context data"""
        return self.conversation_context.get(key, default)

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    user_message = models.TextField()
    bot_response = models.TextField()
    intent_detected = models.CharField(max_length=100, blank=True)  # What the bot understood
    created_at = models.DateTimeField(auto_now_add=True)
    response_type = models.CharField(max_length=50, default='text')

class JiraTicket(models.Model):
    """Enhanced ticket model with all necessary fields"""
    PRIORITY_CHOICES = [
        ('Lowest', 'Lowest'),
        ('Low', 'Low'), 
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Highest', 'Highest'),
    ]
    
    ISSUE_TYPE_CHOICES = [
        ('Task', 'Task'),
        ('Bug', 'Bug'),
        ('Story', 'Story'),
        ('Epic', 'Epic'),
        ('Subtask', 'Subtask'),
    ]
    
    STATUS_CHOICES = [
        ('To Do', 'To Do'),
        ('In Progress', 'In Progress'),
        ('Code Review', 'Code Review'),
        ('Testing', 'Testing'),
        ('Done', 'Done'),
    ]
    
    # Basic ticket info
    ticket_key = models.CharField(max_length=50, unique=True)
    project = models.ForeignKey(JiraProject, on_delete=models.CASCADE)
    summary = models.CharField(max_length=255)
    description = models.TextField()
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPE_CHOICES, default='Task')
    priority = models.CharField(max_length=50, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='To Do')
    
    # People
    assignee = models.ForeignKey(JiraUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    reporter = models.ForeignKey(JiraUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_tickets')
    
    # Metadata
    created_by_chat = models.BooleanField(default=False)
    chat_session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    jira_id = models.CharField(max_length=50, blank=True)  # Actual Jira ticket ID
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.ticket_key}: {self.summary}"

class TicketCreationFlow(models.Model):
    """Track multi-step ticket creation process"""
    FLOW_STEPS = [
        ('started', 'Started'),
        ('got_summary', 'Got Summary'),
        ('got_description', 'Got Description'),
        ('got_project', 'Got Project'),
        ('got_assignee', 'Got Assignee'),
        ('got_priority', 'Got Priority'),
        ('completed', 'Completed'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    current_step = models.CharField(max_length=50, choices=FLOW_STEPS, default='started')
    collected_data = models.JSONField(default=dict)  # Store partial ticket data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ConfluencePage(models.Model):
    page_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    space_key = models.CharField(max_length=50)
    page_type = models.CharField(max_length=50, default='page')
    last_updated = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class TicketSolution(models.Model):
    """Store extracted solutions from resolved tickets"""
    ticket = models.OneToOneField(JiraTicket, on_delete=models.CASCADE)
    solution_text = models.TextField()
    steps_taken = models.JSONField(default=list)
    time_to_resolve = models.DurationField(null=True, blank=True)
    success_rating = models.IntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    tags = models.JSONField(default=list)  # For categorization
    
class KnowledgeBase(models.Model):
    """Extracted knowledge from docs and tickets"""
    title = models.CharField(max_length=255)
    content = models.TextField()
    source_type = models.CharField(max_length=50)  # 'ticket' or 'confluence'
    source_id = models.CharField(max_length=50)
    keywords = models.JSONField(default=list)
    category = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)