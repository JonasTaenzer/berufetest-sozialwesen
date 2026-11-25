from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Scenario, ScenarioAnswer, ScenarioChoice, ScenarioSession

SESSION_KEY = "scenario_sessions"
TRUST_MIN, TRUST_MAX = 0, 100
# Ab so vielen Antworten je Situation werden Zeiten im Protokoll markiert
MIN_ANSWERS_FOR_FLAG = 3


def _get_own_session(request, session_id):
    """Lädt einen Durchlauf, aber nur, wenn er in diesem Browser gestartet wurde."""
    if session_id not in request.session.get(SESSION_KEY, []):
        raise PermissionDenied
    return get_object_or_404(ScenarioSession, pk=session_id)


def index(request):
    """Startseite: Namen eingeben und Spiel starten oder fortsetzen."""
    scenario = Scenario.objects.filter(is_active=True).first()
    own_ids = request.session.get(SESSION_KEY, [])
    running = ScenarioSession.objects.filter(
        pk__in=own_ids, status=ScenarioSession.STATUS_RUNNING
    ).first()

    error = None
    if request.method == "POST" and scenario:
        name = request.POST.get("participant_name", "").strip()
        if not name:
            error = "Bitte gib deinen Namen ein."
        else:
            session = ScenarioSession.objects.create(
                scenario=scenario, participant_name=name[:200], trust=scenario.start_trust
            )
            request.session[SESSION_KEY] = own_ids + [session.pk]
            return redirect("szenario:play", session_id=session.pk)

    return render(
        request,
        "szenario/index.html",
        {"scenario": scenario, "running": running, "error": error},
    )


def play(request, session_id):
    """Zeigt die aktuelle Situation und startet die Zeitmessung."""
    session = _get_own_session(request, session_id)
    if session.status == ScenarioSession.STATUS_COMPLETED:
        return redirect("szenario:done", session_id=session.pk)

    if session.current_step is None:
        step = session.next_step()
        if step is None:
            session.status = ScenarioSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at"])
            return redirect("szenario:done", session_id=session.pk)
        # Die Zeit läuft ab dem ersten Anzeigen. Ein Neuladen setzt sie nicht zurück.
        session.current_step = step
        session.current_step_shown_at = timezone.now()
        session.save(update_fields=["current_step", "current_step_shown_at"])

    step = session.current_step
    return render(
        request,
        "szenario/play.html",
        {
            "session": session,
            "step": step,
            "choices": step.choices.all(),
            "number": session.answers.count() + 1,
        },
    )


@require_POST
def answer(request, session_id):
    """Speichert die Entscheidung. Der Browser schickt nur die ID der Antwort."""
    session = _get_own_session(request, session_id)
    if session.status != ScenarioSession.STATUS_RUNNING or session.current_step is None:
        return redirect("szenario:play", session_id=session.pk)

    choice = ScenarioChoice.objects.filter(
        pk=request.POST.get("choice_id") or 0, step=session.current_step
    ).first()
    if choice is None:
        # Antwort gehört nicht zur aktuellen Situation
        return redirect("szenario:play", session_id=session.pk)

    now = timezone.now()
    with transaction.atomic():
        ScenarioAnswer.objects.create(
            session=session,
            step=session.current_step,
            choice=choice,
            shown_at=session.current_step_shown_at,
            answered_at=now,
            duration_seconds=(now - session.current_step_shown_at).total_seconds(),
        )
        session.trust = max(TRUST_MIN, min(TRUST_MAX, session.trust + choice.trust_delta))
        session.current_step = None
        session.current_step_shown_at = None
        session.save(update_fields=["trust", "current_step", "current_step_shown_at"])

    return redirect("szenario:consequence", session_id=session.pk)


def consequence(request, session_id):
    """Zeigt die Folge der letzten Entscheidung, ohne Punkte."""
    session = _get_own_session(request, session_id)
    last = session.answers.select_related("choice").last()
    if last is None:
        return redirect("szenario:play", session_id=session.pk)
    return render(request, "szenario/consequence.html", {"session": session, "last": last})


def done(request, session_id):
    """Abschlussseite für den Teilnehmer, bewusst ohne Wertung."""
    session = _get_own_session(request, session_id)
    return render(request, "szenario/done.html", {"session": session})


@staff_member_required
def protocol_list(request):
    """Übersicht aller Durchläufe für Coaches."""
    sessions = ScenarioSession.objects.select_related("scenario")
    return render(request, "szenario/protocol_list.html", {"sessions": sessions})


@staff_member_required
def protocol_detail(request, session_id):
    """Protokoll eines Durchlaufs als Grundlage für das Motivationsinterview."""
    session = get_object_or_404(ScenarioSession, pk=session_id)
    rows = []
    for ans in session.answers.select_related("step__category", "choice"):
        avg = None
        flag = ""
        if ans.step.answers.count() >= MIN_ANSWERS_FOR_FLAG:
            avg = ans.step.average_duration()
            if ans.duration_seconds < avg / 2:
                flag = "auffällig schnell"
            elif ans.duration_seconds > avg * 2:
                flag = "auffällig lang"
        rows.append({"answer": ans, "avg": avg, "flag": flag})
    return render(
        request,
        "szenario/protocol_detail.html",
        {"session": session, "rows": rows, "min_answers": MIN_ANSWERS_FOR_FLAG},
    )
