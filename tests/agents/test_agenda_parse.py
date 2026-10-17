"""Unit tests for pure agenda_parse module."""

from __future__ import annotations

from datetime import date, datetime, time
import unittest
from zoneinfo import ZoneInfo

from openjarvis.agents.agenda_parse import (
    build_event_payload,
    format_confirmation_prompt,
    is_create_intent,
    is_short_affirmative,
    parse_create_event,
    parse_date,
    parse_time,
    parse_title,
)

_TZ = ZoneInfo("America/Fortaleza")


class TestAgendaParseAffirmative(unittest.TestCase):
    """Test short affirmative validation."""

    def test_short_affirmative_exact_matches(self):
        valid = ["sim", "Sim", "SIM", "sim!", "sim.", "confirma", "Confirma!", "pode marcar", "Pode marcar.", "isso", "isso!"]
        for phrase in valid:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_short_affirmative(phrase), f"Failed for: {phrase}")

    def test_short_affirmative_negative_cases(self):
        invalid = [
            "sim, mas...",
            "sim, por favor",
            "sim, pode marcar",
            "não",
            "cancela",
            "espera",
            "acho que sim",
            "pode marcar sim",
            "isso mesmo",
            "",
            "ok",
        ]
        for phrase in invalid:
            with self.subTest(phrase=phrase):
                self.assertFalse(is_short_affirmative(phrase), f"Should not match: {phrase}")


class TestAgendaParseIntent(unittest.TestCase):
    """Test detection of create intent vs non-create and summary requests."""

    def test_create_intent_positive(self):
        phrases = [
            "marca reunião amanhã às 15h",
            "marcar dentista na sexta às 10 da manhã",
            "marque uma consulta hoje às 16h",
            "cria um evento almoço dia 23/10 às 12h",
            "criar evento revisão de código amanhã às 15h",
            "crie uma reunião com a equipe amanhã às 10h",
            "agenda dentista amanhã às 15h",
            "agendar consulta amanhã às 14h",
            "agende um café amanhã às 10 da manhã",
            "adiciona um evento almoço amanhã às 12h",
            "novo evento amanhã às 15h",
            "cria um evento hoje às 20h chamado estudar",
            "marca reunião",
            "marca almoço",
            "agendar call amanhã",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_create_intent(phrase), f"Failed for: {phrase}")

    def test_create_intent_negative_general_questions(self):
        # Queries containing 'marca' without date/time or calendar nouns must NOT trigger creation
        negatives = [
            "Que marca de tênis você recomenda?",
            "Qual a melhor marca de café?",
            "Essa marca de carro é boa?",
            "resuma meu dia",
            "o que tenho hoje",
            "minha agenda de hoje",
            "agenda de hoje",
            "como está o tempo hoje?",
            "olá jarvis",
            "sim",
        ]
        for phrase in negatives:
            with self.subTest(phrase=phrase):
                self.assertFalse(is_create_intent(phrase), f"Should not match: {phrase}")


class TestAgendaParseDate(unittest.TestCase):
    """Test pure date parsing and weekday rules."""

    def setUp(self):
        # Base time: Thursday, 2026-10-15 13:00 (weekday = 3)
        self.now = datetime(2026, 10, 15, 13, 0, tzinfo=_TZ)

    def test_parse_date_hoje(self):
        d, raw = parse_date("marca para hoje às 15h", self.now)
        self.assertEqual(d, date(2026, 10, 15))
        self.assertEqual(raw, "hoje")

    def test_parse_date_amanha(self):
        d, raw = parse_date("marca para amanhã às 15h", self.now)
        self.assertEqual(d, date(2026, 10, 16))
        self.assertEqual(raw, "amanhã")

    def test_parse_date_depois_de_amanha(self):
        d, raw = parse_date("marca para depois de amanhã às 15h", self.now)
        self.assertEqual(d, date(2026, 10, 17))
        self.assertEqual(raw, "depois de amanhã")

    def test_weekday_equal_to_today_uses_next_week(self):
        # Today is Thursday (quinta). User asks for "quinta" -> must be next Thursday (+7 days)
        d, raw = parse_date("marca reunião na quinta às 15h", self.now)
        self.assertEqual(d, date(2026, 10, 22))

    def test_weekday_future_same_week(self):
        # Today is Thursday (quinta). User asks for "sexta" -> tomorrow (+1 day)
        d, raw = parse_date("marca dentista na sexta às 10 da manhã", self.now)
        self.assertEqual(d, date(2026, 10, 16))

    def test_weekday_past_in_week_uses_next_week(self):
        # Today is Thursday (quinta). User asks for "terça" -> next Tuesday (2026-10-20)
        d, raw = parse_date("marca reunião na terça às 14h", self.now)
        self.assertEqual(d, date(2026, 10, 20))

    def test_explicit_date_day_month(self):
        d, raw = parse_date("marca dia 23/10 às 15h", self.now)
        self.assertEqual(d, date(2026, 10, 23))

    def test_explicit_date_written_month(self):
        d, raw = parse_date("marca dia 5 de novembro às 10h", self.now)
        self.assertEqual(d, date(2026, 11, 5))


class TestAgendaParseTime(unittest.TestCase):
    """Test pure time parsing, ambiguous detection, and past check."""

    def setUp(self):
        # Base time: 2026-10-15 13:00 (1:00 PM)
        self.now = datetime(2026, 10, 15, 13, 0, tzinfo=_TZ)

    def test_ambiguous_time_without_period(self):
        # "às 3" without morning/afternoon/night is ambiguous
        res = parse_time("marca almoço amanhã às 3", self.now, target_date=date(2026, 10, 16))
        self.assertTrue(res.is_ambiguous)
        self.assertEqual(res.ambiguous_hour, 3)
        self.assertIsNone(res.time)

    def test_ambiguous_time_hour_10(self):
        res = parse_time("marca dentista amanhã às 10", self.now, target_date=date(2026, 10, 16))
        self.assertTrue(res.is_ambiguous)
        self.assertEqual(res.ambiguous_hour, 10)

    def test_unambiguous_time_with_afternoon(self):
        res = parse_time("marca almoço amanhã às 3 da tarde", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(15, 0))

    def test_unambiguous_time_with_morning(self):
        res = parse_time("marca consulta amanhã às 10 da manhã", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(10, 0))

    def test_unambiguous_time_24h_format(self):
        res = parse_time("marca reunião amanhã às 15h", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(15, 0))

    def test_unambiguous_time_with_minutes(self):
        res = parse_time("marca reunião amanhã às 14h30", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(14, 30))

    def test_time_meio_dia(self):
        res = parse_time("marca almoço amanhã ao meio-dia", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(12, 0))

    def test_time_12_da_tarde_equals_12_00(self):
        res = parse_time("marca reunião amanhã às 12 da tarde", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(12, 0))
        self.assertFalse(res.is_12_night)

    def test_time_12_da_noite_equals_00_00_next_day(self):
        res = parse_time("marca reunião amanhã às 12 da noite", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous)
        self.assertEqual(res.time, time(0, 0))
        self.assertTrue(res.is_12_night)

    def test_past_time_today(self):
        # Now is 13:00. Time requested for today is 10:00 -> has passed!
        res = parse_time("marca reunião hoje às 10 da manhã", self.now, target_date=date(2026, 10, 15))
        self.assertTrue(res.is_past)
        self.assertEqual(res.time, time(10, 0))

    def test_future_time_today(self):
        # Now is 13:00. Time requested for today is 16:00 -> not past
        res = parse_time("marca reunião hoje às 16h", self.now, target_date=date(2026, 10, 15))
        self.assertFalse(res.is_past)
        self.assertEqual(res.time, time(16, 0))

    def test_time_in_future_date_not_past(self):
        # Tomorrow at 10:00 is in the future
        res = parse_time("marca reunião amanhã às 10 da manhã", self.now, target_date=date(2026, 10, 16))
        self.assertFalse(res.is_past)
        self.assertEqual(res.time, time(10, 0))

    def test_written_numbers_parse_time(self):
        # Whisper transcription phrases
        res_tres = parse_time("marca dentista amanhã às três", self.now, target_date=date(2026, 10, 16))
        self.assertTrue(res_tres.is_ambiguous)
        self.assertEqual(res_tres.ambiguous_hour, 3)

        res_tarde = parse_time("marca dentista amanhã às três da tarde", self.now, target_date=date(2026, 10, 16))
        self.assertEqual(res_tarde.time, time(15, 0))

        res_standalone_tarde = parse_time("três da tarde", self.now, target_date=date(2026, 10, 16))
        self.assertEqual(res_standalone_tarde.time, time(15, 0))

        res_noite = parse_time("dez e meia da noite", self.now, target_date=date(2026, 10, 16))
        self.assertEqual(res_noite.time, time(22, 30))

        res_quinze = parse_time("quinze horas", self.now, target_date=date(2026, 10, 16))
        self.assertEqual(res_quinze.time, time(15, 0))

        res_vinte_tres = parse_time("vinte e três horas", self.now, target_date=date(2026, 10, 16))
        self.assertEqual(res_vinte_tres.time, time(23, 0))


class TestAgendaParseTitle(unittest.TestCase):
    """Test title cleaning and trigger removal."""

    def test_remove_trigger_and_date_time(self):
        title = parse_title("marca dentista amanhã às 15h", raw_date="amanhã", raw_time="às 15h")
        self.assertEqual(title, "Dentista")

    def test_remove_cria_um_evento(self):
        title = parse_title("cria um evento almoço com diretoria dia 23/10 às 12h", raw_date="dia 23/10", raw_time="às 12h")
        self.assertEqual(title, "Almoço com diretoria")

    def test_remove_chamado_from_title(self):
        # Requirement 3(a): "cria um evento hoje às 20h chamado estudar" => "Estudar"
        title = parse_title("cria um evento hoje às 20h chamado estudar", raw_date="hoje", raw_time="às 20h")
        self.assertEqual(title, "Estudar")

    def test_remove_chamada_and_com_o_nome(self):
        t1 = parse_title("cria um evento amanhã às 10h chamada revisão de código", raw_date="amanhã", raw_time="às 10h")
        self.assertEqual(t1, "Revisão de código")

        t2 = parse_title("marca reunião sexta às 14h com o nome alinhamento semanal", raw_date="sexta", raw_time="às 14h")
        self.assertEqual(t2, "Alinhamento semanal")

        t3 = parse_title("cria compromisso hoje às 19h com o nome de jantar", raw_date="hoje", raw_time="às 19h")
        self.assertEqual(t3, "Jantar")

    def test_reuniao_title_preserved(self):
        title = parse_title("marca reunião amanhã às 15h", raw_date="amanhã", raw_time="às 15h")
        self.assertEqual(title, "Reunião")

    def test_empty_title_when_only_triggers(self):
        title = parse_title("marca amanhã às 15h", raw_date="amanhã", raw_time="às 15h")
        self.assertEqual(title, "")

    def test_title_length_limit(self):
        long_text = "marca " + "a" * 150 + " amanhã às 15h"
        title = parse_title(long_text, raw_date="amanhã", raw_time="às 15h")
        self.assertLessEqual(len(title), 100)


class TestConfirmationAndPayload(unittest.TestCase):
    """Test confirmation formatting and payload building."""

    def test_format_confirmation_prompt(self):
        dt = datetime(2026, 10, 23, 15, 0, tzinfo=_TZ)
        prompt = format_confirmation_prompt("Dentista", dt)
        self.assertEqual(prompt, "Marcar Dentista para sexta, 23/10, 15h? Confirma?")

    def test_format_confirmation_prompt_with_minutes(self):
        dt = datetime(2026, 10, 23, 15, 30, tzinfo=_TZ)
        prompt = format_confirmation_prompt("Dentista", dt)
        self.assertEqual(prompt, "Marcar Dentista para sexta, 23/10, 15h30? Confirma?")

    def test_build_event_payload_includes_10_min_popup_reminder(self):
        # Requirement 2: payload includes 10-minute popup reminder
        dt = datetime(2026, 10, 23, 15, 0, tzinfo=_TZ)
        payload = build_event_payload("Dentista", dt, duration_minutes=60)
        self.assertEqual(payload["summary"], "Dentista")
        self.assertEqual(payload["start"]["dateTime"], "2026-10-23T15:00:00-03:00")
        self.assertEqual(payload["end"]["dateTime"], "2026-10-23T16:00:00-03:00")
        self.assertIn("reminders", payload)
        self.assertFalse(payload["reminders"]["useDefault"])
        self.assertEqual(
            payload["reminders"]["overrides"],
            [{"method": "popup", "minutes": 10}],
        )


class TestParseCreateEventIntegration(unittest.TestCase):
    """Integration of parse_create_event."""

    def setUp(self):
        self.now = datetime(2026, 10, 15, 13, 0, tzinfo=_TZ)

    def test_complete_valid_request(self):
        res = parse_create_event("marca dentista amanhã às 15h", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Dentista")
        self.assertEqual(res.target_date, date(2026, 10, 16))
        self.assertEqual(res.target_time, time(15, 0))
        self.assertFalse(res.missing_title)
        self.assertFalse(res.is_ambiguous_time)
        self.assertFalse(res.is_past_time)

    def test_cria_evento_chamado_estudar_integration(self):
        # Requirement 3(a): "cria um evento hoje às 20h chamado estudar" => "Estudar"
        res = parse_create_event("cria um evento hoje às 20h chamado estudar", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Estudar")
        self.assertEqual(res.target_date, date(2026, 10, 15))
        self.assertEqual(res.target_time, time(20, 0))

    def test_12_da_noite_advances_day_and_sets_00_00(self):
        # Requirement 3(b): "12 da noite" = 00:00 do dia seguinte
        # Requested for today (2026-10-15) -> becomes 2026-10-16 00:00
        res = parse_create_event("cria um evento hoje às 12 da noite chamado vigília", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Vigília")
        self.assertEqual(res.target_date, date(2026, 10, 16))
        self.assertEqual(res.target_time, time(0, 0))
        self.assertEqual(res.target_dt, datetime(2026, 10, 16, 0, 0, tzinfo=_TZ))

    def test_12_da_tarde_keeps_same_day_at_12_00(self):
        # Requirement 3(b): "12 da tarde" = 12:00
        # Requested for tomorrow (2026-10-16) -> 2026-10-16 12:00
        res = parse_create_event("cria um evento amanhã às 12 da tarde chamado almoço", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Almoço")
        self.assertEqual(res.target_date, date(2026, 10, 16))
        self.assertEqual(res.target_time, time(12, 0))
        self.assertEqual(res.target_dt, datetime(2026, 10, 16, 12, 0, tzinfo=_TZ))

    def test_ambiguous_request(self):
        res = parse_create_event("marca dentista amanhã às 3", now=self.now)
        self.assertTrue(res.is_create)
        self.assertTrue(res.is_ambiguous_time)
        self.assertEqual(res.ambiguous_hour, 3)

    def test_past_time_request(self):
        res = parse_create_event("marca café hoje às 10 da manhã", now=self.now)
        self.assertTrue(res.is_create)
        self.assertTrue(res.is_past_time)

    def test_missing_title_request(self):
        res = parse_create_event("marca amanhã às 15h", now=self.now)
        self.assertTrue(res.is_create)
        self.assertTrue(res.missing_title)

    def test_written_numbers_marca_dentista_amanha_as_tres(self):
        # Requirement 1: "marca dentista amanhã às três" -> hora ambígua
        res = parse_create_event("marca dentista amanhã às três", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Dentista")
        self.assertEqual(res.target_date, date(2026, 10, 16))
        self.assertTrue(res.is_ambiguous_time)
        self.assertEqual(res.ambiguous_hour, 3)
        self.assertIsNone(res.target_time)

    def test_written_numbers_as_tres_da_tarde(self):
        # Requirement 1: "marca dentista amanhã às três da tarde" -> 15:00
        res = parse_create_event("marca dentista amanhã às três da tarde", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Dentista")
        self.assertEqual(res.target_date, date(2026, 10, 16))
        self.assertFalse(res.is_ambiguous_time)
        self.assertEqual(res.target_time, time(15, 0))
        self.assertEqual(res.target_dt, datetime(2026, 10, 16, 15, 0, tzinfo=_TZ))

    def test_written_numbers_dez_e_meia_da_noite(self):
        res = parse_create_event("marca dentista amanhã às dez e meia da noite", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Dentista")
        self.assertFalse(res.is_ambiguous_time)
        self.assertEqual(res.target_time, time(22, 30))

    def test_written_numbers_quinze_horas(self):
        res = parse_create_event("marca dentista amanhã quinze horas", now=self.now)
        self.assertTrue(res.is_create)
        self.assertEqual(res.title, "Dentista")
        self.assertFalse(res.is_ambiguous_time)
        self.assertEqual(res.target_time, time(15, 0))


if __name__ == "__main__":
    unittest.main()
