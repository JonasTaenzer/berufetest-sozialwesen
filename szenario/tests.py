from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import ScenarioAnswer, ScenarioChoice, ScenarioSession, ScenarioStep


class GameFlowTests(TestCase):
    """Spielablauf mit dem Demo-Szenario."""

    def setUp(self):
        call_command("demo_laden", stdout=StringIO())

    def start(self, name="Testperson"):
        response = self.client.post(reverse("szenario:index"), {"participant_name": name})
        return ScenarioSession.objects.get(pk=response.url.rstrip("/").split("/")[-1])

    def play_through(self, session, pick=0):
        """Spielt alle Situationen durch und wählt jeweils die Antwort mit Index pick."""
        while True:
            response = self.client.get(reverse("szenario:play", args=[session.pk]))
            if response.status_code == 302:
                return response
            choice = list(response.context["choices"])[pick]
            self.client.post(
                reverse("szenario:answer", args=[session.pk]), {"choice_id": choice.pk}
            )

    def test_full_run_has_eight_answers_and_completes(self):
        session = self.start()
        response = self.play_through(session)
        self.assertEqual(response.url, reverse("szenario:done", args=[session.pk]))
        session.refresh_from_db()
        self.assertEqual(session.status, ScenarioSession.STATUS_COMPLETED)
        self.assertEqual(session.answers.count(), 8)

    def test_branch_depends_on_conflict_choice(self):
        # Antwort 2 im Streit ("abwarten") führt zur Kritik am langen Warten
        session = self.start()
        self.play_through(session, pick=2)
        last_step = session.answers.last().step
        self.assertIn("so lange gewartet", last_step.text)

    def test_duration_is_measured_on_server(self):
        session = self.start()
        self.client.get(reverse("szenario:play", args=[session.pk]))
        session.refresh_from_db()
        # Anzeige 30 Sekunden in die Vergangenheit legen
        session.current_step_shown_at -= timedelta(seconds=30)
        session.save()
        choice = session.current_step.choices.first()
        self.client.post(reverse("szenario:answer", args=[session.pk]), {"choice_id": choice.pk})
        answer = ScenarioAnswer.objects.get(session=session)
        self.assertGreaterEqual(answer.duration_seconds, 30)

    def test_reload_does_not_reset_timer(self):
        session = self.start()
        self.client.get(reverse("szenario:play", args=[session.pk]))
        first = ScenarioSession.objects.get(pk=session.pk).current_step_shown_at
        self.client.get(reverse("szenario:play", args=[session.pk]))
        second = ScenarioSession.objects.get(pk=session.pk).current_step_shown_at
        self.assertEqual(first, second)

    def test_choice_from_other_step_is_rejected(self):
        session = self.start()
        self.client.get(reverse("szenario:play", args=[session.pk]))
        foreign = ScenarioChoice.objects.exclude(step=session.scenario.steps.first()).first()
        self.client.post(reverse("szenario:answer", args=[session.pk]), {"choice_id": foreign.pk})
        self.assertEqual(ScenarioAnswer.objects.count(), 0)

    def test_other_browser_cannot_open_session(self):
        session = self.start()
        self.client.logout()
        self.client.cookies.clear()
        response = self.client.get(reverse("szenario:play", args=[session.pk]))
        self.assertEqual(response.status_code, 403)

    def test_trust_stays_within_bounds(self):
        session = self.start()
        self.play_through(session, pick=3)
        session.refresh_from_db()
        self.assertGreaterEqual(session.trust, 0)
        self.assertLessEqual(session.trust, 100)


class ProtocolTests(TestCase):
    """Protokoll-Ansicht für Coaches."""

    def setUp(self):
        call_command("demo_laden", stdout=StringIO())

    def test_protocol_requires_staff(self):
        response = self.client.get(reverse("szenario:protocol_list"))
        self.assertEqual(response.status_code, 302)

    def test_protocol_flags_unusual_durations(self):
        step = ScenarioStep.objects.order_by("order").first()
        choice = step.choices.first()
        for i, seconds in enumerate([20, 20, 20, 200]):
            session = ScenarioSession.objects.create(
                scenario=step.scenario, participant_name=f"P{i}"
            )
            shown = session.started_at
            ScenarioAnswer.objects.create(
                session=session,
                step=step,
                choice=choice,
                shown_at=shown,
                answered_at=shown + timedelta(seconds=seconds),
                duration_seconds=seconds,
            )
        coach = get_user_model().objects.create_user("coach", password="pw", is_staff=True)
        self.client.force_login(coach)
        response = self.client.get(reverse("szenario:protocol_detail", args=[session.pk]))
        self.assertEqual(response.context["rows"][0]["flag"], "auffällig lang")
        self.assertContains(response, step.interview_question[:30])
