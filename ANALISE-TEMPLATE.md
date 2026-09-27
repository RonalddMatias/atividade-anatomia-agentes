# Análise: anatomia do agente

> Copie este arquivo para `ANALISE.md`. Cole o trace completo (de `trace.md` ou do terminal)
> na seção "Trace anotado" abaixo, e insira notas começando com `>>` logo ao lado ou abaixo
> de cada trecho relevante, identificando o componente correspondente. Depois preencha as
> seis seções de discussão com base nesse trace real.

## Tarefa dada ao agente

```
encontre e conserte o bug baseado no teste que está falhando em test_inventory.py
```

## Trace anotado

<!--
Cole aqui o conteúdo de trace.md (ou do terminal) gerado por uma execução real de
`python agent.py`. Ao lado (ou logo abaixo) de cada trecho relevante, insira uma nota
começando com `>>`, por exemplo:

## Iteracao 1

**Thought:**
Preciso entender a tarefa antes de agir...
>> Thought: raciocínio do modelo antes de decidir a ação, não vira tool call.

**Action:** `tool: read_file({"filename": "inventory.py"})`
>> Action / Tools (ACI): chamada de ferramenta no formato texto "tool: nome({...})",
>> parseada por extract_tool_invocations via regex/split, não por tool calling nativo.

**Observation:**
```
tool_result({"file_path": "...", "content": "def apply_discount(...): ..."})
```
>> Observation: resultado bruto da tool, exatamente como ele volta para a `conversation`
>> (contexto) e passa a fazer parte do que o LLM vê na chamada seguinte.
-->

## 1. Loop

<!-- Escolha uma iteração completa do trace e explique: o que a compõe (uma chamada ao
LLM, que pode conter 0, 1 ou várias tool calls), o que faz o laço continuar (houve tool
call) e o que faria o laço parar (resposta sem nenhuma tool call). -->

## 2. Contexto

<!-- Aponte, no trace, o momento exato em que o resultado de uma tool (Observation)
volta para a `conversation` e passa a ser lido pelo LLM na chamada seguinte. Comente
também o que NÃO volta para o contexto (ex.: o raciocínio do modelo antes de uma tool
call, quando a resposta tem tool call, nunca é appendado à `conversation` no código
atual — isso é uma limitação de contexto, não um bug do seu log). -->

## 3. Tools / ACI

<!-- Mostre uma chamada de tool real do trace e explique o formato usado: texto solto
("tool: nome({...})") parseado por regex/split em `extract_tool_invocations`, contraste
com JSON estruturado (mais verificável, ainda não tipado) e com tool calling nativo
(schema tipado e validado pelo provedor, sem parsing de texto do seu lado). -->

## 4. Thought

<!-- Aponte um trecho de raciocínio do trace que NÃO gerou nenhuma chamada de tool
(pode ser um Thought no meio da tarefa, ou a resposta final). Comente por que esse tipo
de raciocínio costuma ficar escondido em ferramentas prontas (elas não expõem o texto
bruto do modelo, só o resultado da ação). -->

## 5. Guardrail

<!-- O item mais importante. O agente não roda o teste nem verifica se o problema foi
resolvido antes de parar. Baseado na sua execução real: o agente rodou pytest por
conta própria? Ele parou achando que tinha terminado sem de fato ter confirmado isso?
O que aconteceria se a "correção" dele estivesse errada — ele perceberia? -->

## 6. Falhas de parsing

<!-- O que o parser (extract_tool_invocations) errou ou deixou passar na sua execução?
Se seu trace.md registrou algum aviso "[PARSING]", cole o trecho aqui e explique o que
aconteceu. Se não houve nenhuma falha, diga isso explicitamente — também é um dado
relevante (modelos gratuitos seguem o formato com menos consistência, então a ausência
de falha em uma execução não garante que ela não aconteça em outra). -->
