from django.contrib import admin

from .models import (
    Category,
    Scenario,
    ScenarioAnswer,
    ScenarioChoice,
    ScenarioSession,
    ScenarioStep,
)


class ScenarioChoiceInline(admin.StackedInline):
    model = ScenarioChoice
    extra = 1


@admin.register(ScenarioStep)
class ScenarioStepAdmin(admin.ModelAdmin):
    list_display = ["order", "title", "category", "scenario"]
    list_filter = ["scenario", "category"]
    filter_horizontal = ["shown_if_choices"]
    inlines = [ScenarioChoiceInline]


class ScenarioStepInline(admin.TabularInline):
    model = ScenarioStep
    fields = ["order", "title", "category"]
    extra = 0
    show_change_link = True


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    inlines = [ScenarioStepInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "subcategory"]


class ScenarioAnswerInline(admin.TabularInline):
    model = ScenarioAnswer
    fields = ["step", "choice", "duration_seconds", "answered_at"]
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(ScenarioSession)
class ScenarioSessionAdmin(admin.ModelAdmin):
    list_display = ["participant_name", "scenario", "status", "started_at", "completed_at"]
    list_filter = ["status", "scenario"]
    readonly_fields = ["trust", "current_step", "current_step_shown_at", "completed_at"]
    inlines = [ScenarioAnswerInline]
