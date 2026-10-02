# Análise: anatomia do agente

## Tarefa dada ao agente

```
encontre e conserte o bug baseado no teste que está falhando em test_inventory.py
```

## Nota sobre o modelo usado

O modelo inicialmente indicado, `openai/gpt-oss-120b`, não conseguiu ser usado neste
exercício: ele foi pós-treinado para emitir chamadas de ferramentas por um canal nativo
diferente do que o script lê, então a chamada vinha ilegível para o
`extract_tool_invocations`, ia para um campo que o código não lia, ou era rejeitada pela
própria API antes de qualquer texto voltar. A disciplina migrou para
`qwen/qwen3.8-27b` (via Groq), com um `SYSTEM_PROMPT` revisado no repositório oficial. As
execuções analisadas abaixo usam essa configuração.

Foram feitas **7 execuções completas** de `python agent.py` com a tarefa acima. Em **1**
delas o agente chegou a editar o arquivo (execução principal, analisada em detalhe). As
demais aparecem nas seções 2, 4, 5 e 6 quando ilustram algo que a execução principal não
mostra. O `inventory.py` do repositório contém a correção feita pelo agente
na execução principal.

## Prompt exato enviado ao modelo (system + user, sem nenhuma variável)

```
You are a coding assistant whose goal it is to help us solve coding tasks.
You can perform actions by emitting a single command line in exactly this format, and nothing else on that line:

tool: NAME({"arg": "value"})

Do not use JSON function-calling, a <tool_call> tag, or any other structured tool-call format your training may default to.
The ONLY format the system running you understands is the plain text line above.

Available commands:

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


Example of a correct response when you want to read a file named 'notes.txt':
tool: read_file({"filename": "notes.txt"})

Use compact single-line JSON with double quotes. After receiving a tool_result(...) message, continue the task using the same format when another action is needed.
If no action is needed, respond in plain prose.
```
>> Tools/ACI: as três ferramentas só existem como texto descritivo dentro do `content`
>> do system prompt, e a convenção de chamada é uma linha de texto `tool: NAME({...})`.
>> Não existe nenhum campo `tools` nem `tool_choice` na requisição HTTP, ou seja, é
>> parsing de texto, não tool calling nativo.

```
role: user
content: "encontre e conserte o bug baseado no teste que está falhando em test_inventory.py"
```

## Trace anotado (execução principal)

### Iteração 1

```
## Iteracao 1

**Thought:**
_(vazio)_

**Action:** `tool: list_files({"path": "."})`

**Observation:**
tool_result({"path": "/Users/ronalddmatias/atividade-anatomia-agentes", "files": [{"filename": "ANALISE.md", "type": "file"}, {"filename": "requirements.txt", "type": "file"}, {"filename": "ANALISE-TEMPLATE.md", "type": "file"}, {"filename": "test_inventory.py", "type": "file"}, {"filename": "__pycache__", "type": "dir"}, {"filename": "README.md", "type": "file"}, {"filename": ".env", "type": "file"}, {"filename": ".venv", "type": "dir"}, {"filename": "agent.py", "type": "file"}, {"filename": "trace.md", "type": "file"}, {"filename": ".git", "type": "dir"}, {"filename": "inventory.py", "type": "file"}]})
```
>> Loop: início de uma iteração completa. Uma volta do `while True` interno
>> (`agent.py:278`) é uma chamada ao LLM seguida do processamento da resposta. Aqui o
>> laço vai continuar porque a resposta continha uma tool call reconhecida.
>>
>> Thought: vazio. O modelo emitiu direto a linha `tool:`, sem raciocínio escrito antes.
>>
>> Action / Tools (ACI): `tool: list_files({"path": "."})` é exatamente o formato pedido,
>> uma linha que começa com `tool:` e tem JSON compacto entre parênteses, extraída por
>> `extract_tool_invocations` (`agent.py:141-162`).
>>
>> Contexto: a string da Observation, `tool_result({...})`, é appendada à `conversation`
>> como mensagem `role: "user"` (`agent.py:354-357`). Na chamada seguinte ao LLM, essa
>> lista de arquivos já faz parte do que o modelo lê.

### Iteração 2

```
## Iteracao 2

**Thought:**
<tool_call>

[PARSING] texto encontrado após a última linha 'tool:' (ignorado pelo parser): '</tool_call>\n<parameter= path> . </parameter>\n</invoke>'

**Action:** `tool: read_file({"filename": "test_inventory.py"})`

**Observation:**
tool_result({"file_path": "/Users/ronalddmatias/atividade-anatomia-agentes/test_inventory.py", "content": "from inventory import apply_discount\n\n\ndef test_apply_discount():\n    assert apply_discount(200, 10) == 180\n"})

**Action:** `tool: read_file({"filename": "inventory.py"})`

**Observation:**
tool_result({"file_path": "/Users/ronalddmatias/atividade-anatomia-agentes/inventory.py", "content": "def apply_discount(price, percent):\n    \"\"\"Aplica um desconto percentual ao preço.\"\"\"\n    return price - percent\n"})
```
>> Loop: uma única iteração com **duas** Actions. O loop é uma chamada ao LLM por volta,
>> não uma tool call por volta: as duas linhas `tool:` vieram na mesma resposta e o `for`
>> de `agent.py:333` executa as duas em sequência antes de chamar o LLM de novo.
>>
>> Thought / falha de parsing: o único texto antes da primeira `tool:` foi `<tool_call>`,
>> a abertura do formato nativo do próprio modelo, que ele começou a escrever e
>> abandonou. Depois da última `tool:` sobrou lixo desse mesmo formato (`</tool_call>`,
>> `<parameter= path> . </parameter>`, `</invoke>`). O instrumentador sinalizou isso com
>> `[PARSING]` (`agent.py:315-319`). O parser em si funcionou: as duas linhas `tool:`
>> válidas foram extraídas e executadas, e o resto foi ignorado sem causar dano.
>>
>> Contexto: as duas Observations entram na `conversation` na ordem em que foram
>> executadas. Elas contêm o texto exato dos dois arquivos, incluindo o `return price -
>> percent` que é o bug.

### Iteração 3

```
## Iteracao 3

**Thought:**
The test expects `apply_discount(200, 10)` to return 180, but the function returns `200 - 10 = 190`.

I'll fix it:

**Action:** `tool: edit_file({"path": "/Users/ronalddmatias/atividade-anatomia-agentes/inventory.py", "old_str": "def apply_discount(price, percent):\n    \"\"\"Aplica um desconto percentual ao preço.\"\"\"\n    return price - percent", "new_str": "def apply_discount(price, percent):\n    \"\"\"Aplica um desconto percentual ao preço.\"\"\"\n    return price - (price * percent / 100)"})`

**Observation:**
tool_result({"path": "/Users/ronalddmatias/atividade-anatomia-agentes/inventory.py", "action": "edited"})
```
>> Thought: raciocínio explícito que liga a Observation da iteração 2 ao teste ("a função
>> devolve `200 - 10 = 190`", valor que o modelo só poderia obter lendo o código que
>> veio no `tool_result`) e termina com a decisão de agir ("I'll fix it").
>>
>> Contexto: o `old_str` do `edit_file` é uma cópia exata do conteúdo de
>> `inventory.py`, inclusive a docstring com `ç` escapado. Isso só é possível porque a
>> Observation da iteração 2 estava na `conversation` quando o LLM foi chamado.
>>
>> Action / Tools (ACI): a única tool que altera o sistema de arquivos. A Observation
>> `"action": "edited"` é a única confirmação que o agente recebe de que a edição
>> aconteceu, e não diz nada sobre a edição estar correta.

### Iteração 4

````
## Iteracao 4

**Thought:**
Consertado. O bug estava em `inventory.py`:

```python
# Antes (errado):
def apply_discount(price, percent):
    return price - percent          # desconta o valor inteiro do percentual, não o %

# Depois (correto):
def apply_discount(price, percent):
    return price - (price * percent / 100)
```

A função original fazia `price - percent` (ex.: `200 - 10 = 190`), quando deveria aplicar o percentual correto: `200 - (200 * 10 / 100) = 180`, satisfazendo o teste `assert apply_discount(200, 10) == 180`.

_(sem tool call, resposta tratada como final da tarefa)_
````
>> Loop: o laço **para** aqui porque `tool_invocations` ficou vazio
>> (`agent.py:321-329`). Nada além disso decide o fim da execução.
>>
>> Thought: raciocínio que não gera nenhuma chamada de tool, ou seja, é a resposta final.
>> Ele afirma "satisfazendo o teste", mas essa afirmação é uma conta feita pelo próprio
>> modelo, não o resultado de rodar o teste.
>>
>> Guardrail: o agente declara "Consertado" sem nenhuma verificação externa. Ele não
>> rodou `pytest` e não tinha como rodar (ver seção 5).

## 1. Loop

O loop do agente é o `while True` interno de `run_coding_agent_loop`
(`agent.py:278-357`). Uma **iteração completa** é: uma chamada ao LLM
(`execute_llm_call_with_retry`), a separação da resposta em thought e linhas `tool:`
(`split_thought_and_tool_lines`), a extração das invocações
(`extract_tool_invocations`) e a execução de cada tool encontrada.

O que faz o laço **continuar**: a resposta conter pelo menos uma tool call reconhecida.
Nesse caso cada tool é executada, o `tool_result` é appendado à `conversation` e o laço
volta a chamar o LLM, sem passar pelo `input()` externo. Na execução principal isso
aconteceu nas iterações 1, 2 e 3.

O que faz o laço **parar**: a resposta não ter nenhuma tool call reconhecida
(`agent.py:321-329`), como na iteração 4, ou todas as tentativas de chamar a API
falharem (`agent.py:280-288`). Em nenhum dos dois casos o código pergunta se a tarefa
foi de fato concluída, o laço simplesmente não encontra mais nada para executar.

Uma iteração pode conter mais de uma Action, como a iteração 2, porque o que define a
volta é a chamada ao LLM, não a tool call.

## 2. Contexto

O ponto exato em que o resultado de uma tool vira contexto é `agent.py:348-357`:

```python
result_str = f"tool_result({json.dumps(resp)})"
...
conversation.append({"role": "user", "content": result_str})
```

O LLM não tem memória própria entre chamadas, ele só vê a lista `conversation`, que é
reenviada inteira a cada volta. Por isso o `tool_result` appendado na iteração 2 (conteúdo
de `inventory.py` e `test_inventory.py`) é o que permite à iteração 3 escrever um
`old_str` idêntico ao código real e raciocinar sobre `200 - 10 = 190`. O log mostra
exatamente essa mesma string que entra na `conversation`, não uma versão reformatada.

Um detalhe do código que afeta o contexto: quando a resposta tem tool call, o texto do
assistente (o Thought) **não é appendado** à `conversation`. Só o `tool_result` entra,
com `role: "user"`. O ramo que appenda a resposta como `role: "assistant"` só existe no
caminho "sem tool call" (`agent.py:325-329`). Na prática, o raciocínio que levou a uma
tool call (por exemplo, "I'll fix it" na iteração 3) não está no contexto da chamada
seguinte, só o resultado da ação está.

Um exemplo em outra execução de que ter a Observation no contexto não garante bom uso
dela: o agente chamou `list_files({"path": "."})` duas vezes seguidas, e o Thought da
segunda foi "A lista de arquivos não recebeu o caminho do diretório que eu tentei
especificar. Vou listar corretamente e então ler os arquivos relevantes.", mesmo com o
resultado da primeira chamada já presente na `conversation`.

## 3. Tools / ACI

As três tools (`read_file`, `list_files`, `edit_file`, registradas em `TOOL_REGISTRY`,
`agent.py:120-124`) são descritas em prosa no system prompt, com nome, docstring e
assinatura obtidas por `inspect`. O modelo chama uma tool escrevendo uma linha de texto:

```
tool: edit_file({"path": "...", "old_str": "...", "new_str": "..."})
```

e `extract_tool_invocations` (`agent.py:141-162`) a recupera com `startswith("tool:")`,
`split("(", 1)` e `json.loads`. É parsing de texto sobre uma convenção definida no
prompt, sem nenhum contrato verificável entre agente e modelo.

Comparação:

- **Parsing de texto (este agente)**: o modelo só precisa imitar um padrão. Qualquer
  desvio (a linha não começar em `tool:`, JSON em mais de uma linha, texto depois do
  parêntese final) faz a chamada ser ignorada em silêncio, e o código não tem como
  distinguir "o modelo não quis chamar tool" de "o modelo tentou e errou o formato".
- **JSON estruturado pedido no prompt**: melhora o parsing, mas continua sem garantia,
  porque o modelo ainda gera texto livre.
- **Tool calling nativo**: as tools são declaradas num campo próprio da requisição
  (`tools=[...]` com JSON Schema) e a chamada volta num campo próprio da resposta
  (`tool_calls`), já tipada e validada pelo provedor. Não há regex nem convenção de
  texto do lado do agente.

A execução principal mostra o custo dessa escolha logo na iteração 2: o modelo escreveu
`<tool_call>` antes das linhas corretas e `</tool_call>`, `<parameter= path> . </parameter>`
e `</invoke>` depois, resíduos do formato nativo para o qual foi treinado. Funcionou
porque as linhas `tool:` estavam intactas no meio.

## 4. Thought

O trecho mais claro de raciocínio que não gera tool call é o Thought da iteração 4 da
execução principal (resposta final), onde o modelo explica o conserto e faz a conta
`200 - (200 * 10 / 100) = 180`. O Thought da iteração 3 também é raciocínio explícito
("The test expects `apply_discount(200, 10)` to return 180, but the function returns
`200 - 10 = 190`"), mas esse termina em uma Action.

Outra execução tem um exemplo ainda melhor do passo que normalmente fica escondido. Na
iteração 4 dessa execução o Thought foi:

````
O bug está em `inventory.py`. A função `apply_discount` está subtraindo o valor
percentual diretamente do preço em vez de calcular o desconto correto.

Deve subtrair `price * (percent / 100)` em vez de apenas `price`. Vou corrigir:

```python
def apply_discount(price, percent):
````

Aqui o diagnóstico está correto, mas o modelo escreveu o conserto como texto em markdown
em vez de chamar `edit_file`, e a resposta foi cortada logo depois de
`def apply_discount(price, percent):`. Sem nenhuma linha `tool:`, o agente tratou isso
como resposta final. É um raciocínio que existiu, estava certo e não teve efeito algum
sobre o sistema de arquivos. Ferramentas prontas normalmente escondem esse texto, aqui
ele aparece no trace.

Também vale notar que em várias iterações o Thought é vazio (iteração 1 da execução
principal, por exemplo): o modelo nem sempre escreve raciocínio antes de agir. Quando
escreve, o raciocínio é reconhecimento de padrão, "desconto percentual" virando
`price * (1 - percent / 100)` ou equivalente, não prova matemática.

## 5. Guardrail

O agente não tem guardrail. Na execução principal ele leu os dois arquivos, editou
`inventory.py`, escreveu "Consertado" e parou, sem rodar o teste.

Pior que isso, ele não teria como rodar. O `TOOL_REGISTRY` (`agent.py:120-124`) só tem
`read_file`, `list_files` e `edit_file`. Não existe tool de execução (`bash`/`execute`).
A ausência de guardrail aqui é estrutural, não só comportamental: mesmo que o modelo
quisesse verificar o conserto, o harness não oferece o meio.

O que isso significou na prática:

- **Execução principal**: o conserto estava certo. Isso foi confirmado rodando `pytest`
  depois, fora do agente (1 passed). Mas o agente não sabia disso: a frase "satisfazendo
  o teste" é uma conta que ele fez, não um resultado observado. Se o conserto estivesse
  errado, o comportamento do agente seria idêntico.
- **Em 6 das 7 execuções o bug continuou no arquivo ao final**, e o agente parou do mesmo
  jeito, sem dar nenhum sinal de que algo estava pendente. Uma delas parou depois de
  listar o diretório duas vezes, outra depois de ler os dois arquivos e não editar nada,
  outra depois de escrever o conserto como markdown (seção 4), outra no primeiro turno
  com uma `<tool_call>` no formato nativo (seção 6).

Resposta direta à pergunta: sim, o agente pode parar achando que terminou sem ter
terminado, e fez isso na maioria das execuções. O critério de parada é "o modelo
respondeu sem tool call", que é uma decisão do próprio modelo, não uma condição
verificável pelo harness. Um guardrail real seria, por exemplo, rodar o teste ao final
e só parar com `1 passed`.

## 6. Falhas de parsing

O que o parser errou ou deixou passar, com base nas execuções:

1. **Resíduos do formato nativo em volta de chamadas válidas** (execução principal,
   iteração 2): `<tool_call>` antes e `</tool_call>`, `<parameter= path> . </parameter>`,
   `</invoke>` depois. O parser extraiu corretamente as duas linhas `tool:` e ignorou o
   resto. O trecho depois da última `tool:` foi flagado pelo instrumentador
   (`[PARSING] texto encontrado após a última linha 'tool:'`, `agent.py:315-319`). Falha
   de formato do modelo, sem falha do parser.
2. **Resposta inteira no formato nativo do modelo, nenhuma linha `tool:`** (outra
   execução, iteração 1): o modelo respondeu
   ```
   I'll help you find and fix the bug. Let me start by exploring the project structure and reading the test file.

   <tool_call>
   <function=list_files>
   {"path": ""}
   </function>
   </tool_call>
   ```
   O parser não encontrou nenhuma linha que comece com `tool:`, devolveu lista vazia, e o
   agente tratou a resposta como final. Essa é a falha mais grave do conjunto: uma
   intenção clara de chamar `list_files` foi descartada e a execução terminou no primeiro
   turno, sem nada executado. O detector `[PARSING]` de `agent.py:297-301` **não
   disparou**, porque ele procura a substring `tool:` e aqui só existe `tool_call`.
   Ou seja, é uma falha que nem a instrumentação desta atividade enxerga, só dá para ver
   lendo o Thought.
3. **Conserto escrito como prosa em vez de `edit_file`** (outra execução, iteração 4,
   seção 4): sem nenhuma linha `tool:` e sem a substring `tool:`, o parser e o
   instrumentador não têm o que apontar, e a execução é encerrada como "final" com o bug
   intacto. Tecnicamente não é erro do parser, é um desvio de formato do modelo que o
   harness não consegue distinguir de uma resposta legítima.
4. **Chamada repetida sem progresso** (outra execução, iterações 1 e 2, seção 2): não é
   falha de parsing, mas é falha da ACI. O modelo emitiu `list_files` duas vezes com os
   mesmos argumentos, e a segunda Observation foi idêntica à primeira.

Detalhes que não aconteceram, registrados porque a ausência também é dado: o detector de
descarte parcial (`agent.py:307-312`, mais linhas `tool:` do que invocações válidas) não
disparou em nenhuma das 7 execuções, ou seja, não houve JSON quebrado em uma linha
`tool:` que o parser tenha descartado em silêncio. Nas execuções inspecionadas em
detalhe as chamadas à API também não falharam com erro, então o mecanismo de retry
(`agent.py:223-255`) não foi acionado.

Em resumo, os problemas de formato aparecem nos três pontos em que o harness depende de
o modelo imitar uma convenção de texto: no começo da resposta (`<tool_call>` antes das
linhas), no meio (linha `tool:` não é a primeira coisa na linha) e no fim (resíduos
depois da última chamada), além do caso em que o modelo abandona a convenção por
completo. Tool calling nativo elimina essa classe inteira de falha porque a chamada não
passa por texto.
