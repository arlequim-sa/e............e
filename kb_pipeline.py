"""
OMEGA KB Pipeline v2
Monitora conversas do Open WebUI e salva conteudo [KB] automaticamente em D:\OMEGA\KB\
Roda em background no FIRULLADO
"""

import requests
import time
import os
import re
import json
from datetime import datetime

# Configuracao
OPENWEBUI_URL = "https://firullado.tail0d10b0.ts.net"
OPENWEBUI_API_KEY = "sk-87c532ac9285472c9444a0b70b5239d2"
KB_PATH = "D:\\OMEGA\\KB"
STATE_FILE = "D:\\OMEGA\\kb_pipeline_state.json"
POLL_INTERVAL = 30  # segundos entre verificacoes
LOG_FILE = "D:\\OMEGA\\kb_pipeline.log"

HEADERS = {
    "Authorization": f"Bearer {OPENWEBUI_API_KEY}",
    "Content-Type": "application/json"
}


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        with open(LOG_FILE, "a", encoding="ascii", errors="ignore") as f:
            f.write(line + "\n")


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"processed_messages": {}}
    return {"processed_messages": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=True)


def get_chats():
    try:
        r = requests.get(
            f"{OPENWEBUI_URL}/api/v1/chats/",
            headers=HEADERS,
            verify=False,
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        else:
            log(f"Erro ao buscar chats: {r.status_code}")
            return []
    except Exception as e:
        log(f"Excecao ao buscar chats: {e}")
        return []


def get_chat_messages(chat_id):
    try:
        r = requests.get(
            f"{OPENWEBUI_URL}/api/v1/chats/{chat_id}",
            headers=HEADERS,
            verify=False,
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            messages = data.get("chat", {}).get("messages", [])
            return messages
        else:
            log(f"Erro ao buscar mensagens do chat {chat_id}: {r.status_code}")
            return []
    except Exception as e:
        log(f"Excecao ao buscar mensagens: {e}")
        return []


def clean_title(title):
    # Remove emojis e caracteres nao-ASCII
    ascii_title = title.encode('ascii', 'ignore').decode('ascii')
    # Remove caracteres invalidos para nome de arquivo
    safe_title = re.sub(r'[^a-zA-Z0-9_\-\s]', '_', ascii_title).strip()
    # Substitui espacos por underscore e limita tamanho
    safe_title = re.sub(r'\s+', '_', safe_title)[:50]
    return safe_title if safe_title else "OMEGA_KB"


def save_to_kb(content, title):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = clean_title(title)
    filename = os.path.join(KB_PATH, f"{safe_title}_{timestamp}.txt")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"Salvo: {filename}")
        return True
    except Exception as e:
        log(f"Erro ao salvar {filename}: {e}")
        return False


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts)
    return ""


def process_chats(state):
    chats = get_chats()
    processed = state.get("processed_messages", {})
    new_saves = 0

    for chat in chats:
        chat_id = chat["id"]
        chat_updated = chat.get("updated_at", 0)

        # Pula chats que nao foram atualizados desde a ultima verificacao
        last_check = processed.get(f"chat_{chat_id}_updated", 0)
        if chat_updated <= last_check:
            continue

        messages = get_chat_messages(chat_id)

        for msg in messages:
            msg_id = msg.get("id", "")
            if not msg_id:
                continue

            # Pula mensagens ja processadas
            if msg_id in processed:
                continue

            # Marca como processada independente do resultado
            processed[msg_id] = True

            # Processa so mensagens do assistente
            role = msg.get("role", "")
            if role != "assistant":
                continue

            # Extrai conteudo da mensagem
            content = extract_text(msg.get("content", ""))

            # Detecta [KB] APENAS no conteudo da mensagem, nao no titulo
            if "[KB]" not in content:
                continue

            # Salva o conteudo
            chat_title = chat.get("title", "OMEGA_KB")
            if save_to_kb(content, chat_title):
                new_saves += 1
                log(f"[KB] detectado e salvo — chat: {chat_title[:50]}")

        processed[f"chat_{chat_id}_updated"] = chat_updated

    state["processed_messages"] = processed
    if new_saves > 0:
        log(f"Total de novos saves neste ciclo: {new_saves}")
    return state


def main():
    log("OMEGA KB Pipeline v2 iniciando...")
    log(f"Monitorando: {OPENWEBUI_URL}")
    log(f"Salvando em: {KB_PATH}")
    log(f"Intervalo: {POLL_INTERVAL}s")

    os.makedirs(KB_PATH, exist_ok=True)
    state = load_state()

    while True:
        try:
            state = process_chats(state)
            save_state(state)
        except Exception as e:
            log(f"Erro no ciclo principal: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
