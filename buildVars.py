addon_info = {
    "addon_name": "textToAudioConverter",
    "addon_summary": "Conversor de Texto em Áudio",
    "addon_description": "Converte o texto de arquivos PDF em MP3 com uma interface acessível para usuários do NVDA.",
    "addon_version": "1.0.1",
    "addon_changelog": "Remove websocket-client, corrige licenciamento, URL do projeto e avisos de dependências.",
    "addon_author": "]Frasson",
    "addon_url": "https://github.com/Mi-Frasson/conversor-de-texto-em-audio",
    "addon_sourceURL": "https://github.com/Mi-Frasson/conversor-de-texto-em-audio",
    "addon_docFileName": "readme.html",
    "addon_minimumNVDAVersion": "2026.1",
    "addon_lastTestedNVDAVersion": "2026.1.1",
    "addon_updateChannel": None,
    "addon_license": "GPL-2.0-or-later",
    "addon_licenseURL": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
}

pythonSources = [
    "addon/globalPlugins/*.py",
    "addon/lib/**/*.py",
]
i18nSources = ["addon/globalPlugins/*.py"]
excludedFiles = ["addon/lib/websocket/tests"]
baseLanguage = "pt_BR"
markdownExtensions = []
brailleTables = {}
symbolDictionaries = {}
speechDictionaries = {}
