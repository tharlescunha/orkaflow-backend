# app/workers/scheduler_main.py
"""DEPRECATED.

Este módulo antes rodava scheduler engine + watchdog em um loop próprio, duplicando
o que ``app.workers.main`` já executa (processaria schedules/watchdog em dobro se os
dois fossem iniciados). Entrypoint único recomendado:

    python -m app.workers.main

``python -m app.workers.scheduler_main`` agora apenas delega a ``run_all_workers``.
"""
import warnings


def run():
    warnings.warn(
        "app.workers.scheduler_main está deprecated; use `python -m app.workers.main`.",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.workers.main import run_all_workers

    run_all_workers()


if __name__ == "__main__":
    run()
