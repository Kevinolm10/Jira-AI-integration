from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .chat_service import ChatService
from .models import ChatSession, ChatMessage
import uuid
import json

@login_required
@csrf_exempt
def ai_chat(request, session_id=None):
    """Main chat interface view with optional session ID"""
    if request.method == "POST":
        user_input = request.POST["user_input"]
        auto_assign = request.POST.get("auto_assign", "false").lower() == "true"

        # Get session ID from URL parameter or create new one
        if not session_id:
            session_id = request.session.get('chat_session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                request.session['chat_session_id'] = session_id

        # Store auto-assign preference in session
        request.session['auto_assign'] = auto_assign

        # Process message through chat service
        chat_service = ChatService(session_id, user=request.user, auto_assign=auto_assign)

        def response_generator():
            response = chat_service.process_message(user_input)
            for char in response:
                yield char

        return StreamingHttpResponse(response_generator(), content_type='text/plain')

    # For GET requests, load the specific session or create new one
    if session_id:
        # Load specific session
        try:
            chat_session = ChatSession.objects.get(session_id=session_id, user=request.user)
            request.session['chat_session_id'] = session_id
        except ChatSession.DoesNotExist:
            # Session doesn't exist or doesn't belong to user, redirect to new chat
            session_id = None

    if not session_id:
        # Create new session
        session_id = str(uuid.uuid4())
        request.session['chat_session_id'] = session_id

    # Get chat history for this session
    chat_history = []
    if session_id:
        try:
            chat_session = ChatSession.objects.get(session_id=session_id)
            messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')
            chat_history = [
                {
                    'user_message': msg.user_message,
                    'bot_response': msg.bot_response,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        except ChatSession.DoesNotExist:
            pass

    # Get user's chat sessions for sidebar
    user_sessions = ChatSession.objects.filter(
        user=request.user
    ).order_by('-last_activity')[:20]  # Last 20 sessions

    # Serialize user sessions
    sessions_data = []
    for session in user_sessions:
        if not session.title:
            session.generate_title()
        sessions_data.append({
            'session_id': session.session_id,
            'title': session.title or 'New Chat',
            'last_activity': session.last_activity.isoformat(),
            'message_count': session.get_message_count(),
            'created_at': session.created_at.isoformat()
        })

    context = {
        'current_session_id': session_id,
        'chat_history': json.dumps(chat_history),
        'user_sessions': json.dumps(sessions_data)
    }

    return render(request, "ai_chat/chat.html", context)

@login_required
def new_chat(request):
    """Create a new chat session"""
    session_id = str(uuid.uuid4())
    request.session['chat_session_id'] = session_id
    return JsonResponse({'session_id': session_id, 'redirect_url': f'/chat/{session_id}/'})

@login_required
def delete_chat(request, session_id):
    """Delete a chat session"""
    if request.method == "POST":
        try:
            chat_session = ChatSession.objects.get(session_id=session_id, user=request.user)
            chat_session.delete()
            return JsonResponse({'success': True})
        except ChatSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def rename_chat(request, session_id):
    """Rename a chat session"""
    if request.method == "POST":
        try:
            chat_session = ChatSession.objects.get(session_id=session_id, user=request.user)
            new_title = request.POST.get('title', '').strip()
            if new_title:
                chat_session.title = new_title
                chat_session.save()
                return JsonResponse({'success': True, 'title': new_title})
            return JsonResponse({'success': False, 'error': 'Title cannot be empty'})
        except ChatSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Session not found'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def get_chat_sessions(request):
    """Get user's chat sessions for the sidebar"""
    sessions = ChatSession.objects.filter(user=request.user).order_by('-last_activity')[:20]
    sessions_data = []

    for session in sessions:
        # Generate title if not set
        if not session.title:
            session.generate_title()

        sessions_data.append({
            'session_id': session.session_id,
            'title': session.title or 'New Chat',
            'last_activity': session.last_activity.isoformat(),
            'message_count': session.get_message_count(),
            'created_at': session.created_at.isoformat()
        })

    return JsonResponse({'sessions': sessions_data})
