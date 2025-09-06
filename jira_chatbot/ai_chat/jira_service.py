from jira import JIRA
from atlassian import Confluence
from django.conf import settings
from .models import JiraProject, JiraUser, JiraTicket, ConfluencePage
import logging

logger = logging.getLogger(__name__)

class JiraService:
    def __init__(self):
        self.jira = None
        self.confluence = None
        self.jira_available = False
        self.confluence_available = False

        # Try to initialize JIRA connection
        try:
            self.jira = JIRA(
                server=settings.JIRA_SERVER,
                basic_auth=(settings.JIRA_USERNAME, settings.JIRA_API_TOKEN)
            )
            self.jira_available = True
            logger.info("JIRA connection established successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to JIRA: {str(e)}")
            self.jira_available = False

        # Try to initialize Confluence connection
        try:
            self.confluence = Confluence(
                url=settings.CONFLUENCE_SERVER,
                username=settings.CONFLUENCE_USERNAME,
                password=settings.CONFLUENCE_API_TOKEN
            )
            self.confluence_available = True
            logger.info("Confluence connection established successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to Confluence: {str(e)}")
            self.confluence_available = False
    
    def sync_projects(self):
        """Sync Jira projects to database"""
        if not self.jira_available:
            logger.warning("JIRA not available, cannot sync projects")
            return

        try:
            projects = self.jira.projects()
            for project in projects:
                JiraProject.objects.update_or_create(
                    project_key=project.key,
                    defaults={
                        'project_name': project.name,
                        'project_id': project.id,
                        'lead_email': getattr(project.lead, 'emailAddress', ''),
                    }
                )
        except Exception as e:
            logger.error(f"Failed to sync projects: {str(e)}")
    
    def create_ticket(self, project_key, summary, description, issue_type='Task', priority='Medium', assignee=None):
        """Create a new Jira ticket"""
        if not self.jira_available:
            raise Exception("JIRA is not available. Cannot create tickets.")

        try:
            issue_dict = {
                'project': {'key': project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type},
                'priority': {'name': priority}
            }

            # Add assignee if provided
            if assignee:
                # Check if assignee looks like an account ID (starts with alphanumeric, ~24 chars)
                if len(assignee) > 20 and assignee.replace('-', '').replace('_', '').isalnum():
                    # This looks like an account ID, use it directly
                    issue_dict['assignee'] = {'accountId': assignee}
                    logger.info(f"Assigning ticket to user with account ID: {assignee}")
                else:
                    # This looks like an email, try email format
                    issue_dict['assignee'] = {'emailAddress': assignee}
                    logger.info(f"Assigning ticket using email: {assignee}")

            new_issue = self.jira.create_issue(fields=issue_dict)

            # Save to database
            project, created = JiraProject.objects.get_or_create(
                project_key=project_key,
                defaults={'project_name': project_key, 'project_id': project_key}
            )
            ticket = JiraTicket.objects.create(
                ticket_key=new_issue.key,
                project=project,
                summary=summary,
                description=description,
                issue_type=issue_type,
                priority=priority,
                jira_id=new_issue.id,
                created_by_chat=True
            )

            return ticket
        except Exception as e:
            logger.error(f"Failed to create ticket: {str(e)}")
            raise
    
    def search_tickets(self, query):
        """Search for tickets"""
        if not self.jira_available:
            logger.warning("JIRA not available, cannot search tickets")
            return []

        try:
            # Handle different search scenarios
            if query == "*" or not query.strip():
                # Search all tickets in SUP and KAN projects
                jql = 'project in (SUP, KAN) ORDER BY updated DESC'
            else:
                # Search in summary, description, and comments
                jql = f'(summary ~ "{query}" OR description ~ "{query}" OR comment ~ "{query}") AND project in (SUP, KAN) ORDER BY updated DESC'

            issues = self.jira.search_issues(jql, maxResults=10)

            results = []
            for issue in issues:
                results.append({
                    'key': issue.key,
                    'summary': issue.fields.summary,
                    'description': issue.fields.description or '',
                    'status': issue.fields.status.name,
                    'priority': issue.fields.priority.name if issue.fields.priority else 'Medium'
                })

            return results
        except Exception as e:
            logger.error(f"Failed to search tickets: {str(e)}")
            return []
    
    def search_confluence(self, query):
        """Search Confluence pages"""
        if not self.confluence_available:
            logger.warning("Confluence not available, cannot search pages")
            return []

        try:
            # Handle different query types
            if query == "*" or not query.strip():
                # Get all pages using a broad search
                results = self.confluence.cql('type=page')
            else:
                # Search for specific content
                results = self.confluence.cql(f'text ~ "{query}"')

            pages = []
            for result in results.get('results', []):
                pages.append({
                    'title': result['title'],
                    'content': result.get('excerpt', ''),
                    'url': f"{settings.CONFLUENCE_SERVER}{result['url']}"
                })

            return pages
        except Exception as e:
            logger.error(f"Failed to search Confluence: {str(e)}")
            return []

    def create_confluence_page(self, space_key, title, content, parent_id=None):
        """Create a new Confluence page"""
        if not self.confluence_available:
            raise Exception("Confluence is not available. Cannot create pages.")

        try:
            # Use the simpler create_page method from atlassian-python-api
            new_page = self.confluence.create_page(
                space=space_key,
                title=title,
                body=content,
                parent_id=parent_id,
                type='page',
                representation='storage'
            )

            # Save to database
            from django.utils import timezone
            confluence_page = ConfluencePage.objects.create(
                page_id=new_page['id'],
                title=title,
                content=content,
                space_key=space_key,
                last_updated=timezone.now()
            )

            return confluence_page
        except Exception as e:
            logger.error(f"Failed to create Confluence page: {str(e)}")
            raise

    def get_confluence_spaces(self):
        """Get available Confluence spaces"""
        if not self.confluence_available:
            return []

        try:
            spaces = self.confluence.get_all_spaces(start=0, limit=50)
            return [{'key': space['key'], 'name': space['name']} for space in spaces['results']]
        except Exception as e:
            logger.error(f"Failed to get Confluence spaces: {str(e)}")
            return []

    def update_ticket_status(self, ticket_key, new_status):
        """Update ticket status"""
        if not self.jira_available:
            raise Exception("JIRA is not available. Cannot update tickets.")

        try:
            issue = self.jira.issue(ticket_key)
            transitions = self.jira.transitions(issue)

            # Find the transition that leads to the desired status
            target_transition = None
            for transition in transitions:
                if transition['to']['name'].lower() == new_status.lower():
                    target_transition = transition
                    break

            if not target_transition:
                available_statuses = [t['to']['name'] for t in transitions]
                raise Exception(f"Cannot transition to '{new_status}'. Available transitions: {', '.join(available_statuses)}")

            # Perform the transition
            self.jira.transition_issue(issue, target_transition['id'])

            # Refresh the issue to get updated status
            issue = self.jira.issue(ticket_key)
            return {
                'key': issue.key,
                'summary': issue.fields.summary,
                'old_status': issue.fields.status.name,
                'new_status': new_status,
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to update ticket status: {str(e)}")
            raise

    def resolve_ticket(self, ticket_key, resolution_comment="", assignee=None):
        """Resolve a ticket"""
        if not self.jira_available:
            raise Exception("JIRA is not available. Cannot resolve tickets.")

        try:
            issue = self.jira.issue(ticket_key)

            # Assign ticket if assignee provided
            if assignee:
                try:
                    # Check if assignee looks like an account ID
                    if len(assignee) > 20 and assignee.replace('-', '').replace('_', '').isalnum():
                        # This looks like an account ID, use it directly
                        issue.update(assignee={'accountId': assignee})
                        logger.info(f"Assigned ticket {ticket_key} to user with account ID: {assignee}")
                    else:
                        # This looks like an email, try email format
                        issue.update(assignee={'emailAddress': assignee})
                        logger.info(f"Assigned ticket {ticket_key} using email: {assignee}")
                except Exception as e:
                    logger.warning(f"Could not assign ticket {ticket_key} to {assignee}: {str(e)}")

            transitions = self.jira.transitions(issue)

            # Look for resolution transitions (common names)
            resolution_transitions = []
            for transition in transitions:
                to_status = transition['to']['name'].lower()
                if any(word in to_status for word in ['done', 'resolved', 'closed', 'complete', 'finished', 'klart']):
                    resolution_transitions.append(transition)

            if not resolution_transitions:
                available_statuses = [t['to']['name'] for t in transitions]
                raise Exception(f"No resolution transition found. Available transitions: {', '.join(available_statuses)}")

            # Use the first resolution transition found
            resolution_transition = resolution_transitions[0]

            # Add comment if provided
            if resolution_comment:
                self.jira.add_comment(issue, resolution_comment)

            # Perform the transition
            self.jira.transition_issue(issue, resolution_transition['id'])

            # Refresh the issue to get updated status
            issue = self.jira.issue(ticket_key)
            return {
                'key': issue.key,
                'summary': issue.fields.summary,
                'status': issue.fields.status.name,
                'resolution_comment': resolution_comment,
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to resolve ticket: {str(e)}")
            raise

    def add_comment_to_ticket(self, ticket_key, comment):
        """Add a comment to a ticket"""
        if not self.jira_available:
            raise Exception("JIRA is not available. Cannot add comments.")

        try:
            issue = self.jira.issue(ticket_key)
            self.jira.add_comment(issue, comment)
            return {
                'key': issue.key,
                'summary': issue.fields.summary,
                'comment': comment,
                'success': True
            }
        except Exception as e:
            logger.error(f"Failed to add comment: {str(e)}")
            raise

    def get_ticket_transitions(self, ticket_key):
        """Get available transitions for a ticket"""
        if not self.jira_available:
            raise Exception("JIRA is not available. Cannot get transitions.")

        try:
            issue = self.jira.issue(ticket_key)
            transitions = self.jira.transitions(issue)

            return {
                'key': issue.key,
                'current_status': issue.fields.status.name,
                'transitions': [
                    {
                        'id': t['id'],
                        'name': t['name'],
                        'to_status': t['to']['name']
                    } for t in transitions
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get transitions: {str(e)}")
            raise