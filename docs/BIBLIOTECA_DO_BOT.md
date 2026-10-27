# Biblioteca do bot (SDK do orquestrador)

Pacote Python pequeno que o robô importa para conversar com o orquestrador sem lidar com arquivo
de task, stdout e códigos de saída na mão. **Opcional**: o contrato por stdout e código de saída
continua valendo, e a biblioteca só o embrulha.

Nome: a definir junto com o novo nome do orquestrador. Enquanto isso, nas referências abaixo,
`<biblioteca>`.

## Princípios

- Zero dependências além da biblioteca padrão do Python (o robô pode ter qualquer stack).
- Funciona fora do orquestrador: sem as variáveis `ORKAFLOW_*`, lê um `task.json` local e
  imprime no console. Assim o desenvolvedor testa na máquina dele.
- Nunca imprime segredo. O que vier de credencial é marcado para mascarar.
- Tudo que a biblioteca faz pode ser feito "na unha" (stdout, arquivo de resultado, código
  de saída). Ela nunca é obrigatória.

## Ideias (ordem sugerida de implementação)

### 1. Ler a task
```python
from <biblioteca> import tarefa

with tarefa() as t:
    t.id                      # id da task
    t.parametros              # parameters_json como dict (ex.: t.parametros["filtros"])
    t.credencial("sap_senha") # valor já resolvido de dados_acesso; erro claro se não existir
    t.ambiente("SAP_URL")     # variável de ambiente injetada pelo worker
```
Fonte: `ORKAFLOW_TASK_FILE` (JSON que o worker escreve). Fora do orquestrador: `./task.json`.

### 2. Avisar credencial inválida (**primeira coisa a entrar**)
```python
t.alerta_credencial("sap_senha", motivo="senha_expirada", mensagem="SAP: senha venceu")
```
Imprime a linha `ORKAFLOW_ALERTA_CREDENCIAL {json}` e encerra com código 3. É exatamente o
contrato descrito em `docs/GUIA_DO_BOT_AJUSTES.md`; o orquestrador marca a credencial, pausa
agendamentos e bloqueia tasks novas.

### 3. Resultado
```python
t.resultado({"linhas": 1200, "arquivo": "saida.xlsx"})
```
Escreve o `ORKAFLOW_RESULT_FILE`. É o que alimenta o encadeamento (gatilho de sucesso) e os
eventos configuráveis ("se retorno contém X, faça Y").

### 4. Log estruturado
```python
t.log.info("Lendo planilha", linhas=1200)
t.log.aviso("Linha sem CNPJ", linha=37)
```
Uma linha JSON por evento no stdout, que o worker já envia para o log da task; o painel passa a
filtrar por nível e por campo.

### 5. Progresso
```python
t.progresso(etapa=3, total=7, texto="Enviando ao SAP")
```
Linha `ORKAFLOW_PROGRESSO {json}` no stdout; o worker repassa e a tela da task mostra barra e
etapa atual. Precisa de uma rota nova no backend e do campo na task.

### 6. Evidências
```python
t.evidencia("C:/tmp/print_final.png", descricao="Tela final do SAP")
```
Upload pelo worker ao fim da task (limite de tamanho), listado e baixável na tela da task.

### 7. Encadeamento dinâmico
```python
t.proximas_automacoes([{"automation_id": 12, "parameters": {"lote": "A"}}])
```
Escreve a chave `orkaflow.next_automations` no resultado, que o gatilho de sucesso já entende.

### 8. Encerramento padronizado
```python
t.sucesso("Processados 1200 itens")
t.erro("Planilha não encontrada", categoria="negocio", retentavel=False)
```
Define `final_message`, código de saída e categoria do erro (hoje o worker manda tudo como
`bot_exit_code`; com categoria, a retentativa automática sabe o que repetir).

## Lado do worker e do backend

- Worker: já lê a linha de alerta de credencial (feito em out/2026). Para progresso, log
  estruturado e evidências, precisa reconhecer as outras linhas `ORKAFLOW_*` e repassar.
- Backend: rotas de progresso e de evidência; campos na task; tela.

## Distribuição

- Repositório Git próprio, versão semântica, instalado pelo worker junto com o
  `requirements.txt` do bot (ou pré-instalado no venv do worker, com a versão fixada).
- Um robô piloto (o mais simples do parque) migra primeiro; a interface sai do que ficar bom lá.
