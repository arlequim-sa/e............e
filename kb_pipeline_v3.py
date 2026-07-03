"""
OMEGA KB Pipeline v3
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
POLL_INTERVAL = 30
LOG_FILE = "D:\\OMEGA\\kb_pipeline.log"

HEADERS = {
    "Authorization": "Bearer " + OPENWEBUI_API_KEY,
    "Content-Type": "application/json"
}

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def log(msg):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Sanitize msg - remove non-ASCII
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        line = "[" + timestamp + "] " + safe_msg + "\n"
        with open(LOG_FILE, "a", encoding="ascii", errors="replace") as f:
            f.write(line)
    except Exception:
        pass


def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"processed_messages": {}}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=True)
    except Exception as e:
        log("save_state error: " + str(e))


def get_chats():
    try:
        r = requests.get(
            OPENWEBUI_URL + "/api/v1/chats/",
            headers=HEADERS,
            verify=False,
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        else:
            log("Erro ao buscar chats: " + str(r.status_code))
            return []
    except Exception as e:
        log("Excecao ao buscar chats: " + str(e))
        return []


def get_chat_messages(chat_id):
    try:
        r = requests.get(
            OPENWEBUI_URL + "/api/v1/chats/" + chat_id,
            headers=HEADERS,
            verify=False,
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            messages = data.get("chat", {}).get("messages", [])
            return messages
        else:
            log("Erro ao buscar mensagens: " + str(r.status_code))
            return []
    except Exception as e:
        log("Excecao ao buscar mensagens: " + str(e))
        return []


def clean_text(text):
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        return text.encode("ascii", "replace").decode("ascii")
    except Exception:
        return "unknown"


def extract_text(content):
    try:
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
    except Exception:
        pass
    return ""


def save_to_kb(content, title):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = clean_text(title)
        safe_title = re.sub(r'[^a-zA-Z0-9_\-\s]', '_', safe_title).strip()
        safe_title = re.sub(r'\s+', '_', safe_title)[:50]
        if not safe_title:
            safe_title = "OMEGA_KB"
        filename = os.path.join(KB_PATH, safe_title + "_" + timestamp + ".txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        log("Salvo: " + filename)
        return True
    except Exception as e:
        log("Erro ao salvar: " + str(e))
        return False


def process_chats(state):
    chats = get_chats()
    processed = state.get("processed_messages", {})
    new_saves = 0

    for chat in chats:
        try:
            chat_id = str(chat.get("id", ""))
            if not chat_id:
                continue

            chat_updated = chat.get("updated_at", 0)
            last_check = processed.get("chat_" + chat_id + "_updated", 0)

            if chat_updated <= last_check:
                continue

            messages = get_chat_messages(chat_id)

            for msg in messages:
                try:
                    msg_id = str(msg.get("id", ""))
                    if not msg_id:
                        continue

                    if msg_id in processed:
                        continue

                    processed[msg_id] = True

                    role = msg.get("role", "")
                    if role != "assistant":
                        continue

                    content = extract_text(msg.get("content", ""))

                    if "[KB]" not in content:
                        continue

                    chat_title = str(chat.get("title", "OMEGA_KB"))
                    if save_to_kb(content, chat_title):
                        new_saves += 1
                        log("[KB] salvo do chat: " + clean_text(chat_title)[:50])

                except Exception as e:
                    log("Erro ao processar mensagem: " + str(e))
                    continue

            processed["chat_" + chat_id + "_updated"] = chat_updated

        except Exception as e:
            log("Erro ao processar chat: " + str(e))
            continue

    state["processed_messages"] = processed

    if new_saves > 0:
        log("Total saves neste ciclo: " + str(new_saves))

    return state


def main():
    log("OMEGA KB Pipeline v3 iniciando...")
    log("Monitorando: " + OPENWEBUI_URL)
    log("Salvando em: " + KB_PATH)
    log("Intervalo: " + str(POLL_INTERVAL) + "s")

    os.makedirs(KB_PATH, exist_ok=True)
    state = load_state()

    while True:
        try:
            state = process_chats(state)
            save_state(state)
        except Exception as e:
            log("Erro no ciclo principal: " + str(e))
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
