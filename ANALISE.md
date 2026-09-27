# Análise: anatomia do agente

## Tarefa dada ao agente

```
encontre e conserte o bug baseado no teste que está falhando em test_inventory.py
```

## Nota sobre esta execução

O modelo exigido pelo README, `openai/gpt-oss-120b` (via Groq), é um *reasoning model*
treinado pela OpenAI com tool calling **nativo** como parte do comportamento, não um
modelo "neutro" que apenas segue instruções de formatação em prosa. Isso colide de forma
sistemática com o mecanismo de simulação de tool calling por texto que este exercício usa
(a colisão em si virou o principal achado desta análise, discutido nas seções 3, 5 e 6).

Em **15 execuções completas** de `python agent.py` (todas com a mesma tarefa) mais **~25
chamadas isoladas de diagnóstico** direto à API (feitas fora do agente, só para investigar
o comportamento), **0% terminaram com uma tool call executada com sucesso**. Por isso, em
vez de um trace único "feliz" (que não existe, apesar de muita tentativa honesta), esta
análise usa **duas execuções reais completas** (A e B), capturadas com o agente já
instrumentado, que juntas cobrem todos os componentes pedidos. O padrão de falha,
reproduzido de forma consistente, é ele próprio a evidência central.

No caminho, foi encontrado e corrigido um bug real do `agent.py` original (não do
enunciado): ele só lia `response.choices[0].message.content`, mas a Groq devolve, para
esse modelo, um campo `reasoning` separado, e é frequentemente ali, não em `content`, que
a linha `tool: nome({...})` pedida aparece. A correção está em `agent.py:209-218` e é
discutida na seção 3. `inventory.py` permanece com o bug original em todas as execuções
(nenhuma tool foi executada de fato).

## Prompt exato enviado ao modelo (system + user, sem nenhuma variável)

```
You are a coding assistant whose goal it is to help us solve coding tasks.
You have access to a series of tools you can execute. Hear are the tools you can execute:

TOOL
===
    Name: read_file
    Description: 
Gets the full content of a file provided by the user.
:param filename: The name of the file to read.
:return: The full content of the file.

    Signature: (filename: str) -> Dict[str, Any]
    
===============
TOOL
===
    Name: list_files
    Description: 
Lists the files in a directory provided by the user.
:param path: The path to a directory to list files from.
:return: A list of files in the directory.

    Signature: (path: str) -> Dict[str, Any]
    
===============
TOOL
===
    Name: edit_file
    Description: 
Replaces first occurrence of old_str with new_str in file. If old_str is empty,
create/overwrite file with new_str.
:param path: The path to the file to edit.
:param old_str: The string to replace.
:param new_str: The string to replace with.
:return: A dictionary with the path to the file and the action taken.

    Signature: (path: str, old_str: str, new_str: str) -> Dict[str, Any]
    
===============


When you want to use a tool, reply with exactly one line in the format: 'tool: TOOL_NAME({JSON_ARGS})' and nothing else.
Use compact single-line JSON with double quotes. After receiving a tool_result(...) message, continue the task.
If no tool is needed, respond normally.

IMPORTANT: do not use any native function calling / tool_calls mechanism of the API.
The ONLY valid way to invoke a tool is writing a plain text line in the exact format
above. Never fabricate or guess what a tool would return, always actually invoke it
using that text format and wait for the real tool_result(...) message.
```
>> Tools/ACI: repare que **não existe nenhum campo `tools` nem `tool_choice`** na
>> requisição HTTP, as três ferramentas só existem como texto descritivo dentro do
>> `content` do system prompt. Para um modelo treinado com function calling nativo,
>> "ferramenta" é um conceito com lugar próprio no schema da API; aqui esse lugar está
>> vazio, e o que o modelo vê é só prosa. Essa lacuna estrutural é a raiz de quase todas
>> as falhas discutidas na seção 6.

```
role: user
content: "encontre e conserte o bug baseado no teste que está falhando em test_inventory.py"
```

## Trace anotado

### Execução A: as 3 tentativas de chamada à API falham antes de qualquer texto voltar

```
[FALHA] tentativa 1/3 de chamada ao LLM falhou antes de retornar texto: Error code: 400 -
{'error': {'message': "Parsing failed. The model generated output that could not be
parsed. Please adjust your prompt. See 'failed_generation' for more details.",
'type': 'invalid_request_error', 'code': 'output_parse_failed', 'failed_generation':
'The user says: "encontre e conserte o bug baseado no teste que está falhando em
test_inventory.py". Portuguese: find and fix the bug based on failing test in
test_inventory.py. We need to look at repository files. Use list_files.'}}
[THOUGHT PARCIAL VAZADO PELO ERRO] 'The user says: ... We need to look at repository
files. Use list_files.'
```
>> Loop: esta é a 1ª de até 3 tentativas *dentro da mesma iteração* do loop
>> (`execute_llm_call_with_retry`, `agent.py:222-256`). O loop do agente ainda nem
>> começou de fato, estamos presos tentando obter qualquer texto de volta da API.
>>
>> Thought: `failed_generation` é raciocínio real do modelo ("we need to look at
>> repository files") vazado pelo próprio corpo do erro HTTP, um Thought que existiu,
>> mas nunca chegou a virar uma resposta válida que o agente pudesse ver.
>>
>> Falha de parsing (mais grave do que o README antecipa): isto não é o
>> `extract_tool_invocations` falhando em reconhecer uma linha, é a própria API da
>> Groq rejeitando a geração do modelo *antes* de qualquer texto chegar ao nosso
>> parser (código `output_parse_failed`, o servidor não consegue separar os canais de
>> raciocínio e resposta do formato interno do modelo).

```
[FALHA] tentativa 2/3 de chamada ao LLM falhou antes de retornar texto: Error code: 400 -
{'error': {'message': "Parsing failed. ...", 'code': 'output_parse_failed',
'failed_generation': 'The user says (Portuguese): "encontre e conserte o bug baseado no
teste que está falhando em test_inventory.py" meaning "find and fix the bug based on the
failing test in test_inventory.py". So we need to run tests? We have code repository. We
need to list files.'}}
[THOUGHT PARCIAL VAZADO PELO ERRO] 'The user says (Portuguese): ... We need to list
files.'
```
>> Contexto: a `conversation` enviada nas tentativas 1, 2 e 3 é **exatamente a mesma**
>> (o retry em `execute_llm_call_with_retry` não modifica o array de mensagens), cada
>> tentativa é uma nova amostragem independente do mesmo prompt, não uma continuação
>> com mais contexto. É por isso que o raciocínio vazado varia de palavras entre as
>> tentativas mesmo perguntando a mesma coisa: é resposta nova, não conversa.

```
[FALHA] tentativa 3/3 de chamada ao LLM falhou antes de retornar texto: Error code: 400 -
{'error': {'message': "Parsing failed. ...", 'code': 'output_parse_failed',
'failed_generation': 'We need to find failing test in test_inventory.py. We need to
inspect repository.'}}
[THOUGHT PARCIAL VAZADO PELO ERRO] 'We need to find failing test in test_inventory.py. We
need to inspect repository.'

[FALHA IRRECUPERAVEL] todas as 3 tentativas de chamada ao LLM falharam nesta iteracao,
execucao encerrada sem resposta do modelo. Ultimo erro: Error code: 400 - {...
'output_parse_failed' ...}
```
>> Loop / Guardrail: aqui o loop para (`return` em `agent.py:289`), mas não porque a
>> tarefa foi concluída, e sim porque as tentativas técnicas de obter qualquer resposta
>> se esgotaram. Isso é ainda mais extremo do que "parar achando que terminou sem ter
>> terminado": aqui o agente para sem nenhuma noção de ter feito qualquer coisa, nem
>> certa nem errada. `inventory.py` nunca foi tocado.

### Execução B: a resposta chega, mas a tool call não é reconhecida pelo parser

```
## Iteracao 1
```
>> Loop: uma iteração completa é uma chamada a `execute_llm_call_with_retry`
>> bem-sucedida (`agent.py:280-281`), seguida do processamento da resposta em
>> `split_thought_and_tool_lines` mais `extract_tool_invocations`.

```
**Thought:**
The user asks in Portuguese: "encontre e conserte o bug baseado no teste que está
falhando em test_inventory.py" -> Find and fix the bug based on the failing test in
test_inventory.py.

We need to run tests? We need to view repository. Use list_files.tool: list_files({"path": "."})
```
>> Thought: este é o texto que `split_thought_and_tool_lines` (`agent.py:181-201`)
>> tratou como thought inteiro, porque **nenhuma linha começa com `"tool:"`** (a
>> chamada está colada no fim da última frase, não em linha própria). A função aplica
>> a regra do README ("se não houver linha tool, a resposta inteira é o thought") e
>> devolve o texto todo como raciocínio, mesmo ele contendo uma tentativa de ação.
>>
>> Tools/ACI: o modelo decidiu a ação certa (`list_files({"path": "."})` é exatamente
>> o primeiro passo sensato) e escreveu a sintaxe textual certa, mas colada
>> diretamente após "Use list_files." sem quebra de linha. Para um parser estrito
>> baseado em linha (que é o que este exercício pede), isso não é uma tool call válida.
>> Este texto veio do campo `reasoning` da resposta (ver seção 3); sem a correção de
>> `agent.py:209-218`, esse texto inteiro seria descartado e o agente veria uma
>> resposta vazia.

```
[PARSING] a resposta contém a palavra 'tool:' mas nenhuma linha no formato esperado foi
encontrada, tratada como resposta final.
```
>> Falha de parsing: aviso gerado pela detecção automática em `agent.py:298-302`.
>> Confirma exatamente o que a seção 6 documenta; não é uma inferência feita depois,
>> é uma checagem programática rodando a cada iteração.

```
_(sem tool call, resposta tratada como final da tarefa)_
```
>> Guardrail: aqui a ausência de guardrail fica mais visível. O agente não sabe que
>> "list_files" era a intenção do modelo, ele só vê `tool_invocations == []` e conclui,
>> sem nenhuma verificação, que a tarefa terminou (`agent.py:322-330`). Nenhum arquivo
>> foi lido, nenhuma edição feita, nenhum teste rodado. `inventory.py` segue com
>> `return price - percent`.

## 1. Loop

O loop do agente é o `while True` interno de `run_coding_agent_loop`
(`agent.py:279-358`). Uma **iteração completa** é uma chamada bem-sucedida a
`execute_llm_call_with_retry` seguida do processamento da resposta (split em
thought/tool_lines, extração de invocações, execução de cada tool encontrada). O que faz
o laço **continuar**: a resposta contém pelo menos uma tool call reconhecida por
`extract_tool_invocations`, e nesse caso o `for` executa cada tool, acrescenta o
`tool_result` à `conversation`, e o `while True` roda de novo sem nunca ter passado pelo
`input()` externo. O que faz o laço **parar**: (a) a resposta não tem nenhuma tool call
reconhecida (`agent.py:322-330`, caso da Execução B), ou (b) todas as tentativas de
chamar o LLM falharam tecnicamente (`agent.py:282-289`, caso da Execução A).

Achado relevante: em nenhuma das 15 execuções completas o loop chegou a dar uma segunda
volta, ele sempre parou (por um motivo ou outro) já na primeira iteração, porque nunca
houve uma tool call reconhecida que o levasse a continuar. O loop, como código, está
correto e faz exatamente o que deveria; o que falta é o *conteúdo* das respostas do
modelo se encaixar no formato que o disparo do "continue" exige.

## 2. Contexto

O mecanismo está em `agent.py:355-358`: o resultado de uma tool (`result_str =
f"tool_result({json.dumps(resp)})"`) é appendado à `conversation` com `role: "user"`, e é
exatamente esse texto, não uma versão "bonita", que o LLM vai ler na chamada seguinte
(por isso o log da Action/Observation mostra a mesma string que é appendada).

Duas coisas que as execuções reais mostram sobre o contexto, e que não exigem sucesso de
uma tool call para serem visíveis:

- **Na Execução A**, como todas as 3 tentativas falharam, `run_coding_agent_loop` retorna
  sem nunca appendar nada além da mensagem original do usuário. O contexto fica congelado
  em "usuário perguntou X", sem nenhum turno do assistente.
- **Quando há tool call, a resposta do assistente (o Thought) nunca é appendada à
  `conversation`**, só o `tool_result` entra, com `role: "user"` (`agent.py:355-358`). O
  ramo que appenda a resposta do assistente como `role: "assistant"` só existe no caminho
  "sem tool call" (`agent.py:326-329`, visível na Execução B). Ou seja, mesmo numa
  hipotética execução bem-sucedida, o modelo perderia, no turno seguinte, o próprio
  raciocínio que o levou a chamar aquela tool; o contexto que ele "vê" depois é só o
  resultado bruto, sem o porquê. Isso é uma limitação real de como este agente monta
  contexto, não um bug da instrumentação.

## 3. Tools / ACI

As três tools (`read_file`, `list_files`, `edit_file`, registradas em `TOOL_REGISTRY`,
`agent.py:117-121`) são descritas em prosa no system prompt (ver seção "Prompt exato
enviado"), e a convenção pedida é uma linha de texto `tool: NOME({"arg": "valor"})`,
parseada por `extract_tool_invocations` (`agent.py:138-159`) via `split("(", 1)` mais
`json.loads`, ou seja, regex/string matching, não JSON Schema nem tool calling nativo.
Não existe nenhum campo `tools`/`tool_choice` na requisição à API.

O achado central desta análise é que `openai/gpt-oss-120b` **também tem uma ACI própria**,
treinada pela OpenAI, e ela colide com a nossa em três pontos diferentes da pilha:

1. **O modelo tenta usar o canal de tool calling nativo dele mesmo sem termos declarado
   `tools=`.** Erro real capturado:
   ```json
   {
     "message": "Tool choice is none, but model called a tool",
     "type": "invalid_request_error",
     "code": "tool_use_failed",
     "failed_generation": "{\"name\": \"repo_browser.list_files\", \"arguments\": {\"path\": \"\"}}"
   }
   ```
   `repo_browser.list_files`, `tool.exec`, `tool.run`, nomes que não existem no
   `TOOL_REGISTRY` deste projeto, são resquícios do próprio treinamento agentic do
   modelo (ferramentas internas de navegação de repositório e execução, prováveis do
   formato "Harmony" da OpenAI para gpt-oss). A Groq rejeita com 400 porque não há onde
   colocar essa chamada estruturada; o texto nem chega a existir para o
   `extract_tool_invocations`.

2. **A saída interna do modelo (raciocínio mais tentativa de chamada) não fecha de forma
   parseável pelo tradutor da Groq**, gerando `output_parse_failed` (ver Execução A
   completa), mesmo problema de fundo, sintoma diferente.

3. **Quando a resposta passa (200 OK), o texto útil às vezes vem no campo `reasoning`,
   não em `content`.** Resposta real capturada via diagnóstico direto à API:
   ```json
   "message": {
     "content": "",
     "tool_calls": null,
     "reasoning": "We need to run tests to see failing test. Use list_files.tool: list_files({\"path\": \".\"})"
   },
   "usage": { "completion_tokens_details": { "reasoning_tokens": 25 } }
   ```
   O `execute_llm_call` original só lia `message.content`; um bug real, não do modelo,
   corrigido em `agent.py:209-218` (concatena `reasoning` com `content`). Sem essa
   correção, a Execução B teria mostrado uma resposta vazia, escondendo que o modelo
   tinha, de fato, tentado fazer a coisa certa.

Mesmo depois da correção, a chamada extraída do `reasoning` costuma vir colada ao texto
anterior, sem quebra de linha (ver seção 6), então o ciclo de falha nunca se resolve
completamente, só muda de forma.

## 4. Thought

O exemplo mais completo é o Thought da Execução B: um parágrafo inteiro de raciocínio
("The user asks in Portuguese... We need to run tests? We need to view repository...")
que termina tentando, sem sucesso formal, uma tool call, mas nunca gera uma Action
reconhecida. É puro raciocínio do ponto de vista do agente, mesmo contendo uma intenção
de ação.

Mais revelador ainda são os `[THOUGHT PARCIAL VAZADO PELO ERRO]` da Execução A.
Normalmente, segundo a aula, esse passo fica escondido porque as ferramentas prontas só
expõem o resultado da ação, não o texto bruto do modelo. Aqui a situação é mais extrema:
nem a instrumentação deste projeto consegue ver esse Thought pelo caminho normal; ele só
foi capturado porque a API da Groq, ao rejeitar a geração, decidiu (sem garantia nenhuma
de que sempre faça isso) incluir o texto no corpo do erro. Se esse campo não existisse,
esse raciocínio simplesmente desapareceria sem deixar rastro nenhum, nem no trace.

## 5. Guardrail

Este é o item mais importante, e aqui ele é ainda mais extremo do que o exemplo da aula:
o `TOOL_REGISTRY` deste agente simplificado (`agent.py:117-121`) só tem `read_file`,
`list_files` e `edit_file`. **Não existe nenhuma tool de execução (`execute`/`bash`)**.
Ou seja, mesmo num cenário hipotético onde tudo funcionasse perfeitamente, este agente
específico não teria como rodar `pytest` sozinho; a ausência de guardrail aqui não é só
comportamental (ele não pensou em verificar), é estrutural (ele não teria com o quê).

Na prática, em nenhuma das execuções reais o agente chegou perto de precisar dessa
decisão, porque parou antes:

- **Execução A**: parou porque as tentativas técnicas se esgotaram, nem chegou a ter uma
  "opinião" sobre a tarefa estar feita ou não.
- **Execução B**: parou porque `tool_invocations` ficou vazio, e o código trata isso
  incondicionalmente como "resposta final" (`agent.py:322-330`). O modelo achou que
  tinha terminado (ou, pelo menos, o agente tratou a resposta dele como se fosse a
  resposta final), tendo, na prática, feito zero progresso real: nenhum arquivo lido,
  bug intacto. Não há nenhuma verificação, nem rodar o teste, nem checar se algum arquivo
  foi de fato modificado, antes de considerar a tarefa concluída.

Resposta direta à pergunta do template ("ele pode ter parado achando que terminou sem ter
terminado?"): sim, e de forma mais categórica do que o exemplo da aula. Lá, pelo menos, o
agente tinha feito uma correção real (ainda que sem verificar); aqui ele "termina" tendo
feito literalmente nada.

## 6. Falhas de parsing

Esta execução teve muito mais falha de parsing do que o README antecipa, em várias
camadas diferentes da pilha, não só no `extract_tool_invocations`:

1. **`tool_use_failed`**: o modelo tenta emitir uma tool call pelo canal nativo da API
   (`repo_browser.list_files`, `tool.exec`, `tool.run`, até um híbrido bizarro
   `"tool:list_files"`), rejeitado pela Groq antes de qualquer texto existir. Fora do
   alcance do parser deste projeto.
2. **`output_parse_failed`**: a Groq não consegue decodificar a saída interna (formato
   "Harmony") do modelo em texto limpo. Também fora do alcance do parser (ver Execução A
   completa).
3. **Bug de leitura, já corrigido**: texto útil chegando em `message.reasoning` e sendo
   descartado porque só se lia `message.content` (`agent.py:209-218` corrige isso). Não
   é falha do modelo nem da Groq, era leitura incompleta do lado do cliente.
4. **Chamada colada, fora de linha própria**: mesmo depois da correção acima, a linha
   `tool: list_files({"path": "."})` aparece grudada ao fim da frase anterior, sem quebra
   de linha (Execução B). `extract_tool_invocations` exige que a linha, após `.strip()`,
   comece com `"tool:"` (`agent.py:144-146`), corretamente, pela especificação do prompt
   ("exactly one line"), e por isso não reconhece essa chamada. Essa regra não foi
   alterada: fazer o parser procurar `"tool:"` em qualquer posição do texto resolveria
   este caso específico, mas esconderia exatamente o tipo de fragilidade que este
   exercício pede para expor.
5. **Detecção de descarte parcial** (`agent.py:304-313`, tipo 2 do instrumentador
   implementado neste projeto): checagem para quando há mais linhas `tool:` do que
   invocações reconhecidas (indicando JSON quebrado em alguma), mas ela nunca disparou
   nas execuções realizadas; nunca houve mais de uma linha `tool:` reconhecível
   simultaneamente nos casos que passaram pela API. Vale registrar isso porque a ausência
   de um tipo de falha também é dado, como o README pede.

**Tentativas de correção via prompt que não resolveram o problema (e por isso não
entraram na versão final do `agent.py`, com exceção da primeira)**: reforçar a instrução
para nunca usar tool calling nativo (essa entrou, `agent.py:34-37`, ajuda um pouco mas
não elimina o problema); dar um exemplo few-shot da chamada correta (não ajudou); e
restringir "escreva só a linha, nada mais" especificamente para quando o modelo decide
usar uma tool (não ajudou de forma confiável, e ainda introduziu alucinação de ciclos
inteiros de tool_result). Nenhuma alteração de prompt resolveu de forma confiável, o que
reforça que a causa é arquitetural, do treinamento do modelo, não uma questão de
fraseado.

**Estatística final**: em 15 execuções completas do agente instrumentado, com a tarefa
real do enunciado, **0 tool calls foram executadas com sucesso**. O README já avisa que
"modelos gratuitos seguem o formato pedido com menos consistência"; aqui a
inconsistência foi total, e a causa raiz (colisão entre o tool calling nativo do modelo e
a simulação por texto do harness) é, na prática, o argumento mais concreto possível a
favor de tool calling nativo (slide 33 da aula).
