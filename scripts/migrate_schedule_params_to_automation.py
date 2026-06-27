"""
Migra parameters_json e runtime_parameters_json dos agendamentos
para os campos default_* da automação correspondente.

Regra:
- Para cada automação, percorre seus agendamentos (priorizando os ativos).
- Se a automação ainda não tem o campo preenchido, copia do agendamento.
- Nunca sobrescreve um campo que já foi preenchido na automação.

Uso:
    cd orkaflow-backend
    python scripts/migrate_schedule_params_to_automation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.automation import Automation
from app.models.schedule import Schedule


def pick_value_from_schedules(schedules: list[Schedule], field: str):
    """Retorna o primeiro valor não-nulo do campo, priorizando agendamentos ativos."""
    for schedule in sorted(schedules, key=lambda s: (not s.active, s.id)):
        value = getattr(schedule, field, None)
        if value is not None:
            return value
    return None


def run() -> None:
    db = SessionLocal()
    try:
        automations: list[Automation] = db.query(Automation).all()

        updated = 0
        skipped = 0

        for automation in automations:
            schedules: list[Schedule] = (
                db.query(Schedule)
                .filter(Schedule.automation_id == automation.id)
                .all()
            )

            if not schedules:
                skipped += 1
                continue

            changed = False

            if automation.default_parameters_json is None:
                value = pick_value_from_schedules(schedules, "parameters_json")
                if value is not None:
                    automation.default_parameters_json = value
                    changed = True

            if automation.default_runtime_parameters_json is None:
                value = pick_value_from_schedules(schedules, "runtime_parameters_json")
                if value is not None:
                    automation.default_runtime_parameters_json = value
                    changed = True

            if changed:
                db.add(automation)
                updated += 1
                print(
                    f"  [OK] Automação #{automation.id} '{automation.name}' atualizada."
                )
            else:
                skipped += 1

        db.commit()
        print(f"\nConcluído: {updated} automação(ões) atualizadas, {skipped} sem alteração.")

    except Exception as exc:
        db.rollback()
        print(f"\n[ERRO] Rollback realizado. Causa: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Iniciando migração de parâmetros dos agendamentos para as automações...\n")
    run()
