# Maestro — biblioteca do robô (desenho aprovado em 27/10/2026)

Pacote Python `maestro` que o robô importa para conversar com o orquestrador: ler o que o
orquestrador mandou (parâmetros, credenciais, variáveis) e devolver logs, progresso, print de
erro, resultado, próximo robô e encerramento. **Opcional**: o contrato antigo (arquivo JSON por
argumento, `print`, código de saída) continua valendo, sem mexer em nenhum robô existente.

Regra número um (Tharles, 27/10): **o worker não pode quebrar nem travar.** Tudo que o Maestro
pede ao worker passa por canais que já existem e já são tolerantes a falha. Linha que o worker
não entende vira log comum. Falha ao tratar uma linha do Maestro nunca derruba a task.

## Decisões do Tharles

| Ponto | Decisão |
|---|---|
| Nomes das chamadas | Inglês: `info`, `warning`, `error`, `success`, `step`, `screenshot`, `next_automation` |
| Flag produção | `Maestro(producao=True)`; **padrão True** se não passar. `producao=False` = modo local |
| Print no erro | `screenshot_on_error=False` por padrão; o robô liga quando é de tela |
| Chamar outra automação (`next_automation`) | O robô passa o **nome da automação** (não do bot): ela leva parâmetros, credenciais e padrões dela, como em "Nova task"; `parametros` é opcional e só sobrescreve. Permitido para automações ativas do **mesmo repositório** (área) do robô que chamou; cross-repositório é recusado com log. Decidido pelo Tharles em 27/10 |
| Instalação | **Nada a instalar no robô.** O worker instala o `maestro` em todo venv de bot (versão fixada, vem junto com o worker). Na máquina do desenvolvedor: `pip install` apontando para o Git do worker (ver "Distribuição") |
| Argumento do JSON | Novo campo no bot: "robô lê o arquivo da task por argumento". Bots atuais ficam marcados (nada muda); bot novo nasce desmarcado e o worker chama só `python main.py` |

## Como funciona

**Receber**: o worker já escreve o arquivo da task e já exporta `ORKAFLOW_TASK_FILE`,
`ORKAFLOW_RESULT_FILE`, `ORKAFLOW_TASK_ID`, `ORKAFLOW_AUTOMATION_ID`... O Maestro lê daí.
Em modo local (`producao=False`) lê `task.json` ao lado do `main.py`.

**Devolver**: linhas no stdout com prefixo fixo + JSON numa linha só. O worker já lê o stdout
linha a linha (é o mesmo canal do `print`, então o relógio de inatividade continua valendo):

```
MAESTRO {"v":1,"type":"log","level":"info","message":"Lendo pedidos","data":{"total":120}}
MAESTRO {"v":1,"type":"step","current":3,"total":7,"text":"Enviando ao SAP"}
MAESTRO {"v":1,"type":"screenshot","path":"C:\\OrkaFlow\\tmp\\shot_42_1.png","description":"Tela do SAP no erro"}
MAESTRO {"v":1,"type":"end","status":"error","message":"Planilha não encontrada","category":"business","retryable":false}
```

Alerta de credencial continua sendo `ORKAFLOW_ALERTA_CREDENCIAL {json}` + código de saída 3
(já no ar). Resultado e próximo robô vão pelo arquivo de resultado (`ORKAFLOW_RESULT_FILE`),
que já alimenta encadeamento e eventos:

```json
{"result": {"pedidos": 42},
 "orkaflow": {"next_automations": [{"automation": "Aprovacao_Pedidos", "parameters": {"lote": "A"}}]}}
```

**O worker, ao ler uma linha `MAESTRO `**: tenta `json.loads`; se falhar ou `type` for
desconhecido, trata como texto comum. Se der certo:

| type | O que o worker faz |
|---|---|
| `log` | manda ao log da task com o nível pedido (`info`/`warning`/`error`) e os campos extras no texto |
| `step` | guarda etapa atual; manda ao backend (rota nova, só quando muda) |
| `screenshot` | lê o arquivo, comprime em JPEG, guarda para enviar no erro (`error_screenshot`, coluna que já existe) ou como evidência |
| `end` | usa `message` como mensagem final e `category`/`retryable` no erro, em vez de só "bot_exit_code" |

O código de saída do processo continua mandando: `end` com `status=error` sem o processo sair
diferente de 0 é tratado como erro do mesmo jeito (o Maestro garante os dois).

## Interface do pacote

```python
from maestro import Maestro, CredencialInvalida

maestro = Maestro()                      # producao=True, screenshot_on_error=False
maestro = Maestro(producao=False)        # máquina do desenvolvedor: lê ./task.json, imprime no console
maestro = Maestro(screenshot_on_error=True)

# entrada
maestro.param("filial", default="010")   # parameters_json, depois runtime_parameters_json
maestro.params                           # dict completo (parameters_json + runtime mesclados)
maestro.credential("sap_senha")          # valor resolvido de dados_acesso; KeyError claro se não existe
maestro.env("SAP_URL")                   # variável de ambiente injetada pelo worker
maestro.task.id / .automation_id / .correlation_id / .execution_mode

# saída
maestro.info("Lendo planilha", linhas=1200)
maestro.warning("Linha sem CNPJ", linha=37)
maestro.error("Falha ao abrir ME2L")             # só loga; não encerra
maestro.step(3, 7, "Enviando ao SAP")
maestro.screenshot("Tela do SAP")                 # tira print agora (mss/Pillow se houver; senão PowerShell)
maestro.attach("C:/saida.xlsx", "Relatório")     # anexo (até 5 MB, 10 por task): aparece na task para baixar
maestro.next_automation("Aprovacao_Pedidos", parametros={"lote": "A"})

# encerramento
maestro.success("1200 itens", result={"itens": 1200}, items_processed=1200, items_failed=3)   # contadores opcionais; sai com 0
maestro.fail("Planilha não encontrada", category="business", retryable=False)   # sai com 1
raise CredencialInvalida("sap_senha", motivo="senha_expirada", mensagem="...")  # sai com 3

# bloco recomendado
if __name__ == "__main__":
    with maestro:        # exceção não tratada -> error + traceback (+ print se ligado) + exit 1
        main()
```

`category`: `business` (regra de negócio, não repetir) ou `system` (ambiente, pode repetir). A
retentativa automática usa `retryable`.

## Extras que entram no projeto (sugestão minha)

- `maestro.timer("Login SAP")` como `with`: loga duração da etapa.
- `maestro.heartbeat()`: para laços longos sem saída, evita o timeout de inatividade.
- `maestro.secret(valor)`: marca um valor obtido em tempo de execução (ex.: token) para o worker
  mascarar no log.
- Versão do Maestro no primeiro log da task; o worker avisa se for mais nova que ele conhece.
- `maestro.stop_requested()`: diz se o painel pediu parada gentil, para o robô encerrar limpo
  (o worker já grava isso; o Maestro lê de um arquivo-sinal ao lado do arquivo da task).

## Modo local (`producao=False`)

Lê `./task.json` (modelo gerado por `python -m maestro init`), imprime logs no console com
cor, grava `./resultado.json`, `screenshot()` salva em `./screenshots/`, `next_automation()` só
imprime. Nenhum acesso à rede.

## O que muda em cada repositório

**worker** (`orkaflow-worker`):
- `maestro/` dentro do repositório (pacote com `pyproject.toml`), instalado no venv de cada bot
  ao instalar/atualizar o bot e conferido na partida do worker (`pip install --no-index` a
  partir da pasta local: sem rede).
- Leitor de stdout: reconhecer `MAESTRO ` (igual ao alerta de credencial, que já existe).
- `end`: mensagem final e categoria; `screenshot`: enviar no `send_error` (coluna já existe).
- `step`: nova chamada à API, só quando muda.
- Comando do bot sem o argumento quando o bot está marcado para não receber.
- Testes: parsing de cada linha, linha inválida vira texto, nada muda para bot sem Maestro.

**backend**:
- `bots.reads_task_file_arg` (bool, default true via migration).
- Progresso na task (`progress_current`, `progress_total`, `progress_text`) + rota do worker.
- `next_automations` por nome, restrito ao mesmo repositório e automação ativa.
- Guia da API, playbook, testes.

**frontend**:
- Detalhe da task: print abaixo do traceback; etapa atual e barra no cabeçalho.
- Novo bot / editar bot: caixa "robô lê o arquivo por argumento".
- Guia do Bot refeito (depois do Maestro): passo a passo montar → testar local → Git → bot →
  automação → agendamento; Maestro e JSON lado a lado; sem instalação de worker.

## Distribuição

- Fonte da verdade: `orkaflow-worker/maestro/`. Versão semântica em `maestro/__init__.py`.
- Máquinas: o worker instala/atualiza no venv de cada bot a partir da pasta local.
- Desenvolvedor: `pip install "git+https://<git do worker>#subdirectory=maestro"` ou o `.whl`
  publicado no feed do DevOps. Como o pacote não tem dependências, qualquer Python 3.10+ serve.

## Ctrl+Espaço e guia

O pacote tem anotações de tipo, `py.typed` e docstring com exemplo em cada chamada: o editor (VS Code,
PyCharm) mostra a lista e a descrição ao digitar `maestro.`. O Guia do Bot (task 9) ganha uma seção
"Guia do Maestro" com todas as chamadas e exemplos (pedido do Tharles, 27/10).

## Ordem de entrega

1. Pacote `maestro` (entrada, logs, success/fail, credencial, modo local) + worker entendendo
   `log` e `end` + instalação no venv. Nenhum comportamento muda para bot sem Maestro.
2. Print no erro: `screenshot` no worker, envio no `send_error`, imagem na tela da task.
3. Progresso: colunas, rota, worker, tela.
4. `next_automation` por nome (backend) e campo "lê arquivo por argumento" (backend, worker, tela).
5. Evidências de arquivo (`attach`).
6. Guia do Bot novo.
