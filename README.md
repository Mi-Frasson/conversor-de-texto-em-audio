# Conversor de Texto em Áudio

Complemento para o NVDA que converte o texto de arquivos PDF em arquivos MP3.

## Recursos

- Interface acessível.
- Assistente de primeira execução.
- Preferências persistentes dentro das Configurações do NVDA.
- Vozes neurais em português do Brasil.
- Divisão por páginas e tentativa de detecção automática de capítulos.
- Janela de progresso acessível.
- Comandos configuráveis em **NVDA > Preferências > Gestos de entrada**.
- Não exige Python externo nem `pip`.

## Requisitos

- NVDA 2026.1 ou posterior.
- Windows.
- Conexão com a Internet durante a síntese de voz.
- PDF com texto extraível. PDFs somente com imagens precisam de OCR.

## Atalhos

O complemento não impõe atalhos fixos. Abra **NVDA > Preferências > Gestos de entrada**
e procure a categoria **Conversor de Texto em Áudio**.

## Privacidade

A síntese é realizada por um serviço on-line de leitura em voz alta da Microsoft.
Trechos do texto do documento são transmitidos ao serviço para gerar o áudio.
Não utilize documentos confidenciais se isso não for aceitável para você.

## Licença

GPL-2.0-or-later. Componentes incluídos possuem suas próprias licenças; consulte
`addon/THIRD_PARTY_NOTICES.txt` e `addon/licenses/`.

## Autor

]Frasson


## Dependências incluídas

- pypdf 5.9.0 — BSD-3-Clause.
- typing_extensions 4.16.0 — Python Software Foundation License Version 2.

A versão 1.0.1 não inclui `websocket-client`. A comunicação WebSocket necessária
é implementada pelo próprio código do complemento.

## Privacidade e serviço de voz

Durante a síntese, trechos do texto do PDF são enviados pela Internet ao serviço
de leitura em voz alta da Microsoft utilizado pelo complemento. Esse serviço externo
pode mudar ou ficar indisponível sem aviso.
