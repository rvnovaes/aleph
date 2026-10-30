import hashlib
import json
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.db import connection, transaction
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from .models import Document, LoginAttempt, Work
from .schemas import Credentials


@require_GET
def session(request):
    return JsonResponse(
        {
            "username": request.user.username if request.user.is_authenticated else None,
            "csrf": get_token(request),
        }
    )


@require_POST
def sign_in(request):
    try:
        payload = Credentials.model_validate(json.loads(request.body))
    except (ValueError, ValidationError):
        return JsonResponse({"detail": "Informe usuário e senha."}, status=400)
    key = hashlib.sha256(payload.username.lower().encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.get_or_create(key=key, defaults={"started_at": now})
        attempt = LoginAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.started_at < now - timedelta(minutes=10):
            attempt.count = 0
            attempt.started_at = now
        if attempt.count >= 10:
            return JsonResponse({"detail": "Muitas tentativas. Aguarde 10 minutos."}, status=429)
        attempt.count += 1
        attempt.save()
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        return JsonResponse({"detail": "Usuário ou senha incorretos."}, status=401)
    login(request, user)
    LoginAttempt.objects.filter(key=key).delete()
    return JsonResponse({"username": user.username, "csrf": get_token(request)})


@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({"ok": True})


@require_GET
def pdf(request, document_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Autenticação necessária."}, status=401)
    document = get_object_or_404(Document, pk=document_id, work__owner=request.user)
    response = FileResponse(
        document.file.open("rb"),
        content_type="application/pdf",
        as_attachment=request.GET.get("download") == "1",
        filename=document.original_name,
    )
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = "sandbox"
    return response


@require_GET
def cover(request, work_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Autenticação necessária."}, status=401)
    work = get_object_or_404(Work, pk=work_id, owner=request.user)
    if not work.cover:
        return JsonResponse({"detail": "Capa não cadastrada."}, status=404)
    response = FileResponse(work.cover.open("rb"), content_type="image/webp")
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
