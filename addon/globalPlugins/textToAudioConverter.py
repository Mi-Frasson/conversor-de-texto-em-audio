# -*- coding: utf-8 -*-
import sys
import threading
from pathlib import Path

import wx
import config
import gui
import ui
import globalPluginHandler
import scriptHandler
from gui.settingsDialogs import SettingsPanel, NVDASettingsDialog


ADDON_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = ADDON_DIR / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))


CONFIG_SECTION = "textToAudioConverter"
VOICE_OPTIONS = [
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural",
]
RATE_OPTIONS = ["-15%", "-10%", "-5%", "+0%", "+5%", "+10%", "+15%"]

CONFIG_SPEC = {
    "firstRun": "boolean(default=True)",
    "voice": "string(default='pt-BR-FranciscaNeural')",
    "rate": "string(default='-5%')",
    "pagesPerFile": "integer(default=20, min=1, max=200)",
    "mode": "string(default='pages')",
    "defaultOutput": "string(default='')",
}

config.conf.spec[CONFIG_SECTION] = CONFIG_SPEC


def _conf():
    return config.conf[CONFIG_SECTION]


def _save_config():
    try:
        config.conf.save()
    except Exception:
        pass


def _choice_index(values, current, fallback=0):
    try:
        return values.index(current)
    except ValueError:
        return fallback


def _show_shortcut_instructions(parent=None):
    wx.MessageBox(
        "Os comandos do Conversor de Texto em Áudio não possuem teclas fixas.\n\n"
        "Para configurar seus atalhos:\n"
        "1. Abra o menu do NVDA com NVDA+N.\n"
        "2. Entre em Preferências > Gestos de entrada.\n"
        "3. Procure a categoria 'Conversor de Texto em Áudio'.\n"
        "4. Selecione o comando desejado, escolha Adicionar e pressione a combinação de teclas.\n\n"
        "Comandos disponíveis:\n"
        "• Abre o conversor de texto em áudio.\n"
        "• Cancela a conversão de texto em áudio em andamento.",
        "Como configurar os atalhos",
        wx.OK | wx.ICON_INFORMATION,
        parent,
    )


class FirstRunWizard(wx.Dialog):
    """Assistente acessível de primeira execução."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Conversor de Texto em Áudio - Assistente de configuração",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.completed = False
        self._page = 0

        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        self.book = wx.Simplebook(panel)
        outer.Add(self.book, 1, wx.EXPAND | wx.ALL, 12)

        self._build_welcome_page()
        self._build_how_it_works_page()
        self._build_defaults_page()
        self._build_shortcuts_page()

        buttons = wx.BoxSizer(wx.HORIZONTAL)

        self.back_button = wx.Button(panel, wx.ID_ANY, "Voltar")
        self.back_button.Bind(wx.EVT_BUTTON, self._on_back)
        buttons.Add(self.back_button, 0, wx.RIGHT, 8)

        self.next_button = wx.Button(panel, wx.ID_ANY, "Avançar")
        self.next_button.Bind(wx.EVT_BUTTON, self._on_next)
        buttons.Add(self.next_button, 0, wx.RIGHT, 8)

        self.finish_button = wx.Button(panel, wx.ID_ANY, "Concluir")
        self.finish_button.Bind(wx.EVT_BUTTON, self._on_finish)
        buttons.Add(self.finish_button, 0, wx.RIGHT, 8)

        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancelar")
        buttons.Add(cancel_button, 0)

        outer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(outer)

        self.SetSize((760, 600))
        self.CentreOnParent()
        self._update_navigation()

    def _new_page(self):
        page = wx.Panel(self.book)
        sizer = wx.BoxSizer(wx.VERTICAL)
        page.SetSizer(sizer)
        self.book.AddPage(page, "")
        return page, sizer

    def _add_wrapped_text(self, page, sizer, text):
        label = wx.StaticText(page, label=text)
        label.Wrap(680)
        sizer.Add(label, 0, wx.EXPAND | wx.BOTTOM, 12)
        return label

    def _build_welcome_page(self):
        page, sizer = self._new_page()
        title = wx.StaticText(page, label="Bem-vindo ao Conversor de Texto em Áudio")
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        sizer.Add(title, 0, wx.EXPAND | wx.BOTTOM, 12)

        self._add_wrapped_text(
            page,
            sizer,
            "Este complemento transforma o texto de arquivos PDF em arquivos MP3. "
            "Ele é autossuficiente: não é necessário instalar Python, pip ou bibliotecas externas.",
        )
        self._add_wrapped_text(
            page,
            sizer,
            "A geração da voz usa um serviço on-line, portanto é necessária conexão com a Internet. "
            "Se o PDF for apenas uma imagem digitalizada, será necessário aplicar OCR antes.",
        )

    def _build_how_it_works_page(self):
        page, sizer = self._new_page()
        title = wx.StaticText(page, label="Como funciona")
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        sizer.Add(title, 0, wx.EXPAND | wx.BOTTOM, 12)

        self._add_wrapped_text(
            page,
            sizer,
            "1. Abra o conversor pelo comando que você atribuir em Gestos de entrada.\n"
            "2. Escolha o arquivo PDF e a pasta de saída.\n"
            "3. Escolha a voz, a velocidade e a forma de divisão.\n"
            "4. Inicie a conversão.\n"
            "5. Uma janela de progresso permanece aberta e o NVDA anuncia o andamento.\n"
            "6. Os arquivos MP3 são gravados na pasta escolhida.",
        )
        self._add_wrapped_text(
            page,
            sizer,
            "A divisão por número de páginas é a opção mais confiável. "
            "A detecção automática de capítulos é uma tentativa: se não for segura, "
            "o complemento volta automaticamente para a divisão por páginas.",
        )

    def _build_defaults_page(self):
        page, sizer = self._new_page()
        title = wx.StaticText(page, label="Escolha suas preferências padrão")
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        sizer.Add(title, 0, wx.EXPAND | wx.BOTTOM, 12)

        grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=10)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(page, label="Voz padrão:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.voice_choice = wx.Choice(page, choices=VOICE_OPTIONS)
        self.voice_choice.SetSelection(
            _choice_index(VOICE_OPTIONS, str(_conf()["voice"]))
        )
        grid.Add(self.voice_choice, 1, wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Velocidade padrão:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.rate_choice = wx.Choice(page, choices=RATE_OPTIONS)
        self.rate_choice.SetSelection(
            _choice_index(RATE_OPTIONS, str(_conf()["rate"]), 2)
        )
        grid.Add(self.rate_choice, 1, wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Páginas por MP3:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pages_spin = wx.SpinCtrl(
            page,
            min=1,
            max=200,
            initial=int(_conf()["pagesPerFile"]),
        )
        grid.Add(self.pages_spin, 1, wx.EXPAND)

        grid.Add(wx.StaticText(page, label="Divisão padrão:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.mode_choice = wx.Choice(
            page,
            choices=[
                "Por número de páginas",
                "Tentar detectar capítulos",
            ],
        )
        self.mode_choice.SetSelection(0 if str(_conf()["mode"]) == "pages" else 1)
        grid.Add(self.mode_choice, 1, wx.EXPAND)

        sizer.Add(grid, 0, wx.EXPAND | wx.BOTTOM, 14)

        output_label = wx.StaticText(
            page,
            label="Pasta base de saída (opcional; deixe em branco para usar a pasta do PDF):",
        )
        output_label.Wrap(680)
        sizer.Add(output_label, 0, wx.EXPAND | wx.BOTTOM, 5)

        output_row = wx.BoxSizer(wx.HORIZONTAL)
        self.output_text = wx.TextCtrl(page, value=str(_conf()["defaultOutput"]))
        browse = wx.Button(page, label="Selecionar pasta...")
        browse.Bind(wx.EVT_BUTTON, self._browse_output)
        output_row.Add(self.output_text, 1, wx.EXPAND | wx.RIGHT, 8)
        output_row.Add(browse, 0)
        sizer.Add(output_row, 0, wx.EXPAND)

    def _build_shortcuts_page(self):
        page, sizer = self._new_page()
        title = wx.StaticText(page, label="Configuração dos atalhos")
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        sizer.Add(title, 0, wx.EXPAND | wx.BOTTOM, 12)

        self._add_wrapped_text(
            page,
            sizer,
            "O complemento não força nenhuma combinação de teclas. "
            "Cada usuário escolhe seus próprios atalhos pelo NVDA.",
        )
        self._add_wrapped_text(
            page,
            sizer,
            "Caminho: NVDA > Preferências > Gestos de entrada > Conversor de Texto em Áudio.\n\n"
            "Lá aparecem os comandos para abrir o conversor e cancelar uma conversão em andamento. "
            "Selecione um comando, escolha Adicionar e pressione a combinação que desejar.",
        )

        help_button = wx.Button(page, label="Mostrar instruções de atalhos")
        help_button.Bind(wx.EVT_BUTTON, lambda evt: _show_shortcut_instructions(self))
        sizer.Add(help_button, 0)

    def _browse_output(self, event):
        with wx.DirDialog(self, "Selecione a pasta base de saída") as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.output_text.SetValue(dialog.GetPath())
                wx.CallAfter(self.output_text.SetFocus)

    def _on_back(self, event):
        if self._page > 0:
            self._page -= 1
            self.book.SetSelection(self._page)
            self._update_navigation()

    def _on_next(self, event):
        if self._page < self.book.GetPageCount() - 1:
            self._page += 1
            self.book.SetSelection(self._page)
            self._update_navigation()

    def _on_finish(self, event):
        conf = _conf()
        conf["voice"] = self.voice_choice.GetStringSelection()
        conf["rate"] = self.rate_choice.GetStringSelection()
        conf["pagesPerFile"] = int(self.pages_spin.GetValue())
        conf["mode"] = "pages" if self.mode_choice.GetSelection() == 0 else "chapters"
        conf["defaultOutput"] = self.output_text.GetValue().strip()
        conf["firstRun"] = False
        _save_config()

        self.completed = True
        self.EndModal(wx.ID_OK)

    def _update_navigation(self):
        last = self.book.GetPageCount() - 1
        self.back_button.Enable(self._page > 0)
        self.next_button.Show(self._page < last)
        self.finish_button.Show(self._page == last)
        self.Layout()

        if self._page == last:
            self.finish_button.SetFocus()
        else:
            self.next_button.SetFocus()


class PdfParaAudiolivroSettingsPanel(SettingsPanel):
    title = "Conversor de Texto em Áudio"

    def makeSettings(self, settingsSizer):
        conf = _conf()

        intro = wx.StaticText(
            self,
            label=(
                "Configurações padrão usadas ao abrir o conversor. "
                "Estas opções podem ser alteradas novamente em cada conversão."
            ),
        )
        intro.Wrap(650)
        settingsSizer.Add(intro, 0, wx.EXPAND | wx.BOTTOM, 12)

        grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=10)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(self, label="Voz padrão:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.voice_choice = wx.Choice(self, choices=VOICE_OPTIONS)
        self.voice_choice.SetSelection(_choice_index(VOICE_OPTIONS, str(conf["voice"])))
        grid.Add(self.voice_choice, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Velocidade padrão:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.rate_choice = wx.Choice(self, choices=RATE_OPTIONS)
        self.rate_choice.SetSelection(_choice_index(RATE_OPTIONS, str(conf["rate"]), 2))
        grid.Add(self.rate_choice, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Páginas por MP3:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pages_spin = wx.SpinCtrl(
            self,
            min=1,
            max=200,
            initial=int(conf["pagesPerFile"]),
        )
        grid.Add(self.pages_spin, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, label="Divisão padrão:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.mode_choice = wx.Choice(
            self,
            choices=[
                "Por número de páginas",
                "Tentar detectar capítulos",
            ],
        )
        self.mode_choice.SetSelection(0 if str(conf["mode"]) == "pages" else 1)
        grid.Add(self.mode_choice, 1, wx.EXPAND)

        settingsSizer.Add(grid, 0, wx.EXPAND | wx.BOTTOM, 12)

        output_label = wx.StaticText(
            self,
            label="Pasta base de saída (opcional):",
        )
        settingsSizer.Add(output_label, 0, wx.BOTTOM, 5)

        output_row = wx.BoxSizer(wx.HORIZONTAL)
        self.output_text = wx.TextCtrl(self, value=str(conf["defaultOutput"]))
        browse_button = wx.Button(self, label="Selecionar pasta...")
        browse_button.Bind(wx.EVT_BUTTON, self._browse_output)
        output_row.Add(self.output_text, 1, wx.EXPAND | wx.RIGHT, 8)
        output_row.Add(browse_button, 0)
        settingsSizer.Add(output_row, 0, wx.EXPAND | wx.BOTTOM, 14)

        shortcut_text = wx.StaticText(
            self,
            label=(
                "Atalhos: abra NVDA > Preferências > Gestos de entrada e procure "
                "a categoria 'Conversor de Texto em Áudio'."
            ),
        )
        shortcut_text.Wrap(650)
        settingsSizer.Add(shortcut_text, 0, wx.EXPAND | wx.BOTTOM, 8)

        buttons = wx.BoxSizer(wx.HORIZONTAL)

        shortcut_button = wx.Button(self, label="Como configurar atalhos...")
        shortcut_button.Bind(
            wx.EVT_BUTTON,
            lambda evt: _show_shortcut_instructions(self),
        )
        buttons.Add(shortcut_button, 0, wx.RIGHT, 8)

        wizard_button = wx.Button(self, label="Abrir assistente novamente...")
        wizard_button.Bind(wx.EVT_BUTTON, self._open_wizard)
        buttons.Add(wizard_button, 0)

        settingsSizer.Add(buttons, 0)

    def _browse_output(self, event):
        with wx.DirDialog(self, "Selecione a pasta base de saída") as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.output_text.SetValue(dialog.GetPath())
                wx.CallAfter(self.output_text.SetFocus)

    def _open_wizard(self, event):
        dialog = FirstRunWizard(self)
        try:
            result = dialog.ShowModal()
        finally:
            completed = dialog.completed
            dialog.Destroy()

        if result == wx.ID_OK and completed:
            conf = _conf()
            self.voice_choice.SetSelection(
                _choice_index(VOICE_OPTIONS, str(conf["voice"]))
            )
            self.rate_choice.SetSelection(
                _choice_index(RATE_OPTIONS, str(conf["rate"]), 2)
            )
            self.pages_spin.SetValue(int(conf["pagesPerFile"]))
            self.mode_choice.SetSelection(
                0 if str(conf["mode"]) == "pages" else 1
            )
            self.output_text.SetValue(str(conf["defaultOutput"]))

    def onSave(self):
        conf = _conf()
        conf["voice"] = self.voice_choice.GetStringSelection()
        conf["rate"] = self.rate_choice.GetStringSelection()
        conf["pagesPerFile"] = int(self.pages_spin.GetValue())
        conf["mode"] = "pages" if self.mode_choice.GetSelection() == 0 else "chapters"
        conf["defaultOutput"] = self.output_text.GetValue().strip()
        _save_config()


class ConverterDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Conversor de Texto em Áudio",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.settings = None
        conf = _conf()

        panel = wx.Panel(self)
        main = wx.BoxSizer(wx.VERTICAL)

        main.Add(
            wx.StaticText(panel, label="Arquivo PDF:"),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            10,
        )

        pdf_row = wx.BoxSizer(wx.HORIZONTAL)
        self.pdf_text = wx.TextCtrl(panel)
        pdf_button = wx.Button(panel, label="Selecionar PDF...")
        pdf_button.Bind(wx.EVT_BUTTON, self._browse_pdf)
        pdf_row.Add(self.pdf_text, 1, wx.EXPAND | wx.RIGHT, 8)
        pdf_row.Add(pdf_button, 0)
        main.Add(pdf_row, 0, wx.EXPAND | wx.ALL, 10)

        main.Add(
            wx.StaticText(panel, label="Pasta de saída:"),
            0,
            wx.LEFT | wx.RIGHT,
            10,
        )

        out_row = wx.BoxSizer(wx.HORIZONTAL)
        self.out_text = wx.TextCtrl(panel)
        out_button = wx.Button(panel, label="Selecionar pasta...")
        out_button.Bind(wx.EVT_BUTTON, self._browse_output)
        out_row.Add(self.out_text, 1, wx.EXPAND | wx.RIGHT, 8)
        out_row.Add(out_button, 0)
        main.Add(out_row, 0, wx.EXPAND | wx.ALL, 10)

        self.mode = wx.RadioBox(
            panel,
            label="Divisão do áudio",
            choices=[
                "Por número de páginas (mais confiável)",
                "Tentar detectar capítulos; se não for seguro, usar páginas",
            ],
            majorDimension=1,
            style=wx.RA_SPECIFY_ROWS,
        )
        self.mode.SetSelection(0 if str(conf["mode"]) == "pages" else 1)
        main.Add(
            self.mode,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=8)
        grid.AddGrowableCol(1, 1)

        grid.Add(
            wx.StaticText(panel, label="Páginas por MP3:"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.pages = wx.SpinCtrl(
            panel,
            min=1,
            max=200,
            initial=int(conf["pagesPerFile"]),
        )
        grid.Add(self.pages, 1, wx.EXPAND)

        grid.Add(
            wx.StaticText(panel, label="Voz:"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.voice = wx.Choice(panel, choices=VOICE_OPTIONS)
        self.voice.SetSelection(_choice_index(VOICE_OPTIONS, str(conf["voice"])))
        grid.Add(self.voice, 1, wx.EXPAND)

        grid.Add(
            wx.StaticText(panel, label="Velocidade:"),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        self.rate = wx.Choice(panel, choices=RATE_OPTIONS)
        self.rate.SetSelection(_choice_index(RATE_OPTIONS, str(conf["rate"]), 2))
        grid.Add(self.rate, 1, wx.EXPAND)

        main.Add(
            grid,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        info = wx.StaticText(
            panel,
            label=(
                "Autossuficiente: não exige Python ou pip no Windows. "
                "É necessária conexão com a Internet para gerar a voz."
            ),
        )
        info.Wrap(640)
        main.Add(
            info,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        buttons = wx.BoxSizer(wx.HORIZONTAL)

        self.start_button = wx.Button(
            panel,
            wx.ID_ANY,
            "Iniciar conversão",
        )
        self.start_button.Bind(wx.EVT_BUTTON, self._on_start)
        buttons.Add(self.start_button, 0, wx.RIGHT, 8)

        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancelar")
        buttons.Add(cancel_button, 0)

        self.SetEscapeId(wx.ID_CANCEL)
        main.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(main)
        self.SetMinSize((700, 520))
        self.Fit()
        self.CentreOnParent()

    def _browse_pdf(self, event):
        with wx.FileDialog(
            self,
            "Selecione o PDF",
            wildcard="Arquivos PDF (*.pdf)|*.pdf",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                path = Path(dialog.GetPath())
                self.pdf_text.SetValue(str(path))

                default_output = str(_conf()["defaultOutput"]).strip()
                if default_output:
                    output = Path(default_output) / ("Audiolivro - " + path.stem)
                else:
                    output = path.parent / ("Audiolivro - " + path.stem)

                self.out_text.SetValue(str(output))
                wx.CallAfter(self.pdf_text.SetFocus)

    def _browse_output(self, event):
        with wx.DirDialog(
            self,
            "Selecione a pasta de saída",
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.out_text.SetValue(dialog.GetPath())
                wx.CallAfter(self.out_text.SetFocus)

    def _on_start(self, event):
        pdf = self.pdf_text.GetValue().strip()
        output = self.out_text.GetValue().strip()

        if not pdf or not Path(pdf).is_file():
            wx.MessageBox(
                "Selecione um arquivo PDF válido.",
                "Conversor de Texto em Áudio",
                wx.OK | wx.ICON_ERROR,
            )
            self.pdf_text.SetFocus()
            return

        if not output:
            wx.MessageBox(
                "Selecione a pasta de saída.",
                "Conversor de Texto em Áudio",
                wx.OK | wx.ICON_ERROR,
            )
            self.out_text.SetFocus()
            return

        self.settings = {
            "pdf": pdf,
            "output": output,
            "mode": (
                "pages"
                if self.mode.GetSelection() == 0
                else "chapters"
            ),
            "pages": int(self.pages.GetValue()),
            "voice": self.voice.GetStringSelection(),
            "rate": self.rate.GetStringSelection(),
        }

        self.EndModal(wx.ID_OK)


class ProgressDialog(wx.Dialog):
    def __init__(self, parent, cancel_callback):
        super().__init__(
            parent,
            title="Conversor de Texto em Áudio - Progresso",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.cancel_callback = cancel_callback
        self.running = True

        panel = wx.Panel(self)
        main = wx.BoxSizer(wx.VERTICAL)

        self.status = wx.StaticText(
            panel,
            label="Preparando conversão...",
        )
        main.Add(self.status, 0, wx.EXPAND | wx.ALL, 10)

        self.log = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        )
        main.Add(
            self.log,
            1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        buttons = wx.BoxSizer(wx.HORIZONTAL)

        self.cancel_button = wx.Button(
            panel,
            wx.ID_ANY,
            "Cancelar conversão",
        )
        self.cancel_button.Bind(
            wx.EVT_BUTTON,
            self._on_cancel,
        )
        buttons.Add(self.cancel_button, 0, wx.RIGHT, 8)

        self.close_button = wx.Button(
            panel,
            wx.ID_CANCEL,
            "Fechar",
        )
        self.close_button.Disable()
        buttons.Add(self.close_button, 0)

        main.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(main)

        self.SetSize((760, 540))
        self.CentreOnParent()
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def append(self, message):
        self.status.SetLabel(message)
        self.log.AppendText(message + "\r\n")

    def finish(self, message):
        self.running = False
        self.append(message)
        self.cancel_button.Disable()
        self.close_button.Enable()
        self.close_button.SetFocus()

    def fail(self, message):
        self.running = False
        self.append(message)
        self.cancel_button.Disable()
        self.close_button.Enable()
        self.close_button.SetFocus()

    def _on_cancel(self, event):
        self.cancel_callback()
        self.append("Cancelamento solicitado...")

    def _on_close(self, event):
        if self.running:
            wx.Bell()
            ui.message(
                "A conversão ainda está em andamento. "
                "Use Cancelar conversão."
            )
            return

        event.Skip()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = "Conversor de Texto em Áudio"

    def __init__(self):
        super().__init__()

        self._worker_thread = None
        self._progress_dialog = None
        self._cancel_event = threading.Event()

        if PdfParaAudiolivroSettingsPanel not in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.append(
                PdfParaAudiolivroSettingsPanel
            )

        wx.CallAfter(
            ui.message,
            "Conversor de Texto em Áudio 1.0 carregado.",
        )

        threading.Thread(
            target=self._dependency_self_test,
            daemon=True,
        ).start()

        if bool(_conf()["firstRun"]):
            wx.CallLater(
                1500,
                self._show_first_run_if_needed,
            )

    def terminate(self):
        try:
            if PdfParaAudiolivroSettingsPanel in NVDASettingsDialog.categoryClasses:
                NVDASettingsDialog.categoryClasses.remove(
                    PdfParaAudiolivroSettingsPanel
                )
        except Exception:
            pass

        super().terminate()

    @scriptHandler.script(
        description="Abre o Conversor de Texto em Áudio",
        category="Conversor de Texto em Áudio",
    )
    def script_openPdfToAudio(self, gesture):
        if (
            self._worker_thread
            and self._worker_thread.is_alive()
        ):
            ui.message(
                "Já existe uma conversão em andamento."
            )

            if self._progress_dialog:
                wx.CallAfter(
                    self._progress_dialog.Raise
                )

            return

        wx.CallAfter(self._open_dialog)

    @scriptHandler.script(
        description=(
            "Cancela a conversão de PDF para "
            "audiolivro em andamento"
        ),
        category="Conversor de Texto em Áudio",
    )
    def script_cancelPdfToAudio(self, gesture):
        self._cancel_conversion()

    def _show_first_run_if_needed(self):
        if not bool(_conf()["firstRun"]):
            return

        dialog = FirstRunWizard(gui.mainFrame)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def _dependency_self_test(self):
        try:
            import secrets
            import typing_extensions
            from pypdf import PdfReader

            try:
                from . import textToAudioConverterCore
            except ImportError:
                from globalPlugins import textToAudioConverterCore

            sample = secrets.token_bytes(8)
            if not isinstance(sample, bytes) or len(sample) != 8:
                raise RuntimeError(
                    "Falha no gerador aleatório interno."
                )

            escaped = textToAudioConverterCore._xml_escape(
                "<&>'\""
            )

            if escaped != "&lt;&amp;&gt;&apos;&quot;":
                raise RuntimeError(
                    "Falha no escape XML interno."
                )

            if PdfReader is None:
                raise RuntimeError(
                    "PdfReader indisponível."
                )

        except Exception as error:
            wx.CallAfter(
                ui.message,
                (
                    "Conversor de Texto em Áudio: "
                    "falha na verificação interna: "
                    + str(error)
                ),
            )

    def _open_dialog(self):
        dialog = ConverterDialog(gui.mainFrame)
        settings = None

        try:
            result = dialog.ShowModal()
            settings = dialog.settings
        finally:
            dialog.Destroy()

        if result == wx.ID_OK and settings:
            self._start_conversion(settings)

    def _start_conversion(self, settings):
        self._cancel_event.clear()

        self._progress_dialog = ProgressDialog(
            gui.mainFrame,
            self._cancel_conversion,
        )

        self._progress_dialog.append(
            "Conversão iniciada."
        )
        self._progress_dialog.Show()
        self._progress_dialog.Raise()

        ui.message(
            "Conversão iniciada. "
            "Janela de progresso aberta."
        )

        self._worker_thread = threading.Thread(
            target=self._run_conversion,
            args=(settings,),
            daemon=True,
        )
        self._worker_thread.start()

    def _cancel_conversion(self):
        if (
            self._worker_thread
            and self._worker_thread.is_alive()
        ):
            self._cancel_event.set()
            ui.message("Cancelamento solicitado.")
        else:
            ui.message(
                "Não há conversão em andamento."
            )

    def _announce(self, message):
        wx.CallAfter(ui.message, message)

        dialog = self._progress_dialog
        if dialog:
            wx.CallAfter(
                dialog.append,
                message,
            )

    def _run_conversion(self, settings):
        try:
            try:
                from .textToAudioConverterCore import (
                    ConverterError,
                    convert_pdf,
                )
            except ImportError:
                from globalPlugins.textToAudioConverterCore import (
                    ConverterError,
                    convert_pdf,
                )

            convert_pdf(
                pdf_path=settings["pdf"],
                output_dir=settings["output"],
                mode=settings["mode"],
                pages_per_file=settings["pages"],
                voice=settings["voice"],
                rate=settings["rate"],
                progress=self._announce,
                cancel_event=self._cancel_event,
            )

            if self._cancel_event.is_set():
                message = "Conversão cancelada."
                wx.CallAfter(ui.message, message)

                if self._progress_dialog:
                    wx.CallAfter(
                        self._progress_dialog.fail,
                        message,
                    )
            else:
                message = "Conversão concluída."
                wx.CallAfter(ui.message, message)

                if self._progress_dialog:
                    wx.CallAfter(
                        self._progress_dialog.finish,
                        message,
                    )

        except Exception as error:
            if error.__class__.__name__ == "ConverterError":
                message = "Erro: " + str(error)
            else:
                message = "Erro inesperado: " + str(error)

            wx.CallAfter(ui.message, message)

            if self._progress_dialog:
                wx.CallAfter(
                    self._progress_dialog.fail,
                    message,
                )
