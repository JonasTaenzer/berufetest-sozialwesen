from django.core.management.base import BaseCommand
from django.db import transaction

from szenario.models import Category, Scenario, ScenarioSession, ScenarioStep

SCENARIO_NAME = "Ein Arbeitstag im Sozialwesen"

SCENARIO_DESCRIPTION = (
    "Du arbeitest in einer sozialen Einrichtung. Die Menschen, die du betreust, "
    "können Kinder, Jugendliche oder Erwachsene sein.\n"
    "Heute begleitest du sie durch einen ganz normalen Arbeitstag mit acht Situationen."
)

# Kategorien aus dem Fragenkatalog des Motivationsinterviews (ohne Arbeits- und Lernmotivation)
CATEGORIES = {
    "autonomie": ("Pädagogische Haltung", "Autonomie zutrauen"),
    "flexibilitaet": ("Pädagogische Haltung", "Situative Flexibilität"),
    "ueberblick": ("Organisationsfähigkeit", "Systematik & Überblick"),
    "geduld": ("Stressresistenz", "Geduld"),
    "deeskalation": ("Konfliktkompetenz", "Deeskalation"),
    "fehler": ("Kooperation", "Eigene Fehler und Grenzen offenlegen"),
    "gewissenhaftigkeit": ("Gewissenhaftigkeit", ""),
    "selbstreflexion": ("Selbstreflexion", ""),
}

# (Antwort, Folge im Spiel, Änderung Vertrauensleiste)
FEEDBACK_CHOICES = [
    (
        "Du hörst zu, fragst nach, was sie genau beobachtet hat, und sagst, dass du darüber nachdenkst.",
        "Ihr redet kurz. Du nimmst einen Gedanken mit, den du morgen ausprobieren willst.",
        10,
    ),
    (
        "Du erklärst ausführlich, warum du richtig gehandelt hast.",
        "Die Kollegin nickt, wirkt aber nicht überzeugt.",
        0,
    ),
    (
        "Du sagst: „Ich hatte einen anstrengenden Tag, lass uns morgen darüber reden.“",
        "Ihr verabredet euch für morgen. Ob das Gespräch stattfindet, bleibt offen.",
        0,
    ),
    (
        "Du sagst, dass sie ja nicht dabei war, und gehst.",
        "Die Kollegin ist verletzt. Die Stimmung im Team ist angespannt.",
        -10,
    ),
]

FEEDBACK_QUESTION = (
    "Frage 9.2: Beschreiben Sie eine Situation, in der jemand Ihre Arbeit oder Ihr Verhalten "
    "kritisiert hat und Sie das im ersten Moment für ungerechtfertigt hielten. "
    "Was haben Sie gemacht?"
)

STEPS = [
    {
        "key": "autonomie",
        "title": "Morgens: Allein los",
        "text": (
            "Kurz nach Dienstbeginn. Mara, die du betreust, möchte heute zum ersten Mal allein "
            "zum Bäcker an der Ecke gehen. Sie ist sehr stolz darauf. Du bist nicht sicher, "
            "ob sie den Weg schon sicher schafft."
        ),
        "question": (
            "Frage 3.1: Erzählen Sie von einer Situation, in der jemand etwas allein ausprobieren "
            "wollte, von dem Sie nicht sicher waren, ob er es schon kann. Wie haben Sie entschieden?"
        ),
        "choices": [
            (
                "Du lässt sie gehen, besprichst vorher kurz den Weg und vereinbarst, wann sie zurück ist.",
                "Mara kommt strahlend mit einer Brezel zurück, zwei Minuten früher als vereinbart.",
                10,
            ),
            (
                "Du sagst, dass das heute noch nicht geht, und gehst lieber mit.",
                "Mara geht mit, ist aber still und enttäuscht.",
                -5,
            ),
            (
                "Du lässt sie gehen und schaust ihr unauffällig hinterher.",
                "Mara schafft es. Als sie dich am Fenster entdeckt, verdreht sie die Augen, lacht aber.",
                5,
            ),
            (
                "Du sagst „Mach ruhig“ und kümmerst dich um deine Aufgaben.",
                "Mara kommt erst nach 40 Minuten zurück. Sie hatte sich verlaufen und ist durcheinander.",
                -5,
            ),
        ],
    },
    {
        "key": "flexibilitaet",
        "title": "Vormittag: Das Angebot kippt",
        "text": (
            "Du hast für die Gruppe eine Bastelaktion vorbereitet. Nach zehn Minuten ist die "
            "Stimmung schlecht: Einige langweilen sich, zwei sind überfordert, es wird unruhig. "
            "Dann klopft der Hausmeister: Der Raum wird in einer Viertelstunde gebraucht."
        ),
        "question": (
            "Frage 3.3: Erzählen Sie von einer Situation, in der Sie etwas für eine Gruppe "
            "vorbereitet hatten und es hat nicht funktioniert. Was haben Sie gemacht?"
        ),
        "choices": [
            (
                "Du brichst ab und gehst mit allen nach draußen für eine Bewegungsrunde.",
                "Draußen löst sich die Spannung. Einige fragen, ob ihr das morgen wieder macht.",
                10,
            ),
            (
                "Du ziehst die Bastelaktion so schnell wie möglich durch, damit der Raum frei wird.",
                "Ihr werdet fertig, aber zwei sind frustriert, und die Ergebnisse landen im Müll.",
                -5,
            ),
            (
                "Du fragst die Gruppe, worauf sie jetzt Lust hat, und ihr entscheidet gemeinsam.",
                "Die Gruppe wählt ein Spiel im Flur. Es dauert etwas, aber alle machen mit.",
                10,
            ),
            (
                "Du bittest den Hausmeister, später wiederzukommen.",
                "Er ist genervt. Die Unruhe in der Gruppe bleibt.",
                0,
            ),
        ],
    },
    {
        "key": "ueberblick",
        "title": "Mittag: Alles gleichzeitig",
        "text": (
            "Du telefonierst gerade mit einer Angehörigen. Eine Kollegin winkt dir, sie braucht "
            "kurz Hilfe beim Tragen. Gleichzeitig steht Leon vor dir und sagt leise: "
            "„Kann ich mal mit dir reden? Es ist wichtig.“"
        ),
        "question": (
            "Frage 4.4: Erzählen Sie von einer Situation, in der jemand mit einem Anliegen zu Ihnen "
            "kam, während Sie mitten in einer anderen Aufgabe steckten. Wie sind Sie damit umgegangen?"
        ),
        "choices": [
            (
                "Du sagst Leon, dass du in fünf Minuten zu ihm kommst, beendest das Telefonat "
                "und gibst der Kollegin Bescheid, dass du gleich hilfst.",
                "Leon wartet. Als du zu ihm kommst, erzählt er dir, dass er Ärger zu Hause hat.",
                10,
            ),
            (
                "Du legst sofort auf und wendest dich Leon zu.",
                "Leon öffnet sich, aber die Angehörige ruft kurz darauf verärgert noch einmal an.",
                0,
            ),
            (
                "Du hilfst zuerst der Kollegin, danach siehst du weiter.",
                "Als du zurückkommst, ist Leon weg. Später sagt er nur: „War nicht so wichtig.“",
                -5,
            ),
            (
                "Du telefonierst in Ruhe zu Ende und bittest beide zu warten.",
                "Die Kollegin trägt allein. Leon zieht sich zurück.",
                -5,
            ),
        ],
    },
    {
        "key": "geduld",
        "title": "Früher Nachmittag: Es dauert",
        "text": (
            "Du übst mit Samira, ihren Wochenplan selbst aufzuschreiben. Sie braucht viel länger "
            "als gedacht und fängt zweimal von vorn an. Im Hintergrund ist es laut, und zwei "
            "andere warten schon auf dich."
        ),
        "question": (
            "Frage 6.2: Beschreiben Sie eine Situation, in der jemand Ihre volle Aufmerksamkeit "
            "brauchte, während gleichzeitig andere auf Sie gewartet haben. Wie haben Sie das gelöst?"
        ),
        "choices": [
            (
                "Du bleibst ruhig bei Samira und sagst den anderen, wann du für sie da bist.",
                "Samira schafft es. Die anderen murren kurz, warten aber.",
                10,
            ),
            (
                "Du schreibst den Plan schnell selbst fertig, damit es weitergeht.",
                "Es geht schneller, aber Samira sagt: „Dann kann ich es ja eh nicht.“",
                -5,
            ),
            (
                "Du gibst Samira eine Vorlage, gehst kurz zu den anderen und kommst dann zurück.",
                "Mit der Vorlage kommt Samira allein ein gutes Stück weiter.",
                5,
            ),
            (
                "Du sagst gereizt, dass sie sich jetzt mal konzentrieren soll.",
                "Samira hört auf und will nicht mehr weitermachen.",
                -10,
            ),
        ],
    },
    {
        "key": "deeskalation",
        "title": "Nachmittag: Streit",
        "text": (
            "Im Gemeinschaftsraum geraten Tom und Ali aneinander. Es wird laut, Tom schubst Ali "
            "gegen den Tisch. Die anderen schauen gebannt zu."
        ),
        "question": (
            "Frage 8.1: Erzählen Sie von einer Situation, in der zwei Menschen in Ihrer Gegenwart "
            "aneinandergeraten sind. Was haben Sie getan?"
        ),
        "choices": [
            (
                "Du gehst ruhig dazwischen, trennst die beiden und sprichst danach mit jedem einzeln.",
                "Die beiden beruhigen sich. Im Einzelgespräch erfährst du, worum es ging.",
                10,
            ),
            (
                "Du rufst laut „Schluss jetzt!“ und schickst beide sofort aus dem Raum.",
                "Es wird still. Tom knallt die Tür, Ali fühlt sich ungerecht behandelt.",
                0,
            ),
            (
                "Du wartest erst ab, ob sie es selbst klären.",
                "Der Streit wird heftiger. Ali hat danach einen blauen Fleck.",
                -10,
            ),
            (
                "Du holst sofort eine Kollegin dazu und sicherst mit ihr die Situation.",
                "Zu zweit beruhigt ihr die Lage. Es hat etwas gedauert, bis die Kollegin da war.",
                5,
            ),
        ],
    },
    {
        "key": "fehler",
        "title": "Später Nachmittag: Etwas vergessen",
        "text": (
            "Dir fällt ein: Samiras Schwester hat dich heute Morgen gebeten, dem Spätdienst "
            "auszurichten, dass Samira um 17 Uhr abgeholt wird. Das hast du vergessen. "
            "Bisher hat es niemand bemerkt."
        ),
        "question": (
            "Frage 7.3: Erzählen Sie von einem Fehler, der Ihnen unterlaufen ist und den zunächst "
            "niemand außer Ihnen bemerkt hat. Wie sind Sie damit umgegangen?"
        ),
        "choices": [
            (
                "Du sagst es sofort dem Spätdienst und entschuldigst dich.",
                "Die Kollegin ist dankbar. Die Abholung klappt ohne Probleme.",
                10,
            ),
            (
                "Du gibst die Info weiter, ohne zu erwähnen, dass sie schon seit heute Morgen bekannt war.",
                "Die Abholung klappt. Später fragt die Kollegin, warum sie es erst so spät erfahren hat.",
                0,
            ),
            (
                "Du hoffst, dass Samiras Schwester selbst noch einmal anruft.",
                "Um 17 Uhr steht die Schwester da, aber Samira ist mit der Gruppe unterwegs.",
                -10,
            ),
            (
                "Du schreibst es ins Übergabebuch, sagst aber nichts.",
                "Die Kollegin liest es erst um 16:55 Uhr. Es wird knapp.",
                0,
            ),
        ],
    },
    {
        "key": "gewissenhaftigkeit",
        "title": "Kurz vor Feierabend: Die Übergabe",
        "text": (
            "Der Tag war voll, du bist müde, und in zehn Minuten ist Feierabend. "
            "Die Dokumentation zum Streit und die Übergabe für morgen fehlen noch."
        ),
        "question": (
            "Frage 5.1: Erzählen Sie von einer Aufgabe, bei der Sie regelmäßig etwas schriftlich "
            "festhalten mussten. Wie sind Sie damit umgegangen, wenn der Tag voll war?"
        ),
        "choices": [
            (
                "Du schreibst kurz das Wichtigste auf und machst eine knappe Übergabe, "
                "auch wenn du dafür etwas länger bleibst.",
                "Der Frühdienst weiß morgen Bescheid und kann gut anknüpfen.",
                10,
            ),
            (
                "Du erzählst der Kollegin vom Spätdienst kurz mündlich, was los war.",
                "Sie hört zu, ist aber abgelenkt. Morgen früh weiß niemand Bescheid.",
                0,
            ),
            (
                "Du nimmst dir vor, es morgen früh nachzutragen.",
                "Am nächsten Morgen ist so viel los, dass du es vergisst.",
                -5,
            ),
            (
                "Du schreibst alles ausführlich auf, mit allen Details und deiner Meinung zu Tom.",
                "Du bleibst eine Stunde länger. Im Bericht vermischen sich Beobachtung und Bewertung.",
                0,
            ),
        ],
    },
]

# Situation 8 hat drei Varianten. Welche erscheint, hängt von der Entscheidung im Streit ab.
FEEDBACK_VARIANTS = [
    (
        "„Wie du vorhin Tom und Ali angeschrien hast, fand ich nicht gut. "
        "Die anderen hatten richtig Angst.“",
        [1],
    ),
    (
        "„Warum hast du beim Streit so lange gewartet? Ali hätte sich ernsthaft verletzen können.“",
        [2],
    ),
    (
        "„Den Streit hast du gut gelöst. Aber du hättest dem Team sofort Bescheid geben müssen, "
        "wir wussten von nichts.“",
        [0, 3],
    ),
]


class Command(BaseCommand):
    help = "Legt das Demo-Szenario mit 8 Situationen an."

    def add_arguments(self, parser):
        parser.add_argument(
            "--neu",
            action="store_true",
            help="Vorhandenes Demo-Szenario samt Durchläufen löschen und neu anlegen.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Scenario.objects.filter(name=SCENARIO_NAME)
        if existing.exists():
            if not options["neu"]:
                self.stdout.write("Demo-Szenario ist schon vorhanden. Mit --neu neu anlegen.")
                return
            ScenarioSession.objects.filter(scenario__in=existing).delete()
            existing.delete()

        categories = {
            key: Category.objects.get_or_create(name=name, subcategory=sub)[0]
            for key, (name, sub) in CATEGORIES.items()
        }
        scenario = Scenario.objects.create(name=SCENARIO_NAME, description=SCENARIO_DESCRIPTION)

        conflict_choices = []
        for order, data in enumerate(STEPS, start=1):
            step = ScenarioStep.objects.create(
                scenario=scenario,
                order=order,
                title=data["title"],
                text=data["text"],
                category=categories[data["key"]],
                interview_question=data["question"],
            )
            choices = [
                step.choices.create(text=text, consequence_text=cons, trust_delta=delta)
                for text, cons, delta in data["choices"]
            ]
            if data["key"] == "deeskalation":
                conflict_choices = choices

        for quote, choice_indexes in FEEDBACK_VARIANTS:
            step = ScenarioStep.objects.create(
                scenario=scenario,
                order=len(STEPS) + 1,
                title="Auf dem Weg nach draußen: Kritik",
                text=f"Auf dem Weg nach draußen spricht dich eine Kollegin an: {quote}",
                category=categories["selbstreflexion"],
                interview_question=FEEDBACK_QUESTION,
            )
            step.shown_if_choices.set([conflict_choices[i] for i in choice_indexes])
            for text, cons, delta in FEEDBACK_CHOICES:
                step.choices.create(text=text, consequence_text=cons, trust_delta=delta)

        self.stdout.write(self.style.SUCCESS(f"Demo-Szenario „{SCENARIO_NAME}“ angelegt."))
