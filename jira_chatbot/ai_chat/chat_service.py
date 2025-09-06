from .ollama_api import generate_response
from .jira_service import JiraService
from .models import ChatSession, ChatMessage
import json
import re

class ChatService:
    def __init__(self, session_id, user=None, auto_assign=False):
        self.session_id = session_id
        self.user = user
        self.auto_assign = auto_assign
        self.jira_service = JiraService()
        self.session = self._get_or_create_session()
    
    def _get_or_create_session(self):
        session, created = ChatSession.objects.get_or_create(
            session_id=self.session_id,
            defaults={'user': self.user}
        )

        # Update user if session exists but user wasn't set
        if not session.user and self.user:
            session.user = self.user
            session.save()

        return session
    
    def process_message(self, user_message):
        """Process user message and generate response"""
        # Get conversation context
        context = self._get_conversation_context()

        # Detect intent
        intent = self._detect_intent(user_message)

        # Handle different intents
        if intent == 'bulk_close_tickets':
            response = self._handle_bulk_close_tickets(user_message)
        elif intent == 'resolve_ticket':
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
        elif intent == 'list_confluence_pages':
            response = self._handle_list_confluence_pages(user_message)
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

        # Generate title for new sessions
        if not self.session.title:
            self.session.generate_title()

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

        # Check for bulk operations first (most specific)
        if any(word in message_lower for word in ['close all', 'resolve all', 'close them', 'resolve them']) or (any(word in message_lower for word in ['close', 'resolve']) and any(word in message_lower for word in ['all', 'related', 'issues', 'tickets'])):
            return 'bulk_close_tickets'
        # Check for ticket management requests (specific tickets)
        elif any(word in message_lower for word in ['resolve', 'close', 'complete', 'finish']) and re.search(r'\b(sup|kan)-\d+\b', message_lower):
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
        # Check for listing confluence pages
        elif any(phrase in message_lower for phrase in ['what confluence pages', 'list confluence', 'show confluence', 'available confluence', 'confluence pages available']):
            return 'list_confluence_pages'
        # Check for confluence search specifically
        elif any(word in message_lower for word in ['find', 'search']) and any(word in message_lower for word in ['confluence', 'page', 'documentation']):
            return 'search_confluence'
        # Check for create ticket intent
        elif any(word in message_lower for word in ['create', 'new']) and any(word in message_lower for word in ['ticket', 'issue']):
            return 'create_ticket'
        # Check for search ticket intent
        elif any(word in message_lower for word in ['search', 'find']) and any(word in message_lower for word in ['ticket', 'issue']):
            return 'search_tickets'
        # Check for general search/help (should search both tickets and confluence)
        elif any(word in message_lower for word in ['search', 'find']):
            return 'search_knowledge'
        elif any(word in message_lower for word in ['help', 'how', 'solution', 'problem']):
            return 'search_knowledge'
        else:
            return 'general_chat'
    
    def _handle_ticket_creation(self, message):
        """Handle ticket creation requests"""
        # Check if JIRA is available
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot create tickets at the moment, but I can still help you with other questions!"

        # Get conversation context for better ticket creation
        conversation_context = self._get_conversation_context()

        # Extract ticket details using AI with conversation context
        prompt = f"""
        Based on this conversation and the user's request to create a ticket, extract relevant ticket information.

        Conversation context:
        {conversation_context}

        Current user message: "{message}"

        Analyze the conversation to understand the specific technical issue or problem the user is experiencing. Create a meaningful support ticket with:

        1. A specific, descriptive title that clearly identifies the problem
        2. A detailed description that includes:
           - The specific issue or error
           - Any relevant technical details mentioned (model numbers, error messages, etc.)
           - Context from the conversation
           - Any troubleshooting steps already discussed

        Return ONLY valid JSON without any extra text, comments, or markdown formatting:
        {{
            "summary": "Write a specific title here based on the actual technical issue discussed",
            "description": "Write a comprehensive description here including all relevant details from the conversation",
            "project_key": "SUP",
            "priority": "Choose High/Medium/Low based on urgency and impact of the issue",
            "issue_type": "Task"
        }}

        Examples of good ticket summaries:
        - "ZD421 Zebra printer producing blurry print output"
        - "External monitor not displaying via HDMI connection"
        - "Network shared drive access denied error"
        - "Software installation fails with error code 1603"

        IMPORTANT:
        - Do NOT use placeholder text like "brief title" or "detailed description"
        - Do NOT use generic titles like "user issue" or "technical problem"
        - DO create specific titles based on the actual problem discussed
        - DO include specific technical details mentioned in the conversation

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

            # Debug logging
            print(f"DEBUG: AI Response: {ai_response[:500]}")
            print(f"DEBUG: Parsed JSON: {json_str}")

            ticket_data = json.loads(json_str)
            print(f"DEBUG: Ticket data: {ticket_data}")

            # Create ticket
            assignee = None
            if self.auto_assign and self.user and self.user.is_authenticated:
                # Get user's JIRA info from their profile
                try:
                    from jiraAuth.models import UserJiraProfile
                    profile = UserJiraProfile.objects.get(user=self.user)
                    # Prefer account ID, fallback to username/email
                    assignee = profile.jira_account_id or profile.jira_username
                except:
                    assignee = self.user.email  # Fallback to email

            print(f"DEBUG: Creating ticket with data: {ticket_data}")
            print(f"DEBUG: Assignee: {assignee}")

            ticket = self.jira_service.create_ticket(
                project_key=ticket_data.get('project_key', 'SUP'),
                summary=ticket_data['summary'],
                description=ticket_data['description'],
                issue_type=ticket_data.get('issue_type', 'Task'),
                priority=ticket_data.get('priority', 'Medium'),
                assignee=assignee
            )

            print(f"DEBUG: Ticket created successfully: {ticket.ticket_key}")

            assignment_msg = f"\nAssigned to: {assignee}" if assignee else "\nAssigned to: Unassigned"
            return f"**✅ Ticket Created Successfully**\n\n**{ticket.ticket_key}**: {ticket.summary}\n\nStatus: To Do | Priority: {ticket_data.get('priority', 'Medium')}{assignment_msg}\n\nYour ticket has been created and is ready for processing."

        except json.JSONDecodeError as e:
            return f"Sorry, I couldn't parse the AI response. AI said: '{ai_response[:200]}...'. Error: {str(e)}"
        except Exception as e:
            return f"Sorry, I couldn't create the ticket. JIRA might be unavailable or there was an error: {str(e)}"

    def _handle_bulk_close_tickets(self, message):
        """Handle bulk closing of tickets based on search criteria"""
        if not self.jira_service.jira_available:
            return "Sorry, JIRA is currently not available. I cannot close tickets at the moment."

        # Extract search terms from the message more intelligently
        search_terms = self._extract_search_terms_from_bulk_message(message)

        if not search_terms:
            return "I couldn't determine what type of tickets to close. Please specify what tickets you want to close (e.g., 'close all Windows login tickets' or 'close all iOS WiFi issues')."

        try:
            # Search for tickets matching the criteria
            tickets = self.jira_service.search_tickets(search_terms)

            if not tickets:
                return f"No tickets found matching '{search_terms}' to close."

            closed_tickets = []
            failed_tickets = []

            # Get assignee if auto-assign is enabled
            assignee = None
            if self.auto_assign and self.user and self.user.is_authenticated:
                try:
                    from jiraAuth.models import UserJiraProfile
                    profile = UserJiraProfile.objects.get(user=self.user)
                    # Prefer account ID, fallback to username/email
                    assignee = profile.jira_account_id or profile.jira_username
                except:
                    assignee = self.user.email  # Fallback to email

            # Close each ticket
            for ticket in tickets:
                try:
                    result = self.jira_service.resolve_ticket(
                        ticket['key'],
                        f"Bulk closure: Issue resolved - {search_terms} related matter addressed",
                        assignee=assignee
                    )
                    closed_tickets.append(ticket['key'])
                except Exception as e:
                    failed_tickets.append(f"{ticket['key']} (Error: {str(e)})")

            # Build response
            response = f"✅ **Bulk ticket closure completed!**\n\n"

            if closed_tickets:
                response += f"**Successfully closed {len(closed_tickets)} tickets:**\n"
                for ticket_key in closed_tickets:
                    response += f"- {ticket_key}\n"
                response += f"\n**Resolution comment**: Bulk closure: Issue resolved - {search_terms} related matter addressed\n"

            if failed_tickets:
                response += f"\n**Failed to close {len(failed_tickets)} tickets:**\n"
                for failure in failed_tickets:
                    response += f"- {failure}\n"

            return response

        except Exception as e:
            return f"Sorry, I couldn't perform the bulk closure. Error: {str(e)}"

    def _extract_search_terms_from_bulk_message(self, message):
        """Extract search terms from bulk operation messages"""
        import re

        message_lower = message.lower()

        # Remove common bulk operation words
        noise_words = [
            'close', 'resolve', 'all', 'tickets', 'issues', 'them', 'please', 'now',
            'stop', 'ask', 'confirm', 'regarding', 'related', 'about', 'with', 'for',
            'can', 'you', 'the', 'and', 'or', 'to', 'from', 'in', 'on', 'at', 'by'
        ]

        # Split message into words
        words = re.findall(r'\b\w+\b', message_lower)

        # Remove noise words
        meaningful_words = [word for word in words if word not in noise_words and len(word) > 2]

        # Look for common patterns
        search_terms = []

        # Pattern 1: "close all [topic] tickets/issues"
        patterns = [
            r'(?:close|resolve)\s+all\s+([^t]+?)(?:\s+(?:tickets|issues))',
            r'(?:tickets|issues)\s+(?:regarding|about|related\s+to)\s+(.+?)(?:\s|$)',
            r'all\s+([^t]+?)(?:\s+(?:tickets|issues|related))',
        ]

        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                terms = match.group(1).strip()
                if terms:
                    search_terms.extend(terms.split())

        # If no patterns matched, use meaningful words
        if not search_terms:
            search_terms = meaningful_words[:3]  # Take first 3 meaningful words

        # Clean and join search terms
        final_terms = ' '.join(search_terms).strip()

        # Handle specific common cases
        if any(word in message_lower for word in ['windows', 'login', 'sign']):
            if 'windows' in message_lower and any(word in message_lower for word in ['login', 'sign']):
                final_terms = 'windows login'
        elif any(word in message_lower for word in ['ios', 'wifi', 'wireless']):
            if 'ios' in message_lower and any(word in message_lower for word in ['wifi', 'wireless']):
                final_terms = 'ios wifi'
        elif any(word in message_lower for word in ['microsoft', 'office', '365']):
            final_terms = 'microsoft'
        elif any(word in message_lower for word in ['printer', 'printing']):
            final_terms = 'printer'
        elif any(word in message_lower for word in ['network', 'connectivity']):
            final_terms = 'network'

        return final_terms

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
            response = f"**🎫 Ticket Details: {ticket_key}**\n\n"
            response += f"**{issue.fields.summary}**\n\n"
            response += f"Status: {issue.fields.status.name} | Priority: {issue.fields.priority.name if issue.fields.priority else 'Not set'}\n"
            response += f"Assignee: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}\n"
            response += f"Created: {issue.fields.created[:10]}\n\n"

            if issue.fields.description:
                response += f"**Description:**\n{issue.fields.description}\n\n"
            else:
                response += "**Description:** No description provided\n\n"

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
            # Get assignee if auto-assign is enabled
            assignee = None
            if self.auto_assign and self.user and self.user.is_authenticated:
                try:
                    from jiraAuth.models import UserJiraProfile
                    profile = UserJiraProfile.objects.get(user=self.user)
                    # Prefer account ID, fallback to username/email
                    assignee = profile.jira_account_id or profile.jira_username
                except:
                    assignee = self.user.email  # Fallback to email

            result = self.jira_service.resolve_ticket(ticket_key, resolution_comment, assignee=assignee)
            response = f"✅ **Ticket {ticket_key} has been resolved!**\n\n"
            response += f"**Summary**: {result['summary']}\n"
            response += f"**New Status**: {result['status']}\n"
            if resolution_comment:
                response += f"**Resolution Comment**: {resolution_comment}\n"
            if assignee:
                response += f"**Assigned to**: {assignee}\n"

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
            response = f"**🎫 Ticket Search Results ({len(tickets)} found)**\n\n"
            for i, ticket in enumerate(tickets[:5], 1):  # Limit to 5 results
                response += f"{i}. **{ticket['key']}**: {ticket['summary']}\n"
                response += f"   Status: {ticket['status']} | Priority: {ticket['priority']}\n"
                if ticket['description']:
                    response += f"   {ticket['description'][:100]}...\n"
                response += "\n"
        else:
            response = "**🎫 No tickets found**\n\nNo tickets found matching your search criteria."

        return response
    
    def _handle_knowledge_search(self, message):
        """Search for solutions in tickets and Confluence"""
        # Extract meaningful search terms
        search_terms = re.sub(r'(help|how|solution|problem|find|search)', '', message, flags=re.IGNORECASE).strip()

        # If no meaningful terms, use the full message
        if not search_terms or len(search_terms) < 3:
            search_terms = message

        # Search both tickets and Confluence
        tickets = self.jira_service.search_tickets(search_terms)
        confluence_pages = self.jira_service.search_confluence(search_terms)

        response = ""

        # Build comprehensive response
        if tickets or confluence_pages:
            response += f"**Search Results for '{search_terms}'**\n\n"

            if confluence_pages:
                response += "**📚 From Confluence Documentation:**\n\n"
                for i, page in enumerate(confluence_pages[:3], 1):
                    response += f"{i}. **{page['title']}**\n"
                    response += f"   {page['content'][:150]}...\n"
                    response += f"   [View full page]({page['url']})\n\n"

            if tickets:
                response += "**🎫 From Related Tickets:**\n\n"
                for i, ticket in enumerate(tickets[:3], 1):
                    response += f"{i}. **{ticket['key']}**: {ticket['summary']}\n"
                    response += f"   Status: {ticket['status']} | Priority: {ticket['priority']}\n"
                    if ticket['description']:
                        response += f"   {ticket['description'][:100]}...\n"
                    response += "\n"

            # Add AI-generated advice based on found content
            context_info = ""
            if confluence_pages:
                context_info += "Documentation available: " + ", ".join([p['title'] for p in confluence_pages[:3]])
            if tickets:
                context_info += " Related tickets: " + ", ".join([t['key'] for t in tickets[:3]])

            prompt = f"""
            User is asking: {message}

            Available resources: {context_info}

            Based on the documentation and tickets found, provide 2-3 practical next steps or recommendations.
            Keep it concise and actionable.
            """

            ai_advice = ""
            for chunk in generate_response(prompt):
                ai_advice += chunk

            response += f"**💡 Recommended Next Steps:**\n{ai_advice}"

        else:
            # Check service availability
            if not self.jira_service.jira_available and not self.jira_service.confluence_available:
                response = "JIRA and Confluence are currently not available, so I cannot search for specific information. "
            elif not self.jira_service.jira_available:
                response = "JIRA is currently not available, so I cannot search tickets. "
            elif not self.jira_service.confluence_available:
                response = "Confluence is currently not available, so I cannot search documentation. "
            else:
                response = f"No specific information found for '{search_terms}' in JIRA or Confluence. "

            # Provide general AI assistance
            prompt = f"""
            User is asking for help with: {message}

            No specific documentation or tickets were found for this topic.
            Provide helpful general advice and suggest they might want to:
            1. Try different search terms
            2. Create a ticket if this is a new issue
            3. Contact support if needed

            Keep the response helpful and professional.
            """

            ai_advice = ""
            for chunk in generate_response(prompt):
                ai_advice += chunk

            response += ai_advice

        return response
    
    def _handle_list_confluence_pages(self, message):
        """Handle requests to list available Confluence pages"""
        if not self.jira_service.confluence_available:
            return "Sorry, Confluence is currently not available. I cannot access documentation at the moment."

        try:
            # Get all available pages by searching with a broad query
            all_pages = self.jira_service.search_confluence("*")

            if all_pages:
                response = f"**📚 Available Confluence Pages ({len(all_pages)} total)**\n\n"
                for i, page in enumerate(all_pages[:10], 1):  # Limit to 10 results
                    response += f"{i}. **{page['title']}**\n"
                    if page['content']:
                        response += f"   Preview: {page['content'][:100]}...\n"
                    response += f"   [View page]({page['url']})\n\n"

                if len(all_pages) > 10:
                    response += f"... and {len(all_pages) - 10} more pages. Use search to find specific topics.\n"
            else:
                response = "No Confluence pages found. You may need to create some documentation first."

        except Exception as e:
            response = f"Error accessing Confluence pages: {str(e)}"

        return response

    def _handle_confluence_search(self, message):
        """Handle Confluence-specific search requests"""
        if not self.jira_service.confluence_available:
            return "Sorry, Confluence is currently not available. I cannot search documentation at the moment."

        # Extract search terms
        search_terms = re.sub(r'(find|search|confluence|page|documentation)', '', message, flags=re.IGNORECASE).strip()

        # If no specific terms, show available pages
        if not search_terms or len(search_terms) < 2:
            return self._handle_list_confluence_pages(message)

        confluence_pages = self.jira_service.search_confluence(search_terms)

        if confluence_pages:
            response = f"**📚 Confluence Search Results ({len(confluence_pages)} found)**\n\n"
            response += f"Search term: `{search_terms}`\n\n"
            for i, page in enumerate(confluence_pages[:5], 1):  # Limit to 5 results
                response += f"{i}. **{page['title']}**\n"
                response += f"   {page['content'][:200]}...\n"
                response += f"   [View page]({page['url']})\n\n"
        else:
            response = f"**📚 No Confluence pages found**\n\n"
            response += f"No pages found matching `{search_terms}`. Try different keywords or check available pages."

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