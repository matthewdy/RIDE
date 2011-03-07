#  Copyright 2008-2009 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import wx.html
from StringIO import StringIO

from robotide.context import Font
from robotide.errors import SerializationError
from robotide.pluginapi import Plugin, ActionInfo
from robotide.publish import (RideTreeSelection, RideNotebookTabChanged,
                              RideTestCaseAdded, RideUserKeywordAdded)
from robotide.robotapi import TestCase, UserKeyword
from robotide.writer.serializer import Serializer, SerializationContext
from robotide.widgets.button import ButtonWithHandler
from robotide.utils import Printing


class PreviewPlugin(Plugin):
    """Provides preview of the test data in HTML, TSV and TXT formats."""
    datafile = property(lambda self: self.get_selected_datafile())

    def __init__(self, application):
        Plugin.__init__(self, application, default_settings={'format': 'HTML'})
        self._panel = None

    def enable(self):
        self.register_action(ActionInfo('Tools','Preview', self.OnShowPreview,
                                        shortcut='F6',
                                        doc='Show preview of the current file'))
        self.subscribe(self.OnTreeSelection, RideTreeSelection)
        self.subscribe(self.OnTabChanged, RideNotebookTabChanged)
        self.subscribe(self._update_preview, RideTestCaseAdded)
        self.subscribe(self._update_preview, RideUserKeywordAdded)

    def disable(self):
        self.unsubscribe_all()
        self.unregister_actions()
        self.delete_tab(self._panel)
        self._panel = None

    def OnShowPreview(self, event):
        if not self._panel:
            self._panel = PreviewPanel(self, self.notebook)
        self.show_tab(self._panel)
        self._update_preview()

    def OnTreeSelection(self, event):
        if event and event.text == 'Resources':
            return
        if self.tab_is_visible(self._panel):
            self._panel.tree_node_selected(event.item)

    def OnTabChanged(self, event):
        self._update_preview()

    def _update_preview(self, event=None):
        if self.tab_is_visible(self._panel) and self.datafile:
            self._panel.update_preview()


class PreviewPanel(wx.Panel):
    _formats = ['HTML', 'TSV', 'Text (Spaces)', 'Text (Pipes)']

    def __init__(self, parent, notebook):
        wx.Panel.__init__(self, notebook)
        self._parent = parent
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(main_sizer)
        self._format = parent.format
        self.__view = None
        self._printing = Printing()
        box = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(self._chooser())
        box.Add(self._print_button(), 1, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        self.Sizer.Add(box)
        notebook.AddPage(self, "Preview")

    def OnPrint(self, evt):
        self._printing.preview_text(self._get_content())

    @property
    def _file_format(self):
        if self._format in ['HTML', 'TSV']:
            return self._format.lower()
        return 'txt'

    @property
    def _pipe_separated(self):
        return 'Pipes' in self._format

    def _chooser(self):
        chooser = wx.RadioBox(self, label='Format', choices=self._formats)
        chooser.SetStringSelection(self._format)
        self.Bind(wx.EVT_RADIOBOX, self.OnTypeChanged, chooser)
        return chooser

    def _print_button(self):
        return ButtonWithHandler(self, 'Print')

    @property
    def _view(self):
        view_class = HtmlView if self._file_format == 'html' else TxtView
        if isinstance(self.__view, view_class):
            return self.__view
        self._remove_current_view()
        self.__view = self._create_view(view_class)
        return self.__view

    def _remove_current_view(self):
        if self.__view:
            self.Sizer.Remove(self.__view)
            self.__view.Destroy()

    def _create_view(self, view_class):
        view = view_class(self)
        self.Sizer.Add(view, 1, wx.EXPAND|wx.ALL, border=8)
        self.Sizer.Layout()
        return view

    def tree_node_selected(self, item):
        self.update_preview()
        self._view.scroll_to_subitem(item)

    def update_preview(self):
        self._view.set_content(self._get_content().decode('UTF-8'))

    def _get_content(self):
        datafile = self._parent.datafile
        if not datafile:
            return ''
        output = StringIO()
        ctx = SerializationContext(output=output, format=self._file_format,
                                   pipe_separated=self._pipe_separated)
        try:
            Serializer(ctx).serialize(datafile)
        except SerializationError, e:
            return "Creating preview of '%s' failed: %s" % (datafile.name, e)
        else:
            return output.getvalue()

    def OnTypeChanged(self, event):
        self._format = event.String
        self.update_preview()
        self._parent.save_setting('format', self._format)


class HtmlView(wx.html.HtmlWindow):

    def __init__(self, parent):
        wx.html.HtmlWindow.__init__(self, parent)
        self.SetStandardFonts()

    def set_content(self, content):
        self.SetPage(content)

    def scroll_to_subitem(self, item):
        anchor = self._get_anchor(item)
        if self.HasAnchor(anchor):
            self.ScrollToAnchor(anchor)
            self.ScrollLines(-1)
        else:
            self.Scroll(0,0)

    def _get_anchor(self, item):
        if isinstance(item, UserKeyword):
            return 'keyword_%s' % item.name
        if isinstance(item, TestCase):
            return 'test_%s' % item.name
        return ''


class TxtView(wx.TextCtrl):

    def __init__(self, parent):
        wx.TextCtrl.__init__(self, parent, style=wx.TE_MULTILINE)
        self.SetEditable(False)
        self.SetFont(Font().fixed)

    def set_content(self, content):
        self.SetValue(content)

    def scroll_to_subitem(self, item):
        pass
