from .ollama_api import generate_response
from .jira_service import JiraService
from .models import ChatSession, ChatMessage
import json
import re

class ChatService:
    def __init__(self, session_id, user=None):
        self.session_id = session_id
        self.user = user
        self.jira_service = JiraService()
        self.session = self._get_or_create_session()
    
    def _get_or_create_session(self):
        session, created = ChatSession.objects.get_or_create(
            session_id=self.session_id
        )
        return session
    
    def process_message(self, user_message):
        """Process user message and generate response"""
        # Get conversation context
        context = self._get_conversation_context()

        # Detect intent
        intent = self._detect_intent(user_message)

        # Handle different intents
        if intent == 'resolve_ticket':
            response = self._handle_resolve_ticket(user_message)
        elif intent == 'update_ticket_status':
            response = self._handle_update_ticket_status(user_message)
        elif intent == 'add_ticket_comment':
            response = self._handle_add_ticket_comment(user_message)
        elif intent == 'get_ticket_details':
            response = self._handle_get_ticket_details(user_message)
        elif intent == 'get_ticket_solution':
            response = self._handle_get_ticket_solution(user_message)
        elif intent == 'create_ticket':
            response = self._handle_ticket_creation(user_message)
        elif intent == 'create_confluence_page':
            response = self._handle_confluence_page_creation(user_message)
        elif intent == 'search_tickets':
            response = self._handle_ticket_search(user_message)
        elif intent == 'search_confluence':
            response = self._handle_confluence_search(user_message)
        elif intent == 'search_knowledge':
            response = self._handle_knowledge_search(user_message)
        else:
            response = self._handle_general_chat(user_message, context)

        # Save conversation
        ChatMessage.objects.create(
            session=self.session,
            user_message=user_message,
            bot_response=response,
            intent_detected=intent
        )

        return response

    def _get_conversation_context(self):
        """Get recent conversation history for context"""
        recent_messages = ChatMessage.objects.filter(
            session=self.session
        ).order_by('-created_at')[:5]  # Last 5 messages

        context = ""
        for msg in reversed(recent_messages):
            context += f"User: {msg.user_message}\n"
            context += f"Bot: {msg.bot_response[:100]}...\n\n"

        return context
    
    def _detect_intent(self, message):
        """Enhanced intent detection"""
        message_lower = message.lower()

        # Check for ticket management requests first (most specific)
        if any(word in message_lower for word in ['resolve', 'close', 'complete', 'finish']) and re.search(r'\b(sup|kan)-\d+\b', message_lower):
            return 'resolve_ticket'
        elif any(word in message_lower for word in ['update', 'change', 'set']) and any(word in message_lower for word in ['status', 'state']) and re.search(r'\b(sup|kan)-\d+\b', message_lower):
            return 'update_ticket_status'
        elif any(word in message_lower for word in ['comment', 'add comment', 'note']) and re.search(r'\b(sup|kan)-\d+\b', message_lower):
            return 'add_ticket_comment'
        # Check for solution requests
        elif any(word in message_lower for word in ['solution', 'solve', 'fix']) and re.search(r'\b(sup|kan)-\d+\b', message_lower):
            return 'get_ticket_solution'
        # Check for specific ticket requests (SUP-1, etc.)
        elif re.search(r'\b(sup|kan)-\d+\b', message_lower):
            return 'get_ticket_details'
        # Check for create confluence page intent
        elif any(word in message_lower for word in ['create', 'new', 'make']) and any(word in message_lower for word in ['confluence', 'page', 'documentation', 'guide', 'troubleshoot']):
            return 'create_confluence_page'
        # Check for confluence search specifically
        elif any(word in message_lower for word in ['find', 'search']) and any(word in message_lower for word in ['confluence', 'page', 'documentation']):
            return 'search_confluence'
        # Check for create ticket intent
        elif any(word in message_lower for word in ['create', 'new']) and any(word in message_lower for word in ['ticket', 'issue']):
            return 'create_ticket'
        # Check for search ticket intent
        elif any(word in message_lower for word in ['search', 'find']) and any(word in message_lower for word in ['ticket', 'issue']):
            return 'search_tickets'
        # Check for general search/help
        elif any(word in message_lower for word in ['search', 'find']):
            return 'search_tickets'
        elif any(word in message_lower for word in ['help', 'how', 'solution', 'problem']):
            return 'search_knowledge'
        else:
            return 'general_chat'
    
    def _handle_ticket_creation(self, message):
        """Handle ticket creation requests"""
        # Check if JIRA is available
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot create tickets at the moment, but I can still help you with other questions!"

        # Extract ticket details using AI
        prompt = f"""
        Extract ticket information from this message: "{message}"

        Return ONLY valid JSON without any extra text, comments, or markdown formatting:
        {{
            "summary": "brief title",
            "description": "detailed description",
            "project_key": "SUP",
            "priority": "Medium",
            "issue_type": "Task"
        }}

        Do not include any text before or after the JSON. Do not use comments in the JSON.
        """

        # Get AI response and parse
        ai_response = ""
        try:
            for chunk in generate_response(prompt):
                ai_response += chunk
        except Exception as e:
            return f"Sorry, I couldn't generate a response from the AI: {str(e)}"

        if not ai_response.strip():
            return "Sorry, I couldn't get a response from the AI to process your ticket request."

        try:
            # Extract JSON from AI response (it might have extra text, markdown, or comments)
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                return f"Sorry, I couldn't find valid JSON in the AI response: '{ai_response[:200]}...'"

            json_str = ai_response[json_start:json_end]

            # Remove comments from JSON (lines starting with //)
            lines = json_str.split('\n')
            clean_lines = []
            for line in lines:
                # Remove inline comments
                if '//' in line:
                    line = line.split('//')[0].rstrip()
                clean_lines.append(line)

            json_str = '\n'.join(clean_lines)
            ticket_data = json.loads(json_str)

            # Create ticket
            ticket = self.jira_service.create_ticket(
                project_key=ticket_data.get('project_key', 'SUP'),
                summary=ticket_data['summary'],
                description=ticket_data['description'],
                issue_type=ticket_data.get('issue_type', 'Task'),
                priority=ticket_data.get('priority', 'Medium')
            )

            return f"Created ticket {ticket.ticket_key}: {ticket.summary}"

        except json.JSONDecodeError as e:
            return f"Sorry, I couldn't parse the AI response. AI said: '{ai_response[:200]}...'. Error: {str(e)}"
        except Exception as e:
            return f"Sorry, I couldn't create the ticket. JIRA might be unavailable or there was an error: {str(e)}"

    def _handle_get_ticket_details(self, message):
        """Handle requests for specific ticket details"""
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot retrieve ticket details at the moment."

        # Extract ticket key from message
        ticket_match = re.search(r'\b(SUP|KAN)-(\d+)\b', message, re.IGNORECASE)
        if not ticket_match:
            return "I couldn't find a valid ticket key in your message. Please specify a ticket like SUP-1 or KAN-2."

        ticket_key = f"{ticket_match.group(1).upper()}-{ticket_match.group(2)}"

        try:
            issue = self.jira_service.jira.issue(ticket_key)
            response = f"**Ticket {ticket_key}**\n\n"
            response += f"**Summary**: {issue.fields.summary}\n"
            response += f"**Status**: {issue.fields.status.name}\n"
            response += f"**Priority**: {issue.fields.priority.name if issue.fields.priority else 'Not set'}\n"
            response += f"**Description**: {issue.fields.description or 'No description provided'}\n"
            response += f"**Assignee**: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}\n"
            response += f"**Created**: {issue.fields.created[:10]}\n"

            return response
        except Exception as e:
            return f"Sorry, I couldn't retrieve details for ticket {ticket_key}. Error: {str(e)}"

    def _handle_get_ticket_solution(self, message):
        """Handle requests for ticket solutions"""
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot provide ticket solutions at the moment."

        # Extract ticket key from message
        ticket_match = re.search(r'\b(SUP|KAN)-(\d+)\b', message, re.IGNORECASE)
        if not ticket_match:
            return "I couldn't find a valid ticket key in your message. Please specify a ticket like SUP-1 or KAN-2."

        ticket_key = f"{ticket_match.group(1).upper()}-{ticket_match.group(2)}"

        try:
            issue = self.jira_service.jira.issue(ticket_key)

            # Create a solution prompt based on the ticket
            prompt = f"""
            Provide a step-by-step solution for this JIRA ticket:

            Ticket: {ticket_key}
            Summary: {issue.fields.summary}
            Description: {issue.fields.description or 'No description provided'}
            Status: {issue.fields.status.name}

            Please provide:
            1. A clear explanation of the problem
            2. Step-by-step troubleshooting instructions
            3. Common causes and solutions
            4. Prevention tips if applicable

            Make the response practical and actionable.
            """

            # Get AI response
            ai_response = ""
            try:
                for chunk in generate_response(prompt):
                    ai_response += chunk
            except Exception as e:
                return f"Sorry, I couldn't generate a solution. Error: {str(e)}"

            response = f"**Solution for {ticket_key}: {issue.fields.summary}**\n\n"
            response += ai_response

            return response
        except Exception as e:
            return f"Sorry, I couldn't provide a solution for ticket {ticket_key}. Error: {str(e)}"

    def _handle_resolve_ticket(self, message):
        """Handle ticket resolution requests"""
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot resolve tickets at the moment."

        # Extract ticket key from message
        ticket_match = re.search(r'\b(SUP|KAN)-(\d+)\b', message, re.IGNORECASE)
        if not ticket_match:
            return "I couldn't find a valid ticket key in your message. Please specify a ticket like SUP-1 or KAN-2."

        ticket_key = f"{ticket_match.group(1).upper()}-{ticket_match.group(2)}"

        # Extract resolution comment if provided
        comment_match = re.search(r'(?:with comment|comment|note):\s*(.+)', message, re.IGNORECASE)
        resolution_comment = comment_match.group(1) if comment_match else "Resolved via chatbot"

        try:
            result = self.jira_service.resolve_ticket(ticket_key, resolution_comment)
            response = f"✅ **Ticket {ticket_key} has been resolved!**\n\n"
            response += f"**Summary**: {result['summary']}\n"
            response += f"**New Status**: {result['status']}\n"
            if resolution_comment:
                response += f"**Resolution Comment**: {resolution_comment}\n"

            return response
        except Exception as e:
            return f"Sorry, I couldn't resolve ticket {ticket_key}. Error: {str(e)}"

    def _handle_update_ticket_status(self, message):
        """Handle ticket status update requests"""
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot update ticket status at the moment."

        # Extract ticket key from message
        ticket_match = re.search(r'\b(SUP|KAN)-(\d+)\b', message, re.IGNORECASE)
        if not ticket_match:
            return "I couldn't find a valid ticket key in your message. Please specify a ticket like SUP-1 or KAN-2."

        ticket_key = f"{ticket_match.group(1).upper()}-{ticket_match.group(2)}"

        # Extract new status from message
        status_keywords = {
            'Pågående': ['progress', 'start', 'working', 'pågående', 'in progress'],
            'Pending': ['pending', 'review', 'waiting'],
            'Done': ['done', 'complete', 'finished'],
            'Closed': ['closed', 'close']
        }

        new_status = None
        for status, keywords in status_keywords.items():
            if any(keyword in message.lower() for keyword in keywords):
                new_status = status
                break

        if not new_status:
            # Get available transitions
            try:
                transitions = self.jira_service.get_ticket_transitions(ticket_key)
                available = [t['to_status'] for t in transitions['transitions']]
                return f"I couldn't determine the new status. Available options for {ticket_key}: {', '.join(available)}"
            except Exception as e:
                return f"Sorry, I couldn't get available statuses for {ticket_key}. Error: {str(e)}"

        try:
            result = self.jira_service.update_ticket_status(ticket_key, new_status)
            response = f"✅ **Ticket {ticket_key} status updated!**\n\n"
            response += f"**Summary**: {result['summary']}\n"
            response += f"**New Status**: {result['new_status']}\n"

            return response
        except Exception as e:
            return f"Sorry, I couldn't update the status for ticket {ticket_key}. Error: {str(e)}"

    def _handle_add_ticket_comment(self, message):
        """Handle adding comments to tickets"""
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot add comments at the moment."

        # Extract ticket key from message
        ticket_match = re.search(r'\b(SUP|KAN)-(\d+)\b', message, re.IGNORECASE)
        if not ticket_match:
            return "I couldn't find a valid ticket key in your message. Please specify a ticket like SUP-1 or KAN-2."

        ticket_key = f"{ticket_match.group(1).upper()}-{ticket_match.group(2)}"

        # Extract comment from message
        comment_match = re.search(r'(?:comment|note)\s+(?:to\s+\w+-\d+)?\s*:\s*(.+)', message, re.IGNORECASE)
        if not comment_match:
            return f"I couldn't find a comment to add. Please use format: 'add comment to {ticket_key}: your comment here'"

        comment = comment_match.group(1)

        try:
            result = self.jira_service.add_comment_to_ticket(ticket_key, comment)
            response = f"✅ **Comment added to {ticket_key}!**\n\n"
            response += f"**Summary**: {result['summary']}\n"
            response += f"**Comment**: {comment}\n"

            return response
        except Exception as e:
            return f"Sorry, I couldn't add a comment to ticket {ticket_key}. Error: {str(e)}"

    def _handle_confluence_page_creation(self, message):
        """Handle Confluence page creation requests"""
        # Check if Confluence is available
        if not self.jira_service.confluence_available:
            return "Sorry, Confluence is currently not available. I cannot create pages at the moment, but I can still help you with other questions!"

        # Extract page details using AI
        prompt = f"""
        Create a troubleshooting guide based on: "{message}"

        Return ONLY valid JSON:
        {{
            "title": "Brief title for the guide",
            "content": "Simple HTML content with basic troubleshooting steps",
            "space_key": "ITSUPPORT"
        }}

        Keep the content simple with basic HTML tags only. Use h2 for headings, p for paragraphs, ul and li for lists.
        Avoid special characters, quotes, and newlines in the content.
        """

        # Get AI response and parse
        ai_response = ""
        try:
            for chunk in generate_response(prompt):
                ai_response += chunk
        except Exception as e:
            return f"Sorry, I couldn't generate a response from the AI: {str(e)}"

        if not ai_response.strip():
            return "Sorry, I couldn't get a response from the AI to process your page creation request."

        try:
            # Extract JSON from AI response (it might have extra text, markdown, or comments)
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                return f"Sorry, I couldn't find valid JSON in the AI response: '{ai_response[:200]}...'"

            json_str = ai_response[json_start:json_end]

            # Clean the JSON string more thoroughly
            import re
            # Remove control characters and normalize whitespace
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            # Remove comments
            json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
            # Normalize whitespace in strings but preserve structure
            json_str = re.sub(r'\s+', ' ', json_str)
            json_str = json_str.replace('{ ', '{').replace(' }', '}').replace('[ ', '[').replace(' ]', ']')
            page_data = json.loads(json_str)

            # Get available spaces to use a default one (prefer IT-support)
            spaces = self.jira_service.get_confluence_spaces()
            default_space = 'ITSUPPORT'  # Default to IT-support space
            for space in spaces:
                if space['key'] == 'ITSUPPORT':
                    default_space = 'ITSUPPORT'
                    break

            # Create Confluence page
            page = self.jira_service.create_confluence_page(
                space_key=page_data.get('space_key', default_space),
                title=page_data['title'],
                content=page_data['content']
            )

            return f"Created Confluence page '{page.title}' successfully! You can view it in your Confluence space."

        except json.JSONDecodeError as e:
            return f"Sorry, I couldn't parse the AI response. AI said: '{ai_response[:200]}...'. Error: {str(e)}"
        except Exception as e:
            return f"Sorry, I couldn't create the Confluence page. Confluence might be unavailable or there was an error: {str(e)}"
    
    def _handle_ticket_search(self, message):
        """Handle ticket search requests"""
        # Check if JIRA is available
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot search tickets at the moment, but I can still help you with other questions!"

        # Extract search terms more intelligently
        search_terms = re.sub(r'\b(search|find|ticket|tickets|issue|issues|can|you|a|the|for|about|regarding|with)\b', '', message, flags=re.IGNORECASE).strip()

        # If no meaningful search terms, try to search all tickets
        if not search_terms or len(search_terms) < 2:
            search_terms = "*"

        tickets = self.jira_service.search_tickets(search_terms)

        if tickets:
            response = "Found tickets:\n\n"
            for ticket in tickets[:5]:  # Limit to 5 results
                response += f"**{ticket['key']}**: {ticket['summary']}\n"
                response += f"Status: {ticket['status']} | Priority: {ticket['priority']}\n"
                if ticket['description']:
                    response += f"Description: {ticket['description'][:100]}...\n"
                response += "\n"
        else:
            response = "No tickets found matching your search."

        return response
    
    def _handle_knowledge_search(self, message):
        """Search for solutions in tickets and Confluence"""
        search_terms = message

        # Search both tickets and Confluence
        tickets = self.jira_service.search_tickets(search_terms)
        confluence_pages = self.jira_service.search_confluence(search_terms)

        context = "Found information:\n\n"
        has_context = False

        if tickets:
            context += "From Jira tickets:\n"
            for ticket in tickets[:3]:
                context += f"- {ticket['key']}: {ticket['summary']}\n"
            has_context = True

        if confluence_pages:
            context += "\nFrom Confluence:\n"
            for page in confluence_pages[:3]:
                context += f"- {page['title']}\n"
            has_context = True

        if not has_context:
            if not self.jira_service.jira_available and not self.jira_service.confluence_available:
                context = "JIRA and Confluence are currently not available, so I cannot search for specific information."
            elif not self.jira_service.jira_available:
                context = "JIRA is currently not available, so I cannot search tickets."
            elif not self.jira_service.confluence_available:
                context = "Confluence is currently not available, so I cannot search documentation."
            else:
                context = "No specific information found in JIRA or Confluence."

        # Generate AI response with context
        prompt = f"""
        User question: {message}

        Available context:
        {context}

        Provide a helpful answer based on the context above. If no specific context is available, provide general helpful advice.
        """

        response = ""
        for chunk in generate_response(prompt):
            response += chunk

        return response
    
    def _handle_confluence_search(self, message):
        """Handle Confluence-specific search requests"""
        if not self.jira_service.confluence_available:
            return "Sorry, Confluence is currently not available. I cannot search documentation at the moment."

        # Extract search terms
        search_terms = re.sub(r'(find|search|confluence|page|documentation)', '', message, flags=re.IGNORECASE).strip()

        confluence_pages = self.jira_service.search_confluence(search_terms)

        if confluence_pages:
            response = "Found Confluence pages:\n\n"
            for page in confluence_pages[:5]:  # Limit to 5 results
                response += f"**{page['title']}**\n"
                response += f"Content: {page['content'][:200]}...\n"
                response += f"URL: {page['url']}\n\n"
        else:
            response = "No Confluence pages found matching your search."

        return response

    def _handle_general_chat(self, message, context=""):
        """Handle general conversation with context"""
        # Check if user is asking about capabilities
        message_lower = message.lower()
        if any(phrase in message_lower for phrase in ['what can you', 'what do you', 'help me with', 'capabilities', 'features']) or message_lower in ['help', 'what can you do']:
            return self._get_capabilities_response()

        prompt = f"""You are a helpful Jira assistant.

        Previous conversation context:
        {context}

        Current user message: {message}

        Respond helpfully, taking into account the conversation history if relevant."""

        response = ""
        for chunk in generate_response(prompt):
            response += chunk

        return response

    def _get_capabilities_response(self):
        """Return a response about bot capabilities"""
        jira_status = "✅ Available" if self.jira_service.jira_available else "❌ Unavailable"
        confluence_status = "✅ Available" if self.jira_service.confluence_available else "❌ Unavailable"

        user_greeting = ""
        if self.user and self.user.is_authenticated:
            name = self.user.first_name or self.user.username
            user_greeting = f"Hello {name}! "

        return f"""{user_greeting}I'm your JIRA and Confluence assistant! Here's what I can help you with:

**🎫 JIRA Ticket Management:**
- Create new tickets: "Create a ticket for..."
- Search tickets: "Find tickets about..."
- View ticket details: "SUP-1" or "Show me KAN-2"
- Get solutions: "Provide solution for SUP-1"
- Update status: "Update SUP-1 status to in progress"
- Add comments: "Add comment to SUP-1: your comment here"
- Resolve tickets: "Resolve SUP-1 with comment: issue fixed"

**📚 Confluence Documentation:**
- Search documentation: "Find confluence page about..."
- Create troubleshooting guides: "Create confluence page for..."

**💬 General Support:**
- Ask questions and get helpful advice
- Get step-by-step troubleshooting instructions

**System Status:**
- JIRA: {jira_status}
- Confluence: {confluence_status}

Just tell me what you need help with, and I'll do my best to assist you!"""