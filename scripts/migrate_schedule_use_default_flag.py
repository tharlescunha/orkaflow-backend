"""
Define a flag use_default_runtime_parameters em cada agendamento:
- True  -> agendamento não tem runtime_parameters_json próprio (usa o da automação)
- False -> agendamento tem parâmetros próprios diferentes dos da automação

Uso:
    cd orkaflow-backend
    python scripts/migrate_schedule_use_default_flag.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.schedule import Schedule
from app.models.automation import Automation


def params_equal(a, b) -> bool:
    """Compara dois valores JSON independente de ordenação."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def run() -> None:
    db = SessionLocal()
    try:
        schedules: list[Schedule] = db.query(Schedule).all()

        set_true = 0
        set_false = 0

        for schedule in schedules:
            automation: Automation | None = (
                db.query(Automation).filter(Automation.id == schedule.automation_id).first()
            )

            schedule_runtime = getattr(schedule, "runtime_parameters_json", None)
            automation_runtime = getattr(automation, "default_runtime_parameters_json", None) if automation else None

            # Sem parâmetros próprios OU idêntico ao da automação -> usa default
            if not schedule_runtime or params_equal(schedule_runtime, automation_runtime):
                schedule.use_default_runtime_parameters = True
                set_true += 1
                print(f"  [TRUE]  Schedule #{schedule.id} '{schedule.name}' -> usa default da automação")
            else:
                schedule.use_default_runtime_parameters = False
                set_false += 1
                print(f"  [FALSE] Schedule #{schedule.id} '{schedule.name}' -> mantém parâmetros próprios")

            db.add(schedule)

        db.commit()
        print(f"\nConcluído: {set_true} usando default, {set_false} com parâmetros próprios.")

    except Exception as exc:
        db.rollback()
        print(f"\n[ERRO] Rollback realizado. Causa: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Definindo flag use_default_runtime_parameters nos agendamentos...\n")
    run()
