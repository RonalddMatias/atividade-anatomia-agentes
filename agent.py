import inspect
import json
import os

from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Dict, List, Tuple

load_dotenv()

openai_client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)


SYSTEM_PROMPT = """
You are a coding assistant whose goal it is to help us solve coding tasks.
You can perform actions by emitting a single command line in exactly this format, and nothing else on that line:

tool: NAME({{"arg": "value"}})

Do not use JSON function-calling, a <tool_call> tag, or any other structured tool-call format your training may default to.
The ONLY format the system running you understands is the plain text line above.

Available commands:

{tool_list_repr}

Example of a correct response when you want to read a file named 'notes.txt':
tool: read_file({{"filename": "notes.txt"}})

Use compact single-line JSON with double quotes. After receiving a tool_result(...) message, continue the task using the same format when another action is needed.
If no action is needed, respond in plain prose.
"""


YOU_COLOR = "\u001b[94m"
ASSISTANT_COLOR = "\u001b[93m"
RESET_COLOR = "\u001b[0m"

def resolve_abs_path(path_str: str) -> Path:
    """
    file.py -> /Users/home/mihail/modern-software-dev-lectures/file.py
    """
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path

def read_file_tool(filename: str) -> Dict[str, Any]:
    """
    Gets the full content of a file provided by the user.
    :param filename: The name of the file to read.
    :return: The full content of the file.
    """
    full_path = resolve_abs_path(filename)
    print(full_path)
    with open(str(full_path), "r") as f:
        content = f.read()
    return {
        "file_path": str(full_path),
        "content": content
    }

def list_files_tool(path: str) -> Dict[str, Any]:
    """
    Lists the files in a directory provided by the user.
    :param path: The path to a directory to list files from.
    :return: A list of files in the directory.
    """
    full_path = resolve_abs_path(path)
    all_files = []
    for item in full_path.iterdir():
        all_files.append({
            "filename": item.name,
            "type": "file" if item.is_file() else "dir"
        })
    return {
        "path": str(full_path),
        "files": all_files
    }

def edit_file_tool(path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """
    Replaces first occurrence of old_str with new_str in file. If old_str is empty,
    create/overwrite file with new_str.
    :param path: The path to the file to edit.
    :param old_str: The string to replace.
    :param new_str: The string to replace with.
    :return: A dictionary with the path to the file and the action taken.
    """
    full_path = resolve_abs_path(path)
    if old_str == "":
        full_path.write_text(new_str, encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "created_file"
        }
    original = full_path.read_text(encoding="utf-8")
    if original.find(old_str) == -1:
        return {
            "path": str(full_path),
            "action": "old_str not found"
        }
    edited = original.replace(old_str, new_str, 1)
    full_path.write_text(edited, encoding="utf-8")
    return {
        "path": str(full_path),
        "action": "edited"
    }


TOOL_REGISTRY = {
    "read_file": read_file_tool,
    "list_files": list_files_tool,
    "edit_file": edit_file_tool
}

def get_tool_str_representation(tool_name: str) -> str:
    tool = TOOL_REGISTRY[tool_name]
    return f"""
    Name: {tool_name}
    Description: {tool.__doc__}
    Signature: {inspect.signature(tool)}
    """

def get_full_system_prompt():
    tool_str_repr = ""
    for tool_name in TOOL_REGISTRY:
        tool_str_repr += "TOOL\n===" + get_tool_str_representation(tool_name)
        tool_str_repr += f"\n{'=' * 15}\n"
    return SYSTEM_PROMPT.format(tool_list_repr=tool_str_repr)

def extract_tool_invocations(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Return list of (tool_name, args) requested in 'tool: name({...})' lines.
    The parser expects single-line, compact JSON in parentheses.
    """
    invocations = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("tool:"):
            continue
        try:
            after = line[len("tool:"):].strip()
            name, rest = after.split("(", 1)
            name = name.strip()
            if not rest.endswith(")"):
                continue
            json_str = rest[:-1].strip()
            args = json.loads(json_str)
            invocations.append((name, args))
        except Exception:
            continue
    return invocations

TRACE_FILE_PATH = Path(__file__).resolve().parent / "trace.md"
MAX_OBSERVATION_CHARS = 2000

def start_trace():
    """Zera trace.md no início de cada execução, para o arquivo sempre refletir só a última run."""
    TRACE_FILE_PATH.write_text("# Trace da execução\n", encoding="utf-8")

def log_trace(block: str):
    """Imprime no terminal e grava o mesmo bloco em trace.md, para termos as duas formas pedidas no README."""
    print(block)
    with open(TRACE_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(block + "\n")

def truncate(text: str) -> str:
    """Evita que uma Observation gigante (ex.: list_files em '.') deixe o trace ilegível."""
    if len(text) <= MAX_OBSERVATION_CHARS:
        return text
    omitted = len(text) - MAX_OBSERVATION_CHARS
    return text[:MAX_OBSERVATION_CHARS] + f"\n[...truncado, {omitted} caracteres omitidos...]"

def split_thought_and_tool_lines(text: str):
    """
    Separa a resposta bruta do LLM em (thought, tool_lines, trailing):
    - thought: texto antes da primeira linha 'tool: ...'. Se não houver nenhuma,
      a resposta inteira é o thought (é a resposta final da tarefa), regra tirada
      literalmente do README: "o texto do modelo antes da chamada de tool ou da
      resposta final".
    - tool_lines: as linhas cruas que começam com 'tool:', na ordem em que aparecem
      no texto (o prompt pede exatamente uma, mas o modelo nem sempre obedece).
    - trailing: texto que sobra depois da ÚLTIMA linha 'tool:'. O formato pedido no
      prompt não permite nada depois da tool call, então texto aqui é sinal de
      resposta fora do formato esperado.
    """
    lines = text.splitlines()
    tool_idxs = [i for i, line in enumerate(lines) if line.strip().startswith("tool:")]
    if not tool_idxs:
        return text.strip(), [], ""
    thought = "\n".join(lines[:tool_idxs[0]]).strip()
    tool_lines = [lines[i].strip() for i in tool_idxs]
    trailing = "\n".join(lines[tool_idxs[-1] + 1:]).strip()
    return thought, tool_lines, trailing

def execute_llm_call(conversation: List[Dict[str, str]]):
    response = openai_client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=conversation,
        max_tokens=2000
    )
    message = response.choices[0].message
    # Modelos de raciocínio servidos pela Groq podem devolver um campo `reasoning`
    # separado de `content`. O código original só lia `content`, então juntamos os
    # dois para não descartar texto que o modelo de fato gerou. Para modelos sem
    # esse campo, o resultado é idêntico a ler só `content`.
    reasoning = getattr(message, "reasoning", None) or ""
    content = message.content or ""
    return (reasoning + ("\n" + content if content else "")).strip()

MAX_LLM_CALL_ATTEMPTS = 3

def execute_llm_call_with_retry(conversation: List[Dict[str, str]]):
    """
    Modelos pós-treinados para tool calling nativo podem tentar responder pelo canal
    nativo da API, e a API pode rejeitar isso com um erro 400 antes de qualquer
    texto voltar. Isso não é uma falha de extract_tool_invocations (o texto nem
    chega a existir). Aqui só evitamos que isso derrube o programa com um traceback
    ilegível: tentamos de novo (a amostragem é probabilística) e, se todas as
    tentativas falharem, devolvemos None para o chamador decidir como encerrar.
    Toda tentativa falha é logada no trace, nada fica escondido.
    """
    last_error = None
    for attempt in range(1, MAX_LLM_CALL_ATTEMPTS + 1):
        try:
            return execute_llm_call(conversation), None
        except Exception as exc:
            last_error = exc
            msg = (
                f"\n[FALHA] tentativa {attempt}/{MAX_LLM_CALL_ATTEMPTS} de chamada ao "
                f"LLM falhou antes de retornar texto: {exc}"
            )
            # A Groq às vezes devolve, dentro do próprio erro, o raciocínio interno
            # que o modelo gerou antes de travar (campo "failed_generation"). Não é
            # uma resposta válida, nunca vira uma Action de verdade, mas é texto de
            # Thought real que a API deixou vazar, então vale capturar em vez de
            # descartar junto com o erro.
            failed_generation = getattr(exc, "body", None)
            if isinstance(failed_generation, dict) and failed_generation.get("failed_generation"):
                msg += (
                    "\n[THOUGHT PARCIAL VAZADO PELO ERRO] "
                    f"{failed_generation['failed_generation']!r}"
                )
            log_trace(msg)
    return None, last_error

def run_coding_agent_loop():
    print(get_full_system_prompt())
    start_trace()
    conversation = [{
        "role": "system",
        "content": get_full_system_prompt()
    }]
    iteration = 0
    while True:
        try:
            user_input = input(f"{YOU_COLOR}You:{RESET_COLOR}:")
        except (KeyboardInterrupt, EOFError):
            break
        conversation.append({
            "role": "user",
            "content": user_input.strip()
        })
        # Este while interno É o loop do agente: uma volta = uma chamada ao LLM.
        # Ele só para quando o próprio modelo responde sem nenhuma tool call,
        # não existe, hoje, nenhuma verificação externa que confirme se a tarefa
        # foi de fato concluída antes de parar (ausência de guardrail).
        while True:
            iteration += 1
            assistant_response, error = execute_llm_call_with_retry(conversation)
            if assistant_response is None:
                log_trace(
                    f"\n[FALHA IRRECUPERAVEL] todas as {MAX_LLM_CALL_ATTEMPTS} tentativas de "
                    f"chamada ao LLM falharam nesta iteracao, execucao encerrada sem resposta "
                    f"do modelo. Ultimo erro: {error}"
                )
                print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR}: [falha irrecuperável, ver trace.md]")
                return
            thought, tool_lines, trailing = split_thought_and_tool_lines(assistant_response)
            tool_invocations = extract_tool_invocations(assistant_response)

            block = [f"\n## Iteracao {iteration}", "\n**Thought:**", thought or "_(vazio)_"]

            # Falha de parsing tipo 1: a resposta tem "tool:" mas nem uma linha nesse
            # formato foi reconhecida por extract_tool_invocations (ex.: o modelo
            # escreveu "tool:" no meio de uma frase, e não como início de linha).
            if not tool_lines and "tool:" in assistant_response:
                block.append(
                    "\n[PARSING] a resposta contém a palavra 'tool:' mas nenhuma linha "
                    "no formato esperado foi encontrada, tratada como resposta final."
                )

            # Falha de parsing tipo 2: havia N linhas 'tool: ...' reconhecíveis, mas
            # extract_tool_invocations só conseguiu extrair M < N (ex.: JSON quebrado
            # em alguma delas). Isso descarta silenciosamente uma ação que o modelo
            # pretendia executar.
            if tool_lines and len(tool_lines) != len(tool_invocations):
                block.append(
                    f"\n[PARSING] {len(tool_lines)} linha(s) 'tool:' encontradas no texto, "
                    f"mas apenas {len(tool_invocations)} foram reconhecidas como chamadas "
                    "válidas, pelo menos uma foi descartada silenciosamente pelo parser."
                )

            # Texto sobrando depois da última tool call: fora do formato pedido no prompt.
            if trailing:
                block.append(
                    f"\n[PARSING] texto encontrado após a última linha 'tool:' (ignorado "
                    f"pelo parser): {trailing!r}"
                )

            if not tool_invocations:
                block.append("\n_(sem tool call, resposta tratada como final da tarefa)_")
                log_trace("\n".join(block))
                print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR}: {assistant_response}")
                conversation.append({
                    "role": "assistant",
                    "content": assistant_response
                })
                break

            log_trace("\n".join(block))

            for name, args in tool_invocations:
                tool = TOOL_REGISTRY[name]
                resp = ""
                print(name, args)
                if name == "read_file":
                    resp = tool(args.get("filename", "."))
                elif name == "list_files":
                    resp = tool(args.get("path", "."))
                elif name == "edit_file":
                    resp = tool(args.get("path", "."),
                                args.get("old_str", ""),
                                args.get("new_str", ""))
                # É exatamente esta string que volta para a conversa (contexto) e que
                # o LLM vai ler na próxima chamada, por isso o log mostra o mesmo
                # texto que é appendado abaixo, e não uma versão só "bonitinha" dele.
                result_str = f"tool_result({json.dumps(resp)})"
                action_block = (
                    f"\n**Action:** `tool: {name}({json.dumps(args)})`"
                    f"\n\n**Observation:**\n```\n{truncate(result_str)}\n```"
                )
                log_trace(action_block)
                conversation.append({
                    "role": "user",
                    "content": result_str
                })


if __name__ == "__main__":
    run_coding_agent_loop()
