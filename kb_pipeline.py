"""
OMEGA KB Pipeline
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
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"processed_messages": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_chats():
    try:
        r = requests.get(f"{OPENWEBUI_URL}/api/v1/chats/", headers=HEADERS, verify=False, timeout=10)
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
        r = requests.get(f"{OPENWEBUI_URL}/api/v1/chats/{chat_id}", headers=HEADERS, verify=False, timeout=10)
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


def extract_kb_content(text):
    if "[KB]" in text:
        return text
    return None


def save_to_kb(content, title):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:50]
    filename = os.path.join(KB_PATH, f"{safe_title}_{timestamp}.txt")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"Salvo: {filename}")
        return True
    except Exception as e:
        log(f"Erro ao salvar {filename}: {e}")
        return False


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

            # Processa so mensagens do assistente
            role = msg.get("role", "")
            if role != "assistant":
                processed[msg_id] = True
                continue

            # Extrai conteudo
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join([c.get("text", "") for c in content if isinstance(c, dict)])

            kb_content = extract_kb_content(content)
            if kb_content:
                title = chat.get("title", "OMEGA_KB")
                if save_to_kb(kb_content, title):
                    new_saves += 1
                    log(f"[KB] detectado e salvo do chat: {chat.get('title', chat_id)}")

            processed[msg_id] = True

        processed[f"chat_{chat_id}_updated"] = chat_updated

    state["processed_messages"] = processed
    if new_saves > 0:
        log(f"Total de novos saves neste ciclo: {new_saves}")
    return state


def main():
    log("OMEGA KB Pipeline iniciando...")
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
