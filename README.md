# JIRA AI Integration Chatbot

A comprehensive Django-based chatbot that integrates with JIRA and Confluence to provide intelligent ticket management and documentation assistance.

## Features

### JIRA Ticket Management
- **Create tickets**: Generate JIRA tickets from natural language descriptions
- **Search tickets**: Find tickets using intelligent search queries
- **View ticket details**: Get complete ticket information including status, priority, and description
- **Update ticket status**: Change ticket status with natural language commands
- **Add comments**: Add comments to tickets with simple commands
- **Resolve tickets**: Mark tickets as resolved with optional resolution comments
- **AI-powered solutions**: Get step-by-step troubleshooting guides for specific tickets

### Confluence Documentation
- **Search documentation**: Find relevant Confluence pages
- **Create troubleshooting guides**: Generate comprehensive documentation pages
- **AI-powered content**: Automatically create structured troubleshooting content

### Intelligent Features
- **Context retention**: Remembers conversation history within sessions
- **Intent detection**: Understands user requests and routes them appropriately
- **Multi-language support**: Handles both English and Swedish JIRA workflows
- **Error handling**: Graceful degradation when services are unavailable

## Setup Instructions

### Prerequisites
- Python 3.8+
- Django 5.2+
- JIRA instance with API access
- Confluence instance with API access
- Ollama for local LLM integration

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Kevinolm10/Jira-AI-integration.git
   cd Jira-AI-integration/jira_chatbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and configure:
   ```env
   # JIRA Configuration
   JIRA_SERVER=https://your-company.atlassian.net
   JIRA_USERNAME=your-email@company.com
   JIRA_API_TOKEN=your_jira_api_token
   
   # Confluence Configuration
   CONFLUENCE_SERVER=https://your-company.atlassian.net
   CONFLUENCE_USERNAME=your-email@company.com
   CONFLUENCE_API_TOKEN=your_confluence_api_token
   
   # Django Settings
   SECRET_KEY=your_generated_secret_key
   DEBUG=True
   ```

4. **Generate Django SECRET_KEY**
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Start the development server**
   ```bash
   python manage.py runserver
   ```

### API Token Setup

#### JIRA API Token
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label and copy the generated token
4. Use your email as username and the token as password

#### Confluence API Token
- Use the same API token as JIRA (they share the same authentication system)

## Usage Examples

### Ticket Management
```
User: "Create a ticket for printer not working in office"
Bot: Created ticket SUP-123: Printer not working in office

User: "SUP-123"
Bot: **Ticket SUP-123**
     Summary: Printer not working in office
     Status: Open
     Priority: Medium
     ...

User: "Update SUP-123 status to in progress"
Bot: ✅ Ticket SUP-123 status updated! New Status: In Progress

User: "Add comment to SUP-123: Checked printer cables, all connections secure"
Bot: ✅ Comment added to SUP-123!

User: "Resolve SUP-123 with comment: Printer driver updated, issue resolved"
Bot: ✅ Ticket SUP-123 has been resolved!
```

### Documentation
```
User: "Create a confluence page for troubleshooting WiFi connection issues"
Bot: Created Confluence page 'WiFi Connection Troubleshooting Guide' successfully!

User: "Find confluence page about password reset"
Bot: Found Confluence pages:
     **Microsoft Password Reset Troubleshooting Guide**
     Content: Step-by-step guide for resetting passwords...
```

### Search and Solutions
```
User: "Find tickets about network issues"
Bot: Found tickets:
     **SUP-456**: Network connectivity problems
     Status: Open | Priority: High

User: "Provide solution for SUP-456"
Bot: **Solution for SUP-456: Network connectivity problems**
     
     1. Check physical connections...
     2. Restart network equipment...
     3. Verify IP configuration...
```

## Architecture

- **Django Framework**: Web application backend
- **JIRA API Integration**: Using `jira` Python library
- **Confluence API Integration**: Using `atlassian-python-api`
- **Ollama Integration**: Local LLM for natural language processing
- **SQLite Database**: Session and conversation storage
- **Environment-based Configuration**: Secure credential management

## Security Features

- Environment variable configuration for all credentials
- No hardcoded API tokens or passwords
- Session-based conversation tracking
- Secure Django SECRET_KEY generation
- Git-ignored environment files

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.
