document.addEventListener('DOMContentLoaded', function () {
    // Get DOM elements
    const chatContainer = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');

    const autoAssignToggle = document.getElementById('autoAssignToggle');
    const chatSessions = document.getElementById('chatSessions');
    const newChatBtn = document.getElementById('newChatBtn');
    const renameChatBtn = document.getElementById('renameChatBtn');
    const deleteChatBtn = document.getElementById('deleteChatBtn');
    const chatTitle = document.getElementById('chatTitle');

    // Initialize chat history and sessions
    initializeChatHistory();
    loadChatSessions();

    // Load saved toggle state
    const savedToggleState = localStorage.getItem('autoAssignToggle');
    if (savedToggleState !== null) {
        autoAssignToggle.checked = savedToggleState === 'true';
    }

    // Save toggle state when changed and update UI
    autoAssignToggle.addEventListener('change', function() {
        localStorage.setItem('autoAssignToggle', this.checked);
        updateToggleStatus();
    });

    // Update toggle status display
    function updateToggleStatus() {
        const statusElement = document.getElementById('toggleStatus');
        if (autoAssignToggle.checked) {
            statusElement.textContent = '✅ ON - Tickets will be assigned to you';
            statusElement.className = 'text-success d-block';
        } else {
            statusElement.textContent = '❌ OFF - Tickets will remain unassigned';
            statusElement.className = 'text-muted d-block';
        }
    }

    // Initialize status display
    updateToggleStatus();

    // Chat history functions
    function initializeChatHistory() {
        if (window.chatData && window.chatData.chatHistory) {
            const history = window.chatData.chatHistory;
            chatContainer.innerHTML = '';

            history.forEach(msg => {
                addUserMessage(msg.user_message, false);
                addBotMessage(msg.bot_response, false);
            });

            scrollToBottom();
        }
    }

    function loadChatSessions() {
        fetch('/api/chat-sessions/')
            .then(response => response.json())
            .then(data => {
                renderChatSessions(data.sessions);
            })
            .catch(error => console.error('Error loading chat sessions:', error));
    }

    function renderChatSessions(sessions) {
        chatSessions.innerHTML = '';

        sessions.forEach(session => {
            const sessionElement = document.createElement('div');
            sessionElement.className = `list-group-item list-group-item-action ${session.session_id === window.chatData.currentSessionId ? 'active' : ''}`;
            sessionElement.style.cursor = 'pointer';

            const title = session.title || 'New Chat';
            const messageCount = session.message_count || 0;
            const lastActivity = new Date(session.last_activity).toLocaleDateString();

            sessionElement.innerHTML = `
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${title}</h6>
                    <small>${lastActivity}</small>
                </div>
                <p class="mb-1">${messageCount} messages</p>
            `;

            sessionElement.addEventListener('click', () => {
                if (session.session_id !== window.chatData.currentSessionId) {
                    window.location.href = `/chat/${session.session_id}/`;
                }
            });

            chatSessions.appendChild(sessionElement);
        });
    }

    // New chat button
    newChatBtn.addEventListener('click', function() {
        fetch('/api/new-chat/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.session_id) {
                window.location.href = `/chat/${data.session_id}/`;
            }
        })
        .catch(error => console.error('Error creating new chat:', error));
    });

    // Show rename/delete buttons if we have a current session
    if (window.chatData.currentSessionId) {
        renameChatBtn.style.display = 'inline-block';
        deleteChatBtn.style.display = 'inline-block';
    }

    // Handle form submission
    chatForm.addEventListener('submit', async function (e) {
        e.preventDefault(); // Stop default form submission

        const message = userInput.value.trim();
        if (!message) return;

        // Disable input while processing
        userInput.disabled = true;
        const submitBtn = chatForm.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending...';

        try {
            // Show user's message immediately
            addUserMessage(message);

            // Clear input
            userInput.value = '';

            // Send to server and handle streaming response
            await sendMessageAndStream(message);

        } catch (error) {
            console.error('Error:', error);
            showErrorMessage('Sorry, something went wrong. Please try again.');
        } finally {
            // Re-enable input
            userInput.disabled = false;
            submitBtn.disabled = false;
            submitBtn.textContent = originalBtnText;
            userInput.focus();
        }
    });

    // Add user message to chat
    function addUserMessage(message, scroll = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'user-message';
        messageDiv.innerHTML = `<strong>You:</strong> ${escapeHtml(message)}`;
        chatContainer.appendChild(messageDiv);
        if (scroll) scrollToBottom();
    }

    // Add bot message to chat (for loading history)
    function addBotMessage(message, scroll = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'bot-message';
        messageDiv.innerHTML = `<strong>AI:</strong> ${escapeHtml(message)}`;
        chatContainer.appendChild(messageDiv);
        if (scroll) scrollToBottom();
    }

    // Create empty bot message container
    function createBotMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'bot-message message-loading';
        messageDiv.innerHTML = '<strong>AI:</strong> <span class="response-content">Thinking...</span>';
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv.querySelector('.response-content');
    }

    // Show error message
    function showErrorMessage(error) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'bot-message';
        messageDiv.style.borderLeftColor = '#dc3545';
        messageDiv.style.background = '#f8d7da';
        messageDiv.innerHTML = `<strong>Error:</strong> ${escapeHtml(error)}`;
        chatContainer.appendChild(messageDiv);
        scrollToBottom();
    }

    // Send message and handle streaming response
    async function sendMessageAndStream(message) {
        // Create FormData (matches Django expectation)
        const formData = new FormData();
        formData.append('user_input', message);
        formData.append('auto_assign', autoAssignToggle.checked);

        // Make request to Django endpoint
        const response = await fetch(window.location.pathname, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken() // Django CSRF protection
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Create bot message container
        const botResponseElement = createBotMessage();
        botResponseElement.textContent = '';
        botResponseElement.parentElement.classList.remove('message-loading');

        // Get stream reader
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        // Read stream chunks
        while (true) {
            const {
                done,
                value
            } = await reader.read();

            if (done) break;

            // Decode chunk and add to bot message
            const chunk = decoder.decode(value, {
                stream: true
            });
            botResponseElement.textContent += chunk;

            // Auto-scroll to bottom
            scrollToBottom();
        }
    }

    // Rename and delete functionality
    renameChatBtn.addEventListener('click', function() {
        const modal = new bootstrap.Modal(document.getElementById('renameModal'));
        document.getElementById('newChatTitle').value = chatTitle.textContent;
        modal.show();
    });

    document.getElementById('saveRenameBtn').addEventListener('click', function() {
        const newTitle = document.getElementById('newChatTitle').value.trim();
        if (newTitle && window.chatData.currentSessionId) {
            const formData = new FormData();
            formData.append('title', newTitle);

            fetch(`/api/rename-chat/${window.chatData.currentSessionId}/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    chatTitle.textContent = data.title;
                    loadChatSessions(); // Refresh sidebar
                    bootstrap.Modal.getInstance(document.getElementById('renameModal')).hide();
                }
            })
            .catch(error => console.error('Error renaming chat:', error));
        }
    });

    deleteChatBtn.addEventListener('click', function() {
        if (confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
            fetch(`/api/delete-chat/${window.chatData.currentSessionId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = '/'; // Redirect to new chat
                }
            })
            .catch(error => console.error('Error deleting chat:', error));
        }
    });

    // Utility functions
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
            document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }

    // Focus input on page load
    userInput.focus();
});