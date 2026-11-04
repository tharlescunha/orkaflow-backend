"""Out/2026: carga por hora do dia (Brasília) no Dashboard, geral e por máquina."""
import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.enums import TaskStatus
from app.services.dashboard_service import DashboardService

from tests.test_concurrency_watchdog import Fixture

BRT = ZoneInfo("America/Sao_Paulo")


def ontem_as(hour: int, minute: int = 0) -> datetime:
    local = (datetime.now(BRT) - timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(UTC)


class HourlyLoadTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.r1 = self.f.runner("r1", host="H1")
        self.r2 = self.f.runner("r2", host="H2")
        self.auto, self.ver = self.f.automation(runners=[self.r1, self.r2])
        self.f.db.commit()
        self.svc = DashboardService(self.f.db)

    def _task(self, runner, start, minutes, status=TaskStatus.FINISHED):
        end = start + timedelta(minutes=minutes) if status == TaskStatus.FINISHED else None
        self.f.task(self.auto, self.ver, status, runner=runner, started_at=start, finished_at=end)
        self.f.db.commit()

    def test_hora_e_em_brasilia_e_minutos_dividem_entre_as_horas(self):
        # 14:50 a 15:20 (Brasília): 10 min na hora 14 e 20 min na hora 15.
        self._task(self.r1, ontem_as(14, 50), 30)
        data = self.svc.get_hourly_load(period="7d")

        h14, h15 = data.hours[14], data.hours[15]
        self.assertEqual((h14.tasks, h15.tasks), (1, 0))
        self.assertAlmostEqual(h14.avg_busy_minutes, round(10 / 7, 1))
        self.assertAlmostEqual(h15.avg_busy_minutes, round(20 / 7, 1))
        self.assertEqual(sum(h.tasks for h in data.hours), 1)
        self.assertEqual(data.days, 7)

    def test_por_maquina_e_geral_somam(self):
        self._task(self.r1, ontem_as(9, 0), 10)
        self._task(self.r2, ontem_as(9, 5), 10)
        self._task(self.r2, ontem_as(20, 0), 10)
        data = self.svc.get_hourly_load(period="7d")

        self.assertEqual(data.hours[9].tasks, 2)
        porta = {r.name: r for r in data.runners}
        self.assertEqual(porta["r1"].total_tasks, 1)
        self.assertEqual(porta["r2"].total_tasks, 2)
        self.assertEqual(porta["r2"].hours[20].tasks, 1)
        # Simultâneas na mesma hora passam de 60 min no geral só se somar além de uma hora; aqui são 20 min.
        self.assertAlmostEqual(data.hours[9].avg_busy_minutes, round(20 / 7, 1))

    def test_maquina_sem_tasks_aparece_zerada_para_achar_janela_livre(self):
        self._task(self.r1, ontem_as(9, 0), 10)
        data = self.svc.get_hourly_load(period="7d")
        vazia = next(r for r in data.runners if r.name == "r2")
        self.assertEqual(vazia.total_tasks, 0)
        self.assertEqual(len(vazia.hours), 24)
        self.assertTrue(all(h.tasks == 0 and h.avg_busy_minutes == 0 for h in vazia.hours))

    def test_filtro_por_maquina(self):
        self._task(self.r1, ontem_as(9, 0), 10)
        self._task(self.r2, ontem_as(10, 0), 10)
        data = self.svc.get_hourly_load(period="7d", runner_id=self.r2.id)
        self.assertEqual([r.name for r in data.runners], ["r2"])
        self.assertEqual(sum(h.tasks for h in data.hours), 1)

    def test_task_fora_do_periodo_nao_conta(self):
        antiga = datetime.now(UTC) - timedelta(days=40)
        self._task(self.r1, antiga, 10)
        data = self.svc.get_hourly_load(period="30d")
        self.assertEqual(sum(h.tasks for h in data.hours), 0)

    def test_task_presa_rodando_por_dias_nao_infla_todas_as_horas(self):
        self._task(self.r1, datetime.now(UTC) - timedelta(days=3), 0, status=TaskStatus.RUNNING)
        data = self.svc.get_hourly_load(period="7d")
        total_minutos = sum(h.avg_busy_minutes for h in data.hours) * data.days
        self.assertLessEqual(total_minutos, 24 * 60 + 10)  # folga: arredondamento por hora

    # ---------------------------------------------------------------- 24 h: janela deslizante como o gráfico do topo
    def test_24h_e_cronologico_de_ontem_nesta_hora_ate_agora(self):
        agora = datetime.now(UTC)
        self._task(self.r1, agora - timedelta(hours=2), 20)
        self._task(self.r1, agora - timedelta(hours=23, minutes=30), 10)
        data = self.svc.get_hourly_load(period="1d")

        agora_local = agora.astimezone(BRT)
        titulos = [h.title for h in data.hours]
        # Primeira barra é a hora de 24 h atrás (ontem) e a última é a hora atual (hoje).
        self.assertTrue(titulos[0].startswith("ontem"))
        self.assertEqual(titulos[-1], f"hoje {agora_local.hour:02d}h")
        self.assertIn(len(data.hours), (24, 25))
        # Mesma ordem do gráfico de execuções do topo: horas reais seguidas, sem repetir chave.
        self.assertEqual(len({h.key for h in data.hours}), len(data.hours))
        self.assertEqual(sum(h.tasks for h in data.hours), 2)
        self.assertEqual(data.days, 1)

    def test_24h_hora_repetida_nas_pontas_nao_se_mistura(self):
        agora = datetime.now(UTC)
        self._task(self.r1, agora - timedelta(minutes=5), 1)
        data = self.svc.get_hourly_load(period="1d")
        agora_local = agora.astimezone(BRT)
        mesma_hora = [h for h in data.hours if h.hour == agora_local.hour]
        # A hora de agora aparece ontem (ponta parcial) e hoje, em barras separadas.
        self.assertEqual(len(mesma_hora), 2 if agora_local.minute > 0 or len(data.hours) == 25 else 1)
        self.assertEqual(sum(h.tasks for h in mesma_hora), 1)
        self.assertEqual(data.hours[-1].tasks, 1)

    def test_24h_por_maquina_usa_as_mesmas_barras(self):
        agora = datetime.now(UTC)
        self._task(self.r2, agora - timedelta(hours=5), 15)
        data = self.svc.get_hourly_load(period="1d")
        r2 = next(r for r in data.runners if r.name == "r2")
        self.assertEqual([h.key for h in r2.hours], [h.key for h in data.hours])
        self.assertEqual(sum(h.tasks for h in r2.hours), 1)

    def test_7d_continua_por_hora_do_dia(self):
        self._task(self.r1, ontem_as(9, 0), 10)
        data = self.svc.get_hourly_load(period="7d")
        self.assertEqual(len(data.hours), 24)
        self.assertEqual([h.title for h in data.hours][:2], ["00h", "01h"])


if __name__ == "__main__":
    unittest.main()
