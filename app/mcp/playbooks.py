"""Guia "como fazer" do MCP: o passo a passo de cada assunto do OrkaFlow para a IA.

Cada assunto diz quais rotas usar e em que ordem. Os campos exatos de cada rota a IA
pega em detalhe_rota; a execução é por chamar_api (ou pelas ferramentas específicas).
"""

GERAL = """\
O OrkaFlow é o orquestrador de robôs RPA. Hierarquia:
Repositório (área) > Bot (o código, num Git) > Versão do bot > Automação (o bot configurado para um fim)
> Task (cada execução). Máquinas (runners) executam as tasks; uma automação só roda nas máquinas vinculadas a ela.
Agendamentos criam tasks sozinhos. Variáveis de ambiente e credenciais são entregues ao robô na execução.

Como trabalhar:
1. Para consultas do dia a dia prefira as ferramentas prontas (resumo_do_dia, ultimas_execucoes, detalhe_task,
   listar_maquinas, status_maquina, listar_agendamentos...).
2. Para cadastrar, alterar ou qualquer coisa que não tenha ferramenta pronta: como_fazer(assunto) para o roteiro,
   buscar_rotas para achar a rota, detalhe_rota para ver campos obrigatórios e exemplo, chamar_api para executar.
3. Descubra ids antes (listas com GET). Nunca invente id.
4. Antes de qualquer alteração (POST/PUT/PATCH/DELETE) mostre ao usuário o que vai ser enviado e espere ele confirmar.
   DELETE de bot, versão, variável e item de credencial é definitivo: prefira desativar quando existir a opção.
5. Se chamar_api devolver erro 400/404/409, leia o "detail": ele diz o que corrigir.
6. Horários: as rotas devolvem UTC (ISO 8601); ao mostrar ao usuário converta para Brasília (UTC-3).
7. Valores de credenciais nunca são mostrados (só prévia mascarada) e não devem ser pedidos de volta ao usuário.

Assuntos do como_fazer: operacao, bots_e_versoes, automacoes, maquinas, agendamentos, variaveis, credenciais,
notificacoes, repositorios, consultas.
"""

PLAYBOOKS: dict[str, str] = {
    "operacao": """\
Operação do dia a dia (menu Operação):
- Situação geral: resumo_do_dia; saúde por automação: GET /api/v1/automation-health/ (semáforo, atraso);
  indicadores: GET /api/v1/dashboard/overview, /dashboard/runners, /dashboard/bots (parâmetro period; valores em detalhe_rota).
- Última execução de cada automação: ultimas_execucoes.
- Tasks: listar_tasks (filtros) ou GET /api/v1/tasks/ (filtros status/statuses, automation_id, runner_id, created_by, skip/limit).
- Detalhe e erro de uma task: detalhe_task. Erros de todas as tasks: GET /api/v1/task-errors (q = texto,
  start_date/end_date, automation_id, error_type). Logs completos: GET /api/v1/task-logs/task/{task_id}?limit=500.
- Rodar agora: criar_task (usa os parâmetros padrão; 'parametros' sobrescreve). Só existe uma task aberta por
  automação: se já houver, o erro diz qual.
- Parar: parar_task (parada gentil; na fila cancela). Parada forçada: POST /api/v1/tasks/{id}/force-stop (só se a
  gentil não resolver; marca forced_stop na hora). Cancelar task agendada/na fila: POST /api/v1/tasks/{id}/cancel.
- Log bruto da máquina (worker e saída dos robôs): GET /api/v1/runner-logs/?runner_id=ID (aceita task_id, level, search).
""",
    "bots_e_versoes": """\
Bots e versões (menu Automação):
1. Repositório (área) do bot: GET /api/v1/repositories/ (crie com POST se não existir; veja assunto repositorios).
2. Criar o bot: POST /api/v1/bots/ com name, repository_id, technology (python), source_type (git), source_url
   (URL do Git), entrypoint (ex.: main.py), execution_mode (background = sem tela, pode paralelo; foreground = usa a
   tela, 1 por máquina), timeout_default (segundos) e initial_version (ex.: 1.0.0). Cria junto a primeira versão.
3. Alterar bot (descrição, timeout, entrypoint, URL, ativo): PUT /api/v1/bots/{bot_id} (só os campos que mudam).
4. Nova versão a partir do Git: verificar_versao_bot e criar_versao_bot (já fazem tudo). Manualmente:
   GET /api/v1/bot-versions/git-preview?bot_id=ID e depois POST /api/v1/bot-versions/ com os dados sugeridos.
   Versão nova passa a ser a executada.
5. Voltar para uma versão anterior (rollback) ou fixar: POST /api/v1/bot-versions/{bot_version_id}/release.
6. Desativar bot: PUT /api/v1/bots/{id} com active=false (DELETE apaga de vez e falha se houver histórico).
""",
    "automacoes": """\
Automações (menu Automação):
1. Ter o bot (assunto bots_e_versoes) e saber repository_id e bot_id (o bot precisa ser do mesmo repositório).
2. Criar: POST /api/v1/automations/ com name (único no repositório), bot_id, repository_id, default_priority (1-10),
   opcionais: label, description, default_parameters_json, default_runtime_parameters_json,
   exclusive_group_ids (só uma task por vez no grupo), success_trigger_automation_ids (dispara outras ao terminar bem).
3. Vincular máquinas (obrigatório, sem isso nada roda): POST /api/v1/automations/{id}/runners com {"runner_id": X}.
   Ver vínculos: GET /api/v1/automations/{id}/runners. Desvincular: DELETE /api/v1/automations/{id}/runners/{link_id}.
4. Parâmetros declarados (aparecem na Nova Task): GET/POST /api/v1/automations/{id}/parameters
   (type string/integer/float/boolean/datetime/json/select/secret_ref; select exige allowed_values).
5. Alterar: PUT /api/v1/automations/{id}. Ativar/desativar: POST /api/v1/automations/{id}/activate ou /deactivate.
6. Grupos exclusivos: GET/POST /api/v1/automations/exclusive-groups/ (capacity sempre 1).
7. Agendar: assunto agendamentos. Variáveis: assunto variaveis.
""",
    "maquinas": """\
Máquinas / runners (menu Execução):
- Listar e status: listar_maquinas / status_maquina, ou GET /api/v1/runners/ e GET /api/v1/runners/overview.
- Painel completo de uma máquina: GET /api/v1/runners/{runner_id}/overview.
- Renomear/rótulo/ativar/desativar: PUT /api/v1/runners/{runner_id} (ex.: {"label": "RPA 14", "enabled": true}).
- Configuração de execução: GET/PUT /api/v1/runners/{runner_id}/config (max_concurrency 1-5, polling_interval >= 5).
  O worker aplica na próxima sincronização.
- Quais automações rodam nela: vínculos ficam na automação (assunto automacoes, passo 3).
- Remover máquina antiga do painel: DELETE /api/v1/runners/{runner_id} (só faz sentido para máquina desligada).
- Máquinas novas se cadastram sozinhas quando o worker é instalado; não crie runner manualmente.
""",
    "agendamentos": """\
Agendamentos (menu Automação):
- Listar: listar_agendamentos ou GET /api/v1/schedules/ (filtros automation_id, active, status).
- Criar: POST /api/v1/schedules/ com name (único na automação), automation_id, timezone "America/Sao_Paulo",
  priority, policy e o tipo:
  * schedule_type "cron" + cron_expression (5 campos: minuto hora dia mês dia-da-semana; ex.: "0 6 * * 1-5" =
    dias úteis às 06:00; "*/30 7-18 * * *" = a cada 30 min das 7h às 18h).
  * schedule_type "calendar" + calendar_type (once, second, minute, hour, day, week, month) e, nos recorrentes,
    interval_value > 0 (ex.: hour + 2 = a cada 2 horas).
  policy: create_always, ignore_if_running (padrão recomendado), enqueue_if_none_pending, run_if_missed, skip_if_missed.
  Parâmetros de execução: runtime_parameters_json; use_default_runtime_parameters mistura com os padrões da automação.
- Alterar: PUT /api/v1/schedules/{id}. Pausar/reativar: pausar_agendamento / reativar_agendamento.
  Desativar de vez: POST /api/v1/schedules/{id}/deactivate.
- Confira next_run_at na resposta para validar o horário.
""",
    "variaveis": """\
Variáveis de ambiente dos robôs (menu Automação > Variáveis; exige administrador):
- Escopos (o mais específico vence): global < bot < automation < runner. scope_id é o id do alvo (não no global).
- Listar: GET /api/v1/env-variables/ (filtros scope_type, scope_id, search). Valor final que o robô recebe:
  GET /api/v1/env-variables/effective?automation_id=ID&runner_id=ID.
- Criar: POST /api/v1/env-variables/ com name (MAIÚSCULAS, letras/números/_; sem prefixo ORKAFLOW_ nem PATH/TEMP),
  scope_type, scope_id, value, is_secret (true criptografa), description.
- Várias de uma vez (conteúdo de um .env): POST /api/v1/env-variables/import.
- Alterar: PUT /api/v1/env-variables/{var_id}. Apagar: DELETE (definitivo).
""",
    "credenciais": """\
Credenciais (menu Segurança): cofre de usuários/senhas/tokens que os robôs usam.
- Listar: GET /api/v1/credentials/. Detalhe com itens mascarados: GET /api/v1/credentials/{id}.
- Criar: POST /api/v1/credentials/ com repository_id e label (único) — é só o agrupador.
- Itens (os valores): POST /api/v1/credentials/{id}/items com key (ex.: usuario, senha), value_type
  (string, password, token, json, secret) e value. O valor é criptografado.
- Alterar item: PUT /api/v1/credentials/{id}/items/{item_id}. Apagar item: DELETE (definitivo).
- Desativar credencial: DELETE /api/v1/credentials/{id} (exclusão lógica) ou PUT com active=false.
- O valor real NUNCA é exibido por este MCP. Peça ao usuário o valor só para gravar, e não repita o valor na resposta.
""",
    "notificacoes": """\
Notificações de falha (menu Integração > Notificações; exige administrador):
- Quando um agendamento falha N vezes seguidas, o sistema chama uma URL (ex.: abrir chamado) e pode pausar o agendamento.
- Ver configuração: GET /api/v1/notifications/channel. Variáveis dos modelos: GET /api/v1/notifications/variables.
- Alterar: PUT /api/v1/notifications/channel (parcial; headers e pre_steps enviados substituem os atuais).
- Testar: POST /api/v1/notifications/channel/test. Histórico: GET /api/v1/notifications/logs.
""",
    "repositorios": """\
Repositórios (áreas que agrupam bots, automações e credenciais):
- Listar: GET /api/v1/repositories/. Criar: POST /api/v1/repositories/ com name (único) e description.
- Alterar: PUT /api/v1/repositories/{id}. Desativar: DELETE /api/v1/repositories/{id} (lógico).
""",
    "consultas": """\
Consultas úteis:
- Saúde das automações: GET /api/v1/automation-health/.
- Indicadores do período: GET /api/v1/dashboard/overview (parâmetro period; veja detalhe_rota).
- Erros recentes com contexto: GET /api/v1/task-errors?q=texto.
- Usuários e perfis (somente leitura por aqui): GET /api/v1/users/, GET /api/v1/profiles/.
""",
}


def como_fazer(assunto: str | None) -> dict:
    key = (assunto or "").strip().lower().replace(" ", "_")
    if not key or key in ("geral", "visao_geral", "inicio"):
        return {"assunto": "geral", "guia": GERAL, "assuntos": sorted(PLAYBOOKS)}
    if key not in PLAYBOOKS:
        return {"erro": f"Assunto '{assunto}' não existe.", "assuntos": sorted(PLAYBOOKS)}
    return {"assunto": key, "guia": PLAYBOOKS[key]}
