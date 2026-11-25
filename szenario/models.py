from django.db import models
from django.db.models import Avg


class Category(models.Model):
    """Kategorie aus dem Fragenkatalog des Motivationsinterviews.

    Platzhalter für den Prototyp. Im großen Projekt wird daraus ein
    Fremdschlüssel auf MotivationCategory bzw. MotivationSubcategory.
    """

    name = models.CharField("Kategorie", max_length=100)
    subcategory = models.CharField("Unterkategorie", max_length=100, blank=True)

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"
        ordering = ["name", "subcategory"]

    def __str__(self):
        if self.subcategory:
            return f"{self.name} – {self.subcategory}"
        return self.name


class Scenario(models.Model):
    """Ein Spiel, z. B. "Ein Arbeitstag im Sozialwesen"."""

    name = models.CharField("Name", max_length=200)
    description = models.TextField("Einleitung", blank=True)
    is_active = models.BooleanField("Aktiv", default=True)
    start_trust = models.PositiveSmallIntegerField("Startwert Vertrauen", default=50)

    class Meta:
        verbose_name = "Szenario"
        verbose_name_plural = "Szenarien"

    def __str__(self):
        return self.name


class ScenarioStep(models.Model):
    """Eine Situation im Tagesablauf, genau einer Kategorie zugeordnet."""

    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField("Reihenfolge")
    title = models.CharField("Titel", max_length=200)
    text = models.TextField("Situation")
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="steps", verbose_name="Kategorie"
    )
    interview_question = models.TextField("Frage für das Gespräch", blank=True)
    shown_if_choices = models.ManyToManyField(
        "ScenarioChoice",
        blank=True,
        related_name="unlocks_steps",
        verbose_name="Nur zeigen nach diesen Entscheidungen",
        help_text="Leer lassen, wenn die Situation immer gezeigt wird.",
    )

    class Meta:
        verbose_name = "Situation"
        verbose_name_plural = "Situationen"
        ordering = ["scenario", "order", "pk"]

    def __str__(self):
        return f"{self.order}. {self.title}"

    def average_duration(self):
        """Durchschnittliche Entscheidungszeit aller Teilnehmer in Sekunden."""
        return self.answers.aggregate(avg=Avg("duration_seconds"))["avg"]


class ScenarioChoice(models.Model):
    """Eine Handlungsoption mit ihrer Folge im Spiel."""

    step = models.ForeignKey(ScenarioStep, on_delete=models.CASCADE, related_name="choices")
    text = models.TextField("Antwort")
    consequence_text = models.TextField("Folge im Spiel")
    trust_delta = models.SmallIntegerField(
        "Änderung Vertrauensleiste",
        default=0,
        help_text="Nur für die Geschichte. Wird nicht als Punktwert ausgewertet.",
    )

    class Meta:
        verbose_name = "Antwortoption"
        verbose_name_plural = "Antwortoptionen"
        ordering = ["step", "pk"]

    def __str__(self):
        return self.text[:60]


class ScenarioSession(models.Model):
    """Ein Durchlauf eines Teilnehmers."""

    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Läuft"),
        (STATUS_COMPLETED, "Abgeschlossen"),
    ]

    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="sessions")
    participant_name = models.CharField("Teilnehmer", max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    trust = models.SmallIntegerField("Vertrauen", default=50)
    current_step = models.ForeignKey(
        ScenarioStep, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    current_step_shown_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Durchlauf"
        verbose_name_plural = "Durchläufe"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.participant_name} – {self.scenario}"

    def next_step(self):
        """Nächste Situation nach der Reihenfolge.

        Situationen mit Bedingung werden nur gezeigt, wenn der Teilnehmer
        vorher eine der hinterlegten Antworten gewählt hat.
        """
        chosen = set(self.answers.values_list("choice_id", flat=True))
        answered = set(self.answers.values_list("step_id", flat=True))
        steps = self.scenario.steps.exclude(pk__in=answered).prefetch_related("shown_if_choices")
        for step in steps:
            required = {c.pk for c in step.shown_if_choices.all()}
            if not required or required & chosen:
                return step
        return None


class ScenarioAnswer(models.Model):
    """Eine getroffene Entscheidung mit gemessener Zeit."""

    session = models.ForeignKey(ScenarioSession, on_delete=models.CASCADE, related_name="answers")
    step = models.ForeignKey(ScenarioStep, on_delete=models.PROTECT, related_name="answers")
    choice = models.ForeignKey(ScenarioChoice, on_delete=models.PROTECT, related_name="answers")
    shown_at = models.DateTimeField()
    answered_at = models.DateTimeField()
    duration_seconds = models.FloatField()

    class Meta:
        verbose_name = "Entscheidung"
        verbose_name_plural = "Entscheidungen"
        ordering = ["answered_at"]
        constraints = [
            models.UniqueConstraint(fields=["session", "step"], name="unique_answer_per_step"),
        ]

    def __str__(self):
        return f"{self.session}: {self.step}"
