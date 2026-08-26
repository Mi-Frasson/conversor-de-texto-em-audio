# Auditoria da versão 1.0.1

## Licenciamento
- Código do complemento: GPL-2.0-or-later.
- pypdf 5.9.0: BSD-3-Clause; texto da licença incluído.
- typing_extensions 4.16.0: Python Software Foundation License Version 2; texto incluído.
- websocket-client: removido completamente.

## Privacidade
A síntese transmite trechos do texto extraído do PDF ao serviço on-line de voz da Microsoft.
A documentação informa essa transmissão.

## Segurança
- Não executa comandos de shell.
- Não baixa nem executa código.
- Não exige Python externo.
- A conexão de voz usa TLS (`wss://`) e valida o handshake WebSocket.
- Nomes de arquivos são sanitizados para Windows.

## Limitações
- O serviço de voz é externo e pode mudar.
- PDFs somente com imagens exigem OCR.
- A detecção de capítulos é heurística.
- O cliente WebSocket mínimo não implementa suporte explícito a proxy.
