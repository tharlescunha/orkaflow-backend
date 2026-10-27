# Ajustes para o Guia do Bot

Tela: menu **Execução → Guia do Bot** (`orkaflow-frontend/src/pages/runner-config/worker-registration-page.tsx`).
Este arquivo guarda o que precisa mudar nela. Quando a tela for refeita, apagar daqui o que já entrou.

## 1. Enxugar a tela

Hoje a página tem 490 linhas e blocos de código grandes demais: a pessoa que vai escrever um robô
precisa rolar muito para achar o que importa. Direção:

- **Uma ideia por seção, curta.** Título, duas frases, e o trecho de código mínimo (5 a 15 linhas).
  O resto vai para um "ver exemplo completo" recolhido.
- **Ordem pela jornada de quem desenvolve:** 1) como o orquestrador chama o robô, 2) como ler
  parâmetros e credenciais do arquivo da task, 3) como devolver resultado, 4) como avisar
  problemas (credencial inválida), 5) checklist.
- **Blocos de código com botão copiar** e no máximo uma rolagem horizontal.
- Tirar o que é de instalação do worker (isso é da tela Runner Config) ou deixar num rodapé.

## 2. Nova seção: "Avisar que a credencial não serve mais"

Entra logo depois de "como devolver resultado". Texto sugerido:

### Por que avisar

Quando a senha do usuário de serviço vence ou o usuário é bloqueado, o robô falha no login e,
sem aviso, o orquestrador continua agendando execuções. Cada tentativa com senha errada aproxima
o usuário do bloqueio no sistema de destino (SAP, por exemplo). Avisando, o orquestrador:

- marca a credencial como inválida na tela de Credenciais;
- pausa os agendamentos das automações que usam essa credencial;
- recusa novas tasks dessas automações até alguém trocar a senha;
- mostra o motivo na task e na automação.

Ou seja: **uma falha de login, zero novas tentativas, ninguém bloqueado.**

### Como avisar (sem biblioteca)

Quando detectar que o login falhou por senha ou bloqueio, imprima **uma linha** no stdout e
termine com **código de saída 3**:

```python
import json, sys

def avisar_credencial(chave: str, motivo: str, mensagem: str, sistema: str = "SAP") -> None:
    """motivo: senha_incorreta | senha_expirada | usuario_bloqueado"""
    print("ORKAFLOW_ALERTA_CREDENCIAL " + json.dumps({
        "sistema": sistema,
        "chave": chave,          # nome do item em dados_acesso (ex.: "sap_senha")
        "motivo": motivo,
        "mensagem": mensagem,
    }, ensure_ascii=False), flush=True)
    sys.exit(3)
```

Uso dentro do robô:

```python
try:
    sap.login(dados_acesso["sap_usuario"], dados_acesso["sap_senha"])
except SenhaExpirada as exc:
    avisar_credencial("sap_senha", "senha_expirada", str(exc))
```

Regras:

- A linha precisa começar com `ORKAFLOW_ALERTA_CREDENCIAL ` seguida de um JSON numa linha só.
- `chave` é o nome do item dentro de `dados_acesso` que falhou. O worker sabe qual credencial
  resolveu para a task e associa sozinho.
- `motivo` aceita `senha_incorreta`, `senha_expirada` ou `usuario_bloqueado`. Outro valor vira
  "inválida".
- O código de saída 3 é reservado para isso. Se o robô sair com 3 sem a linha, o orquestrador
  marca a credencial como "inválida" com a mensagem genérica.
- Nunca imprima a senha. O worker mascara os valores da credencial no log, mas não dependa disso.
- Não é só SAP: serve para qualquer sistema. O campo `sistema` é só informativo.

### Como avisar (com a biblioteca)

Quando a biblioteca do orquestrador existir (ver `docs/BIBLIOTECA_DO_BOT.md`), a mesma coisa fica:

```python
from <biblioteca> import tarefa

with tarefa() as t:
    try:
        sap.login(t.credencial("sap_usuario"), t.credencial("sap_senha"))
    except SenhaExpirada as exc:
        t.alerta_credencial("sap_senha", motivo="senha_expirada", mensagem=str(exc))
```

### O que o desenvolvedor vê depois

- Credenciais: selo vermelho com o motivo e a task que detectou.
- Automação e Health: faixa "Credencial X com senha expirada. Agendamentos pausados".
- Task: motivo final "Credencial inválida: ...".
- Ao salvar a senha nova em Credenciais, tudo volta sozinho; a próxima task com sucesso marca
  a credencial como válida.

## 3. Outros ajustes menores

- Mostrar o formato real da referência de credencial no `parameters_json`:
  `{"dados_acesso": {"credential_id": 16, "itens": {"sap_usuario": null, "sap_senha": null}}}`.
  O robô recebe `dados_acesso` já resolvido: `{"sap_usuario": "...", "sap_senha": "..."}`.
  As demais chaves do `parameters_json` (ex.: `filtros`) chegam intactas.
- Explicar o arquivo de resultado (`ORKAFLOW_RESULT_FILE`): JSON com o que o robô quiser
  devolver; é ele que alimenta o encadeamento e, no futuro, os eventos.
- Citar os códigos de saída: `0` sucesso, `3` credencial inválida, qualquer outro = erro.
