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

8. **Robô novo sempre usa a biblioteca Maestro** (assunto maestro). Ao ajudar alguém a criar um bot para o
   orquestrador, gere o main.py com `from maestro import Maestro`, `with maestro:` e `maestro.success/fail`,
   e cadastre o bot com reads_task_file_arg=false. Nunca proponha o jeito antigo (JSON por argumento,
   print e sys.exit) para robô novo; ele existe só para os robôs que já estão rodando.

Assuntos do como_fazer: operacao, bots_e_versoes, automacoes, maquinas, agendamentos, variaveis, credenciais,
notificacoes, repositorios, consultas, maestro, novidades.
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
- Ver a tela: print_do_erro(task_id) mostra a imagem do momento do erro; tela_da_maquina(maquina) mostra o
  último print da máquina (enquanto roda task). As duas devolvem a imagem para a IA enxergar.
- Acompanhar uma task: progress_current/progress_total/progress_text (etapa que o robô informou pelo Maestro),
  anexos em GET /api/v1/tasks/{id}/attachments (download em /attachments/{att_id}/download), print do erro em
  error_screenshot_base64 de GET /api/v1/task-errors/task/{id}.
- Task parada na fila (waiting): o campo waiting_reason do detalhe explica (task da mesma automação aberta,
  grupo exclusivo ocupado ou nenhum runner elegível). Encadeamento: parent_task_id (quem originou; execution_mode
  trigger = gatilho de sucesso, retry = retentativa) e children (tasks que ela originou).
- Parar: parar_task (parada gentil; na fila cancela). Parada forçada: POST /api/v1/tasks/{id}/force-stop (só se a
  gentil não resolver; marca forced_stop na hora). Cancelar task agendada/na fila: POST /api/v1/tasks/{id}/cancel.
- Log bruto da máquina (worker e saída dos robôs): GET /api/v1/runner-logs/?runner_id=ID (aceita task_id, level, search).
""",
    "bots_e_versoes": """\
Bots e versões (menu Automação):
1. Repositório (área) do bot: GET /api/v1/repositories/ (crie com POST se não existir; veja assunto repositorios).
2. Conferir o link do Git primeiro: POST /api/v1/bots/inspect-source com source_url (valida o acesso e traz
   name, description e suggested_version). Depois criar o bot: POST /api/v1/bots/ com name, repository_id,
   technology (python), source_type (git), source_url
   (URL do Git), entrypoint (ex.: main.py), execution_mode (background = sem tela, pode paralelo; foreground = usa a
   tela, 1 por máquina), timeout_default (segundos), initial_version (ex.: 1.0.0) e reads_task_file_arg=false
   (robô novo usa o Maestro e não lê o JSON por argumento; só robô antigo fica true). Cria junto a primeira versão.
   Padrão obrigatório para robô novo: main.py com a biblioteca Maestro (assunto maestro).
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
6. Grupos exclusivos (automações que não rodam juntas, mesmo em máquinas diferentes): GET/POST
   /api/v1/automations/exclusive-groups/ e GET/PUT/DELETE /exclusive-groups/{id}. A lista traz automations
   (membros) e current_lock (task que está segurando o grupo agora). PUT com automation_ids substitui os membros;
   active=false desativa sem derrubar nada. DELETE só sem membros. capacity sempre 1.
7. Agendar: assunto agendamentos. Variáveis: assunto variaveis.
""",
    "maquinas": """\
Máquinas / runners (menu Execução):
- Listar e status: listar_maquinas / status_maquina, ou GET /api/v1/runners/ e GET /api/v1/runners/overview.
- Painel completo de uma máquina: GET /api/v1/runners/{runner_id}/overview.
- Renomear/rótulo/ativar/desativar: PUT /api/v1/runners/{runner_id} (ex.: {"label": "RPA 14", "enabled": true}).
  Usuário de acesso da máquina: login_user (cadastrado); os_user é o usuário do Windows em que o worker roda.
- Configuração de execução: GET/PUT /api/v1/runners/{runner_id}/config (max_concurrency 1-5, polling_interval >= 5).
  O worker aplica na próxima sincronização.
- Quais automações rodam nela: vínculos ficam na automação (assunto automacoes, passo 3).
- Remover máquina antiga do painel: DELETE /api/v1/runners/{runner_id} (só faz sentido para máquina desligada).
- Máquinas novas se cadastram sozinhas quando o worker é instalado; não crie runner manualmente.
- Manutenção: PUT /api/v1/runners/{id}/config com maintenance_mode=true (ou PUT /runners/{id} com
  status "maintenance"). A máquina deixa de receber tasks novas, as que estavam na fila dela voltam para
  outra máquina na hora, e a task em execução termina normalmente. maintenance_mode=false libera.
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
  N-ésimo dia útil do mês: business_day_of_month (1-23) + time_of_day "HH:MM" com schedule_type "calendar"
  (dias úteis/feriados do calendar_id; sem calendário, segunda a sexta).
  Calendário de dias úteis: calendar_id (GET /api/v1/calendars/) e calendar_policy ("defer" adia para o próximo
  horário permitido no mesmo horário; "skip" pula e anota em last_skipped_reason). Calendários: menu
  Administração; POST /api/v1/calendars/ com weekdays (0=segunda..6=domingo), holidays (AAAA-MM-DD) e blackouts
  (janelas HH:MM); POST /api/v1/calendars/{id}/holidays/import com year importa os feriados nacionais.
  Retentativa automática (por agendamento, não por automação): retry_max (0-5), retry_delay_seconds, retry_on
  ["erro","timeout"]. Tentativas × espera precisa caber no intervalo do agendamento. Credencial inválida,
  cancelada e parada forçada nunca repetem.
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
Eventos (menu Integração → Eventos): regras "Quando → Então" por robô. Quando = automação/bot/qualquer +
(scope_ids aceita vários bots ou automações na mesma regra, ex.: os 4 bots de um projeto) +
gatilho (task_error, task_success, task_timeout, credential_invalid, result_contains chave/valor, exit_code N).
Então = etapas prévias (ex.: login que guarda {{token}}) + requisição principal com {{variáveis}}
(automacao, task_id, erro, retorno.campo, credencial, motivo, link_task...). Exemplo: avisar no Teams via
Power Automate quando a credencial do SAP vencer. Rotas: GET/POST /api/v1/events/rules, PUT/DELETE
/api/v1/events/rules/{id}, POST /api/v1/events/rules/{id}/test, GET /api/v1/events/runs. A notificação de
"N falhas seguidas pausa o agendamento e abre chamado" continua separada, em /api/v1/notifications/channel.

Credenciais (menu Segurança): cofre de usuários/senhas/tokens que os robôs usam.
Saúde: cada credencial tem `status` (valida | nao_verificada | invalida | senha_incorreta | senha_expirada |
usuario_bloqueado), `status_reason` e `status_task_id`. Quando um robô avisa que a senha não serve, a credencial
fica inválida, os agendamentos das automações que a usam são pausados (paused_reason=credencial_invalida) e
tasks novas são recusadas com 409. Trocar um item (PUT /credentials/{id}/items/{item_id}) volta para
nao_verificada e reativa esses agendamentos; a próxima task com sucesso marca valida.
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
- Alterar: PUT /api/v1/repositories/{id}. Desativar: DELETE /api/v1/repositories/{id} (lógico): desativa
  junto todos os bots e automações do repositório. Reativar o repositório não reativa os bots/automações.
""",
    "maestro": """\
Maestro: a biblioteca que o robô importa para conversar com o orquestrador. É o padrão para TODO robô novo.
Nada a instalar nas máquinas (o worker coloca o pacote no venv de cada bot). Na máquina do desenvolvedor:
pip install git+https://github.com/tharlescunha/maestro.git ; python -m maestro init cria um task.json de exemplo.
Esqueleto do main.py (gere assim quando alguém pedir um robô novo):
    from maestro import Maestro, CredencialInvalida
    maestro = Maestro()                      # producao=True por padrão; producao=False na máquina do dev
    def main():
        filial = maestro.param("filial", default="010")   # parâmetro da automação
        senha = maestro.credential("sap_senha")           # credencial cadastrada (nunca imprima)
        maestro.step(1, 2, "Login")                       # etapa: aparece na lista e no detalhe da task
        maestro.info("Lendo pedidos", total=120)          # log; warning()/error() idem
        maestro.attach("C:/saida/pedidos.xlsx", "Pedidos") # anexo na task (5 MB, 10 por task)
        maestro.next_automation("Aprovacao_Pedidos")      # outra automação entra na fila ao terminar bem
        maestro.success("120 pedidos", result={"pedidos": 120}, items_processed=120)
    if __name__ == "__main__":
        with maestro:                                     # exceção vira erro na task com traceback
            main()
Senha vencida/usuário bloqueado: raise CredencialInvalida("sap_senha", motivo="senha_expirada", mensagem=...) —
o orquestrador pausa os agendamentos e bloqueia tasks novas. Robô de tela: Maestro(screenshot_on_error=True).
Outras chamadas: require, params, env, heartbeat (laços longos sem log), timer, screenshot, fail(category
business|system). Cadastro do bot: reads_task_file_arg=false. Guia completo com exemplos: tela Execução →
Guia do Bot. Robôs antigos (JSON por argumento, print, sys.exit) continuam funcionando sem mudar nada.
""",
    "novidades": """\
O que entrou em outubro/2026 (tudo já em produção):
- Saúde de credenciais: status na credencial, robô avisa senha vencida, agendamentos pausam, 409 em task nova.
- Eventos (Integração → Eventos): regras "Quando → Então" por robô com requisições HTTP (ex.: Teams).
- Retentativa automática por agendamento (retry_max, retry_delay_seconds, retry_on).
- Calendários (dias úteis, feriados, janelas) no agendamento, e "N-ésimo dia útil do mês".
- Fila com explicação: waiting_reason na task; encadeamento visível (parent_task_id, children, execution_mode
  trigger).
- Grupos exclusivos completos: GET/PUT/DELETE, membros e lock atual.
- Maestro (assunto maestro): biblioteca do robô; progresso, print no erro, anexos, next_automation por nome,
  contadores de itens. Bot ganhou reads_task_file_arg.
- Guia do Bot refeito (Execução → Guia do Bot) com o Guia do Maestro.
- Menu "Notificações" virou "Chamado de erro" (mesma tela: N falhas seguidas → chamado no desk).
- Máquina em manutenção devolve as tasks da fila dela para outra máquina.
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
