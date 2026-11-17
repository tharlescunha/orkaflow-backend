# Liberar acesso (desbloquear usuário sem esperar 24 horas)

Escrito em 17/11/2026. Quando alguém disser "liberar acesso" ou "desbloquear aprovador", é aqui que se volta.

---

## 1. O problema

Alguns robôs se protegem sozinhos contra bloqueio de usuário. O robô de **aprovação de insumos** (e o **Beholder**, que
aplica a mesma regra) conta as recusas de login do SAP por aprovador nas últimas 24 horas. Com 2 recusas ele para de
tentar com aquele usuário, para não bloqueá-lo no SAP.

- A conta é feita **dentro do robô**, numa tabela dele (`tbl_registro_erros`). O Regente não participa e não enxerga.
- Por isso a tela de Credenciais (que bloqueia/desbloqueia credenciais cadastradas no Regente) **não resolve** esse caso:
  a senha do aprovador fica no `BD_INTRANET`, e não no Regente.
- Quando o usuário é corrigido (senha trocada, TI desbloqueou no SAP), o robô continuava suspenso até passar as 24 horas.
  Caso real: LEZANATTA, 16/11/2026, pedido 00007397.

## 2. O que foi feito

Uma tela no Regente para avisar: **"este usuário já está ok, pode continuar"**.

**Onde:** menu **Segurança → Liberar acesso** (`/access-releases`).

**Como usar:** digite o usuário (ex.: `LEZANATTA`), confirme o sistema (SAP), uma observação se quiser, clique em
**Liberar usuário** e confirme. Fica registrado quem liberou e quando. A lista abaixo mostra o histórico, com a situação
**Valendo** (últimas 48 h) ou **Antiga**.

**O que a liberação faz:** não faz login em nada, não executa robô nenhum. Só registra o aviso e passa a entregá-lo aos
robôs (seção 3).

| Parte | Arquivo |
|---|---|
| Serviço (armazenamento, entrega) | `app/services/access_release_service.py` |
| Rotas `GET/POST /api/v1/access-releases/` | `app/api/v1/access_releases.py`, `app/schemas/access_release.py` |
| Entrega ao robô | `app/services/env_variable_service.py` (`_add_access_releases`) |
| Guia da API | `app/integration/api_guide.py` |
| Testes | `tests/test_access_releases.py` |
| Tela (frontend) | `src/pages/access-releases/access-releases-page.tsx`, menu em `src/lib/navigation.ts` |

Sem migration e sem tabela nova: as liberações ficam em `system_settings` (chave `access_releases`, JSON, no máximo 300
registros).

## 3. Contrato para os robôs (o que o robô precisa fazer)

**Importante: a tela só tem efeito nos robôs que passarem a ler a variável abaixo.** Sem isso ela apenas registra.

Toda task recebe, junto com as outras variáveis de ambiente do Regente (as mesmas que o robô já lê com `maestro.env(...)`
ou `os.environ`), a variável:

```
LIBERACOES_DE_ACESSO = {"LEZANATTA": "2026-11-17T14:10:00Z", "OUTRO": "2026-11-17T09:00:00Z"}
```

- JSON: **login em MAIÚSCULAS** → horário da liberação em **UTC** (`AAAA-MM-DDTHH:MM:SSZ`).
- Só existe quando há liberação das últimas 48 h. Sem liberação, a variável **não existe**.
- Se houver mais de uma liberação do mesmo login, vale o horário da mais nova.
- Uma variável de mesmo nome cadastrada à mão em Variáveis tem prioridade (não use esse nome para outra coisa).

**Regra para o robô:** ao contar as recusas de login do aprovador nas últimas 24 h, **ignorar as recusas anteriores ao
horário da liberação**. Se sobrar menos de 2, o aprovador não está suspenso.

```python
import json, os
from datetime import datetime, timezone

def liberado_em(login):
    bruto = os.environ.get("LIBERACOES_DE_ACESSO")  # ou maestro.env("LIBERACOES_DE_ACESSO")
    if not bruto:
        return None
    try:
        valor = json.loads(bruto).get(login.upper())
    except ValueError:
        return None
    return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if valor else None

# recusas = linhas de tbl_registro_erros do aprovador nas últimas 24 h, com o horário JÁ CONVERTIDO PARA UTC
corte = liberado_em("LEZANATTA")
validas = [r for r in recusas if corte is None or r.horario_utc > corte]
suspenso = len(validas) >= MAX_LOGINS_RECUSADOS_APROVADOR
```

**Atenção ao fuso:** o outro chat observou que `tbl_registro_erros` grava hora **local** (Brasília, UTC-3) e a comparação
usa UTC. O horário da liberação é UTC: converta o horário das recusas para UTC antes de comparar.

**Onde aplicar:** no robô de aprovação **e** no Beholder (ele aplica a mesma regra). Os dois recebem a variável, porque ela
vem no nível global das variáveis.

Depois que o robô aplicar a regra, se a senha ainda estiver errada ele tenta, recebe a recusa e a conta recomeça: duas
recusas novas suspendem o aprovador de novo. A liberação não enfraquece a proteção.

## 4. Como testar

Testes automáticos:

```powershell
cd C:\Projetos\orkaflow-backend
.venv\Scripts\python.exe -m unittest tests.test_access_releases tests.test_integration_mcp
```

Conferência manual:

1. Abra Segurança → Liberar acesso, libere um usuário de teste (ex.: `TESTE01`).
2. Rode qualquer task de uma automação e confira que ela recebeu `LIBERACOES_DE_ACESSO` (no robô: imprima a variável).
3. Depois de 48 horas a variável deixa de ser entregue e a linha aparece como **Antiga**.

## 5. Como desfazer

A tela não altera nada fora do Regente. Para desligar a entrega aos robôs, apague o registro:

```sql
DELETE FROM orkaflow.system_settings WHERE [key] = 'access_releases';
```

(ou `git revert` do commit desta funcionalidade; não há migration nem schema para desfazer).

## 6. Próximos passos possíveis

- **Liberação automática pela troca de senha** (ideia do outro chat): o robô guarda uma marca (hash) da senha do
  `BD_INTRANET` quando o login é recusado e só conta recusas feitas com a senha atual. Aí corrigir a senha no
  `BD_INTRANET` já libera sozinho, sem ninguém clicar. Combina com esta tela, que cobre o caso em que a senha não mudou.
- **Mostrar no painel quem está suspenso:** exige que os robôs avisem o Regente quando suspendem alguém.
