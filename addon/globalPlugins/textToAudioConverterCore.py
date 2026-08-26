# -*- coding: utf-8 -*-
import base64
import hashlib
import os
import socket
import ssl
import struct
import re
import time
import unicodedata
import uuid
from pathlib import Path

from pypdf import PdfReader


# Current Edge Read Aloud protocol values (August 2026).
TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
CHROMIUM_FULL_VERSION = "143.0.3650.75"
SEC_MS_GEC_VERSION = "1-" + CHROMIUM_FULL_VERSION

WSS_URL = (
    "wss://speech.platform.bing.com/consumer/speech/synthesize/"
    "readaloud/edge/v1?TrustedClientToken=" + TRUSTED_CLIENT_TOKEN
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
)

ORIGIN = "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold"

MAX_TTS_BYTES = 3800
RETRIES = 4


class ConverterError(Exception):
    pass


def _clean_display_text(text):
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)

    replacements = {
        "\u00ad": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
        "￾": "",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "–": "-",
        "—": "-",
        "―": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "•": "-",
        "·": "-",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = "".join(
        char for char in text
        if unicodedata.category(char)[0] != "C"
    )

    text = re.sub(r'[<>:"/\\|?*]', " - ", text)
    text = re.sub(r"[\[\]{}]+", " ", text)
    text = re.sub(r"\s*[-–—]{2,}\s*", " - ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-_")

    return text


def _safe_name(name):
    name = _clean_display_text(name) or "Sem título"

    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    if name.upper() in reserved:
        name = "_" + name

    return name[:100].rstrip(" .")


def _clean_pdf_text(text):
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "").replace("\xa0", " ").replace("￾", "")

    # Caracteres de controle não aceitos pelo serviço.
    text = "".join(
        " " if (ord(c) <= 8 or 11 <= ord(c) <= 12 or 14 <= ord(c) <= 31) else c
        for c in text
    )

    # Palavras quebradas por hífen entre linhas.
    text = re.sub(
        r"([A-Za-zÀ-ÿ])-+\s*\n\s*([A-Za-zÀ-ÿ])",
        r"\1\2",
        text,
    )

    # Números isolados de página.
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)

    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    return text.strip()


def _extract_pages(pdf_path, progress, cancel_event):
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as error:
        raise ConverterError(f"Não foi possível abrir o PDF: {error}")

    total = len(reader.pages)
    if total == 0:
        raise ConverterError("O PDF não possui páginas.")

    progress(f"Lendo PDF com {total} páginas.")

    pages = []
    for number, page in enumerate(reader.pages, start=1):
        if cancel_event.is_set():
            return []

        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        pages.append(_clean_pdf_text(text))

        if number == 1 or number == total or number % 25 == 0:
            progress(f"Leitura do PDF: página {number} de {total}.")

    sample = " ".join(pages[: min(10, len(pages))]).strip()
    if len(sample) < 200:
        raise ConverterError(
            "O PDF contém pouco texto extraível. "
            "Se for digitalizado, aplique OCR antes."
        )

    return pages


def _split_by_pages(pages, count):
    sections = []
    start = 0
    part = 1

    while start < len(pages):
        end = min(start + count, len(pages))
        text = "\n\n".join(pages[start:end]).strip()

        if text:
            sections.append(
                (f"Parte {part:02d} - Páginas {start + 1} a {end}", text)
            )

        start = end
        part += 1

    return sections


def _detect_chapters(pages):
    patterns = [
        r"^\s*cap[ií]tulo\s+\d+\b.*",
        r"^\s*\d{1,2}\s*[.\-:)]\s+\S.*",
        r"^\s*parte\s+[ivxlcdm\d]+\b.*",
    ]

    candidates = []

    for index, text in enumerate(pages):
        if not text:
            continue

        beginning = text[:300].strip()
        first = re.split(r"(?<=[.!?])\s+", beginning)[0].strip()

        if not first or len(first) > 160:
            continue

        for pattern in patterns:
            if re.match(pattern, first, re.IGNORECASE):
                candidates.append((index, first))
                break

    filtered = []
    previous = -99

    for index, title in candidates:
        if index - previous >= 2:
            filtered.append((index, title))
            previous = index

    if len(filtered) < 2:
        return None

    sections = []

    if filtered[0][0] > 0:
        intro = "\n\n".join(pages[: filtered[0][0]]).strip()
        if intro:
            sections.append(("Introdução", intro))

    for position, (start, title) in enumerate(filtered):
        end = (
            filtered[position + 1][0]
            if position + 1 < len(filtered)
            else len(pages)
        )

        text = "\n\n".join(pages[start:end]).strip()
        if not text:
            continue

        title = _clean_display_text(title)

        title = re.sub(
            r"^cap[ií]tulo\s+\d+\s*[:.\-)]*\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(
            r"^\d{1,3}\s*[:.\-)]\s*",
            "",
            title,
        ).strip()

        name = f"Capítulo {position + 1:02d}"
        if title:
            name += f" - {title}"

        sections.append((_safe_name(name), text))

    return sections


def _split_utf8(text, byte_limit=MAX_TTS_BYTES):
    text = text.strip()

    while text:
        encoded = text.encode("utf-8")

        if len(encoded) <= byte_limit:
            yield text
            return

        cut = byte_limit
        while cut > 0:
            try:
                prefix = encoded[:cut].decode("utf-8")
                break
            except UnicodeDecodeError:
                cut -= 1

        split = max(
            prefix.rfind(". "),
            prefix.rfind("? "),
            prefix.rfind("! "),
            prefix.rfind("; "),
            prefix.rfind(", "),
            prefix.rfind(" "),
        )

        if split < 200:
            split = len(prefix)
        else:
            split += 1

        part = prefix[:split].strip()
        if part:
            yield part

        consumed = len(prefix[:split].encode("utf-8"))
        text = encoded[consumed:].decode("utf-8").strip()


def _windows_filetime_token():
    # Windows epoch difference: 1601 to 1970 in seconds.
    win_epoch = 11644473600
    ticks = int(time.time()) + win_epoch
    ticks -= ticks % 300
    ticks_100ns = ticks * 10_000_000

    value = f"{ticks_100ns}{TRUSTED_CLIENT_TOKEN}".encode("ascii")
    return hashlib.sha256(value).hexdigest().upper()


def _timestamp():
    return time.strftime(
        "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
        time.gmtime(),
    )



def _xml_escape(text):
    """Escapa os cinco caracteres necessários para texto em XML/SSML."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def _make_ssml(text, voice, rate):
    safe = _xml_escape(text)
    return (
        "<speak version='1.0' "
        "xmlns='http://www.w3.org/2001/10/synthesis' "
        "xml:lang='pt-BR'>"
        f"<voice name='{voice}'>"
        f"<prosody pitch='+0Hz' rate='{rate}' volume='+0%'>"
        f"{safe}"
        "</prosody></voice></speak>"
    )


def _parse_headers(block):
    headers = {}
    for line in block.split(b"\r\n"):
        if b":" in line:
            key, value = line.split(b":", 1)
            headers[key.strip().lower()] = value.strip().lower()
    return headers


_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConverterError("A conexão com o serviço de voz foi encerrada.")
        data.extend(chunk)
    return bytes(data)


def _build_client_frame(opcode, payload=b""):
    """Cria um frame WebSocket RFC 6455 mascarado."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    first = 0x80 | (opcode & 0x0F)
    length = len(payload)
    mask = os.urandom(4)

    if length < 126:
        header = bytes((first, 0x80 | length))
    elif length <= 0xFFFF:
        header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
    else:
        header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)

    masked = bytes(
        byte ^ mask[index % 4]
        for index, byte in enumerate(payload)
    )
    return header + mask + masked


def _read_frame(sock):
    first, second = _recv_exact(sock, 2)
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F

    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]

    mask = _recv_exact(sock, 4) if masked else None
    payload = _recv_exact(sock, length) if length else b""

    if mask:
        payload = bytes(
            byte ^ mask[index % 4]
            for index, byte in enumerate(payload)
        )

    return fin, opcode, payload


class _WebSocketConnection:
    """Cliente WebSocket mínimo para a conexão usada pelo complemento."""

    def __init__(self, sock):
        self.sock = sock
        self._closed = False

    @classmethod
    def connect(cls, url, origin, user_agent, timeout=60):
        if not url.startswith("wss://"):
            raise ConverterError("O endereço do serviço de voz não é seguro.")

        remainder = url[len("wss://"):]
        host, separator, path = remainder.partition("/")
        if not separator:
            path = ""
        path = "/" + path

        raw = None
        tls = None

        try:
            raw = socket.create_connection((host, 443), timeout=timeout)
            context = ssl.create_default_context()
            tls = context.wrap_socket(raw, server_hostname=host)
            tls.settimeout(timeout)

            key = base64.b64encode(os.urandom(16)).decode("ascii")
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                f"Origin: {origin}\r\n"
                "Pragma: no-cache\r\n"
                "Cache-Control: no-cache\r\n"
                "Accept-Language: en-US,en;q=0.9\r\n"
                f"User-Agent: {user_agent}\r\n"
                "\r\n"
            )
            tls.sendall(request.encode("ascii"))

            response = bytearray()
            while b"\r\n\r\n" not in response:
                chunk = tls.recv(4096)
                if not chunk:
                    raise ConverterError(
                        "O serviço de voz encerrou a conexão durante a negociação."
                    )
                response.extend(chunk)
                if len(response) > 65536:
                    raise ConverterError("Resposta WebSocket inválida.")

            header_block = bytes(response).split(b"\r\n\r\n", 1)[0]
            lines = header_block.split(b"\r\n")
            status = lines[0].decode("latin-1", errors="replace")
            if " 101 " not in status:
                raise ConverterError(
                    "O serviço de voz recusou a conexão WebSocket. "
                    f"Resposta: {status}"
                )

            headers = {}
            for line in lines[1:]:
                if b":" in line:
                    key_header, value = line.split(b":", 1)
                    headers[key_header.strip().lower()] = value.strip()

            expected = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
            )
            actual = headers.get(b"sec-websocket-accept")
            if actual != expected:
                raise ConverterError(
                    "A validação de segurança da conexão WebSocket falhou."
                )

            return cls(tls)

        except ConverterError:
            if tls:
                try:
                    tls.close()
                except Exception:
                    pass
            elif raw:
                try:
                    raw.close()
                except Exception:
                    pass
            raise

        except Exception as error:
            if tls:
                try:
                    tls.close()
                except Exception:
                    pass
            elif raw:
                try:
                    raw.close()
                except Exception:
                    pass

            raise ConverterError(
                "Não foi possível conectar ao serviço de voz. "
                f"Detalhes: {error}"
            )

    def send_text(self, text):
        if self._closed:
            raise ConverterError("A conexão com o serviço de voz já foi encerrada.")
        self.sock.sendall(_build_client_frame(0x1, text))

    def _send_control(self, opcode, payload=b""):
        if not self._closed:
            self.sock.sendall(_build_client_frame(opcode, payload))

    def recv_message(self):
        fragments = bytearray()
        message_opcode = None

        while True:
            fin, opcode, payload = _read_frame(self.sock)

            if opcode == 0x8:
                self._closed = True
                return None, None

            if opcode == 0x9:
                self._send_control(0xA, payload)
                continue

            if opcode == 0xA:
                continue

            if opcode in (0x1, 0x2):
                message_opcode = opcode
                fragments = bytearray(payload)
            elif opcode == 0x0 and message_opcode is not None:
                fragments.extend(payload)
            else:
                continue

            if fin and message_opcode is not None:
                return message_opcode, bytes(fragments)

    def close(self):
        if self._closed:
            return
        try:
            self._send_control(0x8, struct.pack("!H", 1000))
        except Exception:
            pass

        self._closed = True
        try:
            self.sock.close()
        except Exception:
            pass


def _synthesize_once(text, target, voice, rate):
    connection_id = uuid.uuid4().hex
    gec = _windows_filetime_token()

    url = (
        WSS_URL
        + "&ConnectionId=" + connection_id
        + "&Sec-MS-GEC=" + gec
        + "&Sec-MS-GEC-Version=" + SEC_MS_GEC_VERSION
    )

    ws = _WebSocketConnection.connect(
        url=url,
        origin=ORIGIN,
        user_agent=USER_AGENT,
        timeout=60,
    )

    received_audio = False

    try:
        config = (
            f"X-Timestamp:{_timestamp()}\r\n"
            "Content-Type:application/json; charset=utf-8\r\n"
            "Path:speech.config\r\n\r\n"
            '{"context":{"synthesis":{"audio":{"metadataoptions":'
            '{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"},'
            '"outputFormat":"audio-24khz-48kbitrate-mono-mp3"}}}}\r\n'
        )
        ws.send_text(config)

        request_id = uuid.uuid4().hex
        ssml = _make_ssml(text, voice, rate)

        request = (
            f"X-RequestId:{request_id}\r\n"
            "Content-Type:application/ssml+xml\r\n"
            f"X-Timestamp:{_timestamp()}Z\r\n"
            "Path:ssml\r\n\r\n"
            + ssml
        )
        ws.send_text(request)

        with open(target, "wb") as output:
            while True:
                opcode, data = ws.recv_message()
                if opcode is None:
                    break

                if opcode == 0x1:
                    decoded = data.decode("utf-8", errors="replace")
                    header_end = decoded.find("\r\n\r\n")
                    header_text = (
                        decoded[:header_end]
                        if header_end >= 0
                        else decoded
                    )

                    path_value = None
                    for line in header_text.split("\r\n"):
                        if line.lower().startswith("path:"):
                            path_value = line.split(":", 1)[1].strip().lower()
                            break

                    if path_value == "turn.end":
                        break

                elif opcode == 0x2:
                    if len(data) < 2:
                        continue

                    header_length = int.from_bytes(data[:2], "big")
                    if header_length <= 0 or header_length > len(data) - 2:
                        continue

                    header_start = 2
                    header_end = header_start + header_length
                    header_block = bytes(data[header_start:header_end])
                    body = bytes(data[header_end:])

                    if body.startswith(b"\r\n"):
                        body = body[2:]

                    parsed = _parse_headers(header_block)
                    if parsed.get(b"path") != b"audio":
                        continue

                    if parsed.get(b"content-type") == b"audio/mpeg" and body:
                        output.write(body)
                        received_audio = True

    finally:
        ws.close()

    if not received_audio or not target.exists() or target.stat().st_size < 1000:
        target.unlink(missing_ok=True)
        raise ConverterError(
            "O serviço de voz não retornou áudio. "
            "Tente novamente mais tarde."
        )

def _synthesize(text, target, voice, rate, cancel_event):
    last_error = None

    for attempt in range(1, RETRIES + 1):
        if cancel_event.is_set():
            return False

        try:
            _synthesize_once(text, target, voice, rate)
            return True
        except ConverterError as error:
            last_error = error
            target.unlink(missing_ok=True)
            if attempt < RETRIES:
                time.sleep(4)

    raise last_error or ConverterError("Falha desconhecida ao gerar áudio.")


def _create_section(text, final_file, voice, rate, progress, cancel_event, number, total):
    chunks = list(_split_utf8(text))

    if not chunks:
        raise ConverterError("A seção não contém texto para narrar.")

    temp_files = []

    try:
        for part_number, chunk in enumerate(chunks, start=1):
            if cancel_event.is_set():
                return False

            if (
                part_number == 1
                or part_number == len(chunks)
                or part_number % 5 == 0
            ):
                progress(
                    f"Arquivo {number} de {total}. "
                    f"Parte {part_number} de {len(chunks)}."
                )

            temp = final_file.parent / (
                f"__temp_{final_file.stem}_{part_number:03d}.mp3"
            )

            if not _synthesize(chunk, temp, voice, rate, cancel_event):
                return False

            temp_files.append(temp)

        if cancel_event.is_set():
            return False

        with open(final_file, "wb") as destination:
            for temp in temp_files:
                with open(temp, "rb") as source:
                    shutil_buffer = source.read(1024 * 1024)
                    while shutil_buffer:
                        destination.write(shutil_buffer)
                        shutil_buffer = source.read(1024 * 1024)

        return final_file.exists() and final_file.stat().st_size > 1000

    finally:
        for temp in temp_files:
            temp.unlink(missing_ok=True)


def convert_pdf(
    pdf_path,
    output_dir,
    mode,
    pages_per_file,
    voice,
    rate,
    progress,
    cancel_event,
):
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.is_file():
        raise ConverterError("Arquivo PDF não encontrado.")

    if pages_per_file < 1:
        raise ConverterError("Páginas por MP3 deve ser maior que zero.")

    output_dir.mkdir(parents=True, exist_ok=True)

    pages = _extract_pages(pdf_path, progress, cancel_event)
    if cancel_event.is_set():
        return

    if mode == "chapters":
        sections = _detect_chapters(pages)
        if not sections:
            progress(
                "Não foi possível detectar capítulos com segurança. "
                "Usando divisão por páginas."
            )
            sections = _split_by_pages(pages, pages_per_file)
    else:
        sections = _split_by_pages(pages, pages_per_file)

    if not sections:
        raise ConverterError("Nenhuma seção de áudio foi criada.")

    progress(f"Foram preparadas {len(sections)} partes de áudio.")

    for number, (name, text) in enumerate(sections, start=1):
        if cancel_event.is_set():
            return

        name = _safe_name(name)
        final_file = output_dir / f"{name}.mp3"

        if final_file.exists() and final_file.stat().st_size > 10_000:
            progress(
                f"Arquivo {number} de {len(sections)} já existe. Pulando."
            )
            continue

        final_file.unlink(missing_ok=True)

        success = _create_section(
            text=text,
            final_file=final_file,
            voice=voice,
            rate=rate,
            progress=progress,
            cancel_event=cancel_event,
            number=number,
            total=len(sections),
        )

        if not success:
            if cancel_event.is_set():
                return
            raise ConverterError(f"Falha ao gerar {name}.")

        progress(f"Arquivo {number} de {len(sections)} concluído.")
