from jira import JIRA
from atlassian import Confluence
from django.conf import settings
from .models import JiraProject, JiraUser, JiraTicket, ConfluencePage
import logging

logger = logging.getLogger(__name__)

class JiraService:
    def __init__(self):
        self.jira = JIRA(
            server=settings.JIRA_SERVER
            basic_auth(settings.JIRA_USERNAME, settings.JIRA_API_TOKEN)
        )