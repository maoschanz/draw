# window.py
#
# Copyright 2018-2020 Romain F. T.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# Import libs
import os
from gi.repository import Gtk, Gdk, Gio, GdkPixbuf, GLib

# Import tools
from .tool_arc import ToolArc
from .tool_eraser import ToolEraser
from .tool_experiment import ToolExperiment
from .tool_highlight import ToolHighlighter
from .tool_line import ToolLine
from .tool_paint import ToolPaint
from .tool_pencil import ToolPencil
from .tool_picker import ToolPicker
from .tool_shape import ToolShape
from .tool_text import ToolText

from .tool_crop import ToolCrop
from .tool_filters import ToolFilters
from .tool_rotate import ToolRotate
from .tool_scale import ToolScale
# from .tool_skew import ToolSkew

from .select_rect import ToolRectSelect
from .select_free import ToolFreeSelect
from .select_color import ToolColorSelect

# Other imports
from .image import DrImage
from .new_image_dialog import DrCustomImageDialog
from .minimap import DrMinimap
from .options_manager import DrOptionsManager
from .message_dialog import DrMessageDialog
from .deco_manager import DrDecoManagerMenubar, \
                          DrDecoManagerHeaderbar, \
                          DrDecoManagerToolbar

from .utilities import utilities_save_pixbuf_to, \
                       utilities_add_filechooser_filters

UI_PATH = '/com/github/maoschanz/drawing/ui/'

PLACEHOLDER_UI_STRING = '''<?xml version="1.0"?>
<interface>
  <menu id="tool-placeholder">
    <section>
      <item>
        <attribute name="action">none</attribute>
        <attribute name="label">%s</attribute>
      </item>
    </section>
  </menu>
</interface>'''

DEFAULT_TOOL_ID = 'pencil'

################################################################################

@Gtk.Template(resource_path=UI_PATH+'window.ui')
class DrWindow(Gtk.ApplicationWindow):
	__gtype_name__ = 'DrWindow'

	_settings = Gio.Settings.new('com.github.maoschanz.drawing')

	# Window empty widgets
	tools_flowbox = Gtk.Template.Child()
	toolbar_box = Gtk.Template.Child()
	info_bar = Gtk.Template.Child()
	info_label = Gtk.Template.Child()
	notebook = Gtk.Template.Child()
	bottom_panes_box = Gtk.Template.Child()
	tools_scrollable_box = Gtk.Template.Child()
	tools_nonscrollable_box = Gtk.Template.Child()
	fullscreen_btn = Gtk.Template.Child()
	fullscreen_icon = Gtk.Template.Child()

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.app = kwargs['application']

		self.fullscreened = False
		self.pointer_to_current_page = None # this ridiculous hack allows to
		                   # manage several tabs in a single window despite the
		                                      # notebook widget being pure shit
		self.active_tool_id = None

		if self._settings.get_boolean('maximized'):
			self.maximize()
		# self.resize(360, 648)
		# self.resize(720, 288)
		self.set_ui_bars()

	def init_window_content(self, gfile, get_cb):
		"""Initialize the window's content, such as the minimap, the color
		popovers, the tools, their options, and a new image. Depending on the
		parameters, the new image can be imported from the clipboard, loaded
		from a GioFile, or (else) it can be a blank image."""
		self.tools = None
		self.minimap = DrMinimap(self, None)
		self.options_manager = DrOptionsManager(self)

		self.add_all_win_actions()
		if get_cb:
			self.build_image_from_clipboard()
		elif gfile is not None:
			self.build_new_tab(gfile=gfile)
		else:
			self.build_new_image()
		self.init_tools()
		self.connect_signals()
		self.set_picture_title()

	def init_tools(self):
		"""Initialize all tools, building the UI for them including the menubar,
		and enable the default tool."""
		disabled_tools = self._settings.get_strv('disabled-tools')
		dev = self._settings.get_boolean('devel-only')
		self.tools = {}
		self.prompt_message(False, 'window has started, now loading tools')
		# The order might be improvable
		self._load_tool('pencil', ToolPencil, disabled_tools, dev)
		self._load_tool('eraser', ToolEraser, disabled_tools, dev)
		self._load_tool('highlight', ToolHighlighter, disabled_tools, dev)
		self._load_tool('text', ToolText, disabled_tools, dev)
		self._load_tool('rect_select', ToolRectSelect, disabled_tools, dev)
		self._load_tool('free_select', ToolFreeSelect, disabled_tools, dev)
		self._load_tool('line', ToolLine, disabled_tools, dev)
		self._load_tool('arc', ToolArc, disabled_tools, dev)
		self._load_tool('shape', ToolShape, disabled_tools, dev)
		self._load_tool('picker', ToolPicker, disabled_tools, dev)
		self._load_tool('color_select', ToolColorSelect, disabled_tools, dev)
		self._load_tool('paint', ToolPaint, disabled_tools, dev)
		if dev:
			self._load_tool('experiment', ToolExperiment, disabled_tools, dev)
		self._load_tool('crop', ToolCrop, disabled_tools, dev)
		self._load_tool('scale', ToolScale, disabled_tools, dev)
		self._load_tool('rotate', ToolRotate, disabled_tools, dev)
		# self._load_tool('skew', ToolSkew, disabled_tools, dev)
		self._load_tool('filters', ToolFilters, disabled_tools, dev)

		# Side pane buttons for tools, and their menubar items if they don't
		# exist yet
		self._build_tool_rows()
		if not self.app.has_tools_in_menubar:
			self.build_menubar_tools_menu()

		# Initialisation of options and menus
		tool_id = self._settings.get_string('last-active-tool')
		if tool_id not in self.tools:
			tool_id = DEFAULT_TOOL_ID
		self.active_tool_id = tool_id
		self.former_tool_id = tool_id
		if tool_id == DEFAULT_TOOL_ID: # The "pencil" button is already active
			self.enable_tool(tool_id)
		else:
			self.active_tool().row.set_active(True)

	def _load_tool(self, tool_id, tool_class, disabled_tools, dev):
		"""Given its id and its python class, this method tries to load a tool,
		and show an error message if the tool initialization failed."""
		if dev: # Simplest way to get an error stack
			self.tools[tool_id] = tool_class(self)
		elif tool_id not in disabled_tools:
			try:
				self.tools[tool_id] = tool_class(self)
			except:
				self.prompt_message(True, _("Failed to load tool: %s") % tool_id)

	def _build_tool_rows(self):
		"""Adds each tool's button to the side pane."""
		group = None
		for tool_id in self.tools:
			row = self.tools[tool_id].row
			if group is None:
				group = row
			else:
				row.join_group(group)
			self.tools_flowbox.add(row)
			row.get_parent().set_can_focus(False)
		self.on_show_labels_setting_changed()

	def build_menubar_tools_menu(self):
		sections = [None, None, None]
		sections[2] = self.get_menubar_item([[True, 4], [False, 0]])
		sections[0] = self.get_menubar_item([[True, 4], [False, 1]])
		sections[1] = self.get_menubar_item([[True, 4], [False, 2]])
		for tool_id in self.tools:
			tool = self.tools[tool_id]
			tool.add_item_to_menu(sections[tool.menu_id])
		self.app.has_tools_in_menubar = True

	############################################################################
	# TABS AND WINDOWS MANAGEMENT ##############################################

	def build_new_image(self, *args):
		"""Open a new tab with a drawable blank image using the default values
		defined by user's settings."""
		width = self._settings.get_int('default-width')
		height = self._settings.get_int('default-height')
		rgba = self._settings.get_strv('default-rgba')
		self.build_new_tab(width=width, height=height, background_rgba=rgba)
		if self.active_tool_id is not None: # Tools might not be initialized yet
			self.set_picture_title()

	def build_new_custom(self, *args):
		"""Open a new tab with a drawable blank image using the custom values
		defined by user's input."""
		dialog = DrCustomImageDialog(self)
		result = dialog.run()
		if result == Gtk.ResponseType.OK:
			width, height, rgba = dialog.get_values()
			self.build_new_tab(width=width, height=height, background_rgba=rgba)
			self.set_picture_title()
		dialog.destroy()

	def build_image_from_clipboard(self, *args):
		"""Open a new tab with the image in the clipboard. If the clipboard is
		empty, the new image will be blank."""
		cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		pixbuf = cb.wait_for_image()
		self.build_new_tab(pixbuf=pixbuf)

	def build_image_from_selection(self, *args):
		"""Open a new tab with the image in the selection."""
		pixbuf = self.get_active_image().selection.get_pixbuf()
		self.build_new_tab(pixbuf=pixbuf)

	def build_new_tab(self, gfile=None, pixbuf=None, \
		           width=200, height=200, background_rgba=[1.0, 0.0, 0.0, 1.0]):
		"""Open a new tab with an optional file to open in it."""
		new_image = DrImage(self)
		self.notebook.append_page(new_image, new_image.build_tab_widget())
		self.notebook.child_set_property(new_image, 'reorderable', True)
		if gfile is not None:
			new_image.try_load_file(gfile)
		elif pixbuf is not None:
			new_image.try_load_pixbuf(pixbuf)
		else:
			new_image.init_background(width, height, background_rgba)
		self.update_tabs_visibility()
		self.notebook.set_current_page(self.notebook.get_n_pages()-1)

	def on_active_tab_changed(self, *args):
		self.switch_to(self.active_tool_id, args[1])
		print("changement d'image")
		# On devrait être moins bourrin et conserver la sélection # XXX
		self.set_picture_title(args[1].update_title())
		self.minimap.set_zoom_label(args[1].zoom_level * 100)

	def update_tabs_menu_section(self, *args):
		action = self.lookup_action('active_tab')
		section = self.get_menubar_item([[True, 2], [False, 1]])
		section.remove_all()
		for page in self.notebook.get_children():
			tab_title = page.update_title()
			tab_index = self.notebook.page_num(page)
			section.append(tab_title, 'win.active_tab(' + str(tab_index) + ')')

	def action_tab_left(self, *args):
		# XXX (un)availability of this action, + touch gesture
		current_page = self.notebook.get_current_page()
		if current_page == 0:
			self.notebook.set_current_page(self.notebook.get_n_pages() - 1)
		else:
			self.notebook.set_current_page(current_page - 1)

	def action_tab_right(self, *args):
		# XXX (un)availability of this action, + touch gesture
		current_page = self.notebook.get_current_page()
		if current_page == self.notebook.get_n_pages() - 1:
			self.notebook.set_current_page(0)
		else:
			self.notebook.set_current_page(current_page + 1)

	def close_tab(self, tab):
		"""Close a tab (after asking to save if needed)."""
		index = self.notebook.page_num(tab)
		if not self.notebook.get_nth_page(index).is_saved():
			self.notebook.set_current_page(index)
			is_saved = self.confirm_save_modifs()
			if not is_saved:
				return False
		self.notebook.remove_page(index)
		self.update_tabs_visibility()
		return True

	def action_close_tab(self, *args):
		if self.notebook.get_n_pages() > 1:
			self.get_active_image().try_close_tab()
		else:
			self.close()

	def action_close_window(self, *args):
		self.close()

	def on_close(self, *args):
		"""Event callback when trying to close a window. It saves/closes each
		tab and saves the current window settings in order to restore them.
		Returns `False` on success, `True` otherwise."""
		while self.notebook.get_n_pages() != 0:
			if not self.get_active_image().try_close_tab():
				return True

		self.options_manager.remember_options()
		self._settings.set_string('last-active-tool', self.active_tool_id)
		self._settings.set_boolean('maximized', self.is_maximized())
		return False

	############################################################################
	# GENERAL PURPOSE METHODS ##################################################

	def connect_signals(self):
		# Closing the info bar
		self.info_bar.connect('close', self.hide_message)
		self.info_bar.connect('response', self.hide_message)

		# Closing the window
		self.connect('delete-event', self.on_close)

		# Resizing the window
		self.connect('configure-event', self._adapt_to_window_size)

		# When a setting changes
		self._settings.connect('changed::show-labels', self.on_show_labels_setting_changed)
		self._settings.connect('changed::deco-type', self.on_layout_changed)
		self._settings.connect('changed::big-icons', self.on_icon_size_changed)
		# self._settings.connect('changed::preview-size', self.show_info_settings)
		# self._settings.connect('changed::devel-only', self.show_info_settings)
		self._settings.connect('changed::disabled-tools', self.show_info_settings)
		# Other settings are connected in DrImage

		# What happens when the active image change
		self.notebook.connect('switch-page', self.on_active_tab_changed)

		# Managing drag-and-drop
		self.notebook.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.MOVE)
		self.notebook.connect('drag-data-received', self.on_data_dropped)
		self.notebook.drag_dest_add_uri_targets()
		# because drag_dest_add_image_targets doesn't work for files

	def get_menubar_item(self, path_description):
		"""Get an item of the app-wide menubar. The `path_description` object
		is an array of [boolean, int] couples. The boolean means if we're
		looking for a submenu, the int is an index."""
		current_item = self.app.get_menubar()
		for item in path_description:
			if item[0]:
				link_type = Gio.MENU_LINK_SUBMENU
			else:
				link_type = Gio.MENU_LINK_SECTION
			current_item = current_item.get_item_link(item[1], link_type)
		return current_item

	def add_action_simple(self, action_name, callback, shortcuts):
		"""Convenient wrapper method adding a stateless action to the window. It
		will be named 'action_name' (string) and activating the action will
		trigger the method 'callback'."""
		action = Gio.SimpleAction.new(action_name, None)
		action.connect('activate', callback)
		self.add_action(action)
		if shortcuts is not None:
			self.app.set_accels_for_action('win.' + action_name, shortcuts)

	def add_action_boolean(self, action_name, default, callback):
		"""Convenient wrapper method adding a stateful action to the window. It
		will be named 'action_name' (string), be created with the state 'default'
		(boolean), and activating the action will trigger the method 'callback'."""
		action = Gio.SimpleAction().new_stateful(action_name, None, \
		                                      GLib.Variant.new_boolean(default))
		action.connect('change-state', callback)
		self.add_action(action)

	def add_action_enum(self, action_name, default, callback):
		"""Convenient wrapper method adding a stateful action to the window. It
		will be named 'action_name' (string), be created with the state 'default'
		(string), and changing the active target of the action will trigger the
		method 'callback'."""
		action = Gio.SimpleAction().new_stateful(action_name, \
		            GLib.VariantType.new('s'), GLib.Variant.new_string(default))
		action.connect('change-state', callback)
		self.add_action(action)

	def add_all_win_actions(self):
		"""This doesn't add all window-wide GioActions, but only the GioActions
		which are here "by default", independently of any tool."""

		self.add_action_simple('main_menu', self.action_main_menu, ['F10'])
		self.add_action_simple('options_menu', self.action_options_menu, ['<Shift>F10'])

		self.add_action_boolean('toggle_preview', False, self.action_toggle_preview)
		self.app.set_accels_for_action('win.toggle_preview', ['<Ctrl>m'])
		self.add_action_boolean('show_labels', self._settings.get_boolean( \
		                     'show-labels'), self.on_show_labels_action_changed)
		self.app.set_accels_for_action('win.show_labels', ['F9'])

		self.add_action_simple('reload_file', self.action_reload, ['F5'])
		self.add_action_simple('properties', self.action_properties, None)
		self.add_action_simple('fullscreen', self.action_fullscreen, ['F11'])
		self.add_action_simple('unfullscreen', self.action_unfullscreen, ['Escape'])

		self.add_action_simple('go_up', self.action_go_up, ['<Ctrl>Up'])
		self.add_action_simple('go_down', self.action_go_down, ['<Ctrl>Down'])
		self.add_action_simple('go_left', self.action_go_left, ['<Ctrl>Left'])
		self.add_action_simple('go_right', self.action_go_right, ['<Ctrl>Right'])

		self.add_action_simple('zoom_in', self.action_zoom_in, ['<Ctrl>plus', '<Ctrl>KP_Add'])
		self.add_action_simple('zoom_out', self.action_zoom_out, ['<Ctrl>minus', '<Ctrl>KP_Subtract'])
		self.add_action_simple('zoom_100', self.action_zoom_100, ['<Ctrl>1', '<Ctrl>KP_1'])
		self.add_action_simple('zoom_opti', self.action_zoom_opti, ['<Ctrl>0', '<Ctrl>KP_0'])

		self.add_action_simple('new_tab', self.build_new_image, ['<Ctrl>t'])
		self.add_action_simple('new_tab_custom', self.build_new_custom, None)
		self.add_action_simple('new_tab_selection', \
		                    self.build_image_from_selection, ['<Ctrl><Shift>t'])
		self.add_action_simple('new_tab_clipboard', \
		                    self.build_image_from_clipboard, ['<Ctrl><Shift>v'])
		self.add_action_simple('open', self.action_open, ['<Ctrl>o'])
		self.add_action_simple('tab_left', self.action_tab_left, ['<Ctrl><Shift>Left'])
		self.add_action_simple('tab_right', self.action_tab_right, ['<Ctrl><Shift>Right'])
		self.add_action_simple('close_tab', self.action_close_tab, ['<Ctrl>w'])
		self.add_action_simple('close', self.action_close_window, None)

		self.add_action_simple('undo', self.action_undo, ['<Ctrl>z'])
		self.add_action_simple('redo', self.action_redo, ['<Ctrl><Shift>z'])

		self.add_action_simple('save', self.action_save, ['<Ctrl>s'])
		self.add_action_simple('save_as', self.action_save_as, ['<Ctrl><Shift>s'])
		self.add_action_simple('export_as', self.action_export_as, None)
		self.add_action_simple('print', self.action_print, None)

		self.add_action_simple('import', self.action_import, ['<Ctrl>i'])
		self.add_action_simple('paste', self.action_paste, ['<Ctrl>v'])
		self.add_action_simple('select_all', self.action_select_all, ['<Ctrl>a'])
		self.add_action_simple('unselect', self.action_unselect, ['<Ctrl><Shift>a'])
		self.add_action_simple('selection_cut', self.action_cut, ['<Ctrl>x'])
		self.add_action_simple('selection_copy', self.action_copy, ['<Ctrl>c'])
		self.add_action_simple('selection_delete', self.action_delete, ['Delete'])
		self.add_action_simple('selection_export', self.action_selection_export, None)

		self.add_action_simple('back_to_previous', self.back_to_previous, ['<Ctrl>b'])
		self.add_action_simple('force_selection', self.force_selection, None)
		self.add_action_simple('apply_canvas_tool', self.action_apply_canvas_tool, None)

		self.add_action_enum('active_tool', DEFAULT_TOOL_ID, self.on_change_active_tool)

		self.add_action_simple('main_color', self.action_color1, ['<Ctrl>l'])
		self.add_action_simple('secondary_color', self.action_color2, ['<Ctrl>r'])
		self.add_action_simple('exchange_color', self.exchange_colors, ['<Ctrl>e'])

		editor = self._settings.get_boolean('direct-color-edit')
		self.app.add_action_boolean('use_editor', editor, self.action_use_editor)

		if self._settings.get_boolean('devel-only'):
			self.add_action_simple('restore_pixbuf', self.action_restore, None)
			self.add_action_simple('rebuild_from_histo', self.action_rebuild, None)
			self.add_action_simple('get_values', self.action_getvalues, ['<Ctrl>g'])

		action = Gio.PropertyAction.new('active_tab', self.notebook, 'page')
		self.add_action(action)

	def set_cursor(self, is_custom):
		"""Called by the tools at various occasions, this method updates the
		mouse cursor according to `is_custom` (if False, use the default cursor)
		and the active tool `cursor_name` attribute."""
		if is_custom:
			name = self.active_tool().cursor_name
		else:
			name = 'default'
		cursor = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), name)
		self.get_window().set_cursor(cursor)

	############################################################################
	# WINDOW DECORATIONS AND LAYOUTS ###########################################

	def on_layout_changed(self, *args):
		is_narrow = self._decorations.remove_from_ui()
		self.set_ui_bars()
		self._decorations.set_compact(is_narrow)
		self.set_picture_title()

	def show_info_settings(self, *args):
		"""This is executed when a setting changed but the method to apply it
		immediatly in the current window doesn't exist."""
		self.prompt_message(True, \
		            _("Modifications will take effect in the next new window."))

	def set_picture_title(self, *args):
		"""Set the window's title and subtitle (regardless of the preferred UI
		bars), and the active tab title. Tools have to be initialized before
		calling this method, because they provide the subtitle."""
		if len(args) == 1:
			main_title = args[0]
		else:
			main_title = self.get_active_image().update_title()
		subtitle = self.active_tool().get_edition_status()
		self.update_tabs_menu_section()
		self._decorations.set_titles(main_title, subtitle)

	def get_auto_decorations(self):
		"""Return the decorations setting based on the XDG_CURRENT_DESKTOP
		environment variable."""
		desktop_env = os.getenv('XDG_CURRENT_DESKTOP', 'GNOME')
		if 'GNOME' in desktop_env:
			return 'hg'
		elif 'Pantheon' in desktop_env:
			return 'he'
		elif 'Unity' in desktop_env:
			return 'tc'
		elif 'KDE' in desktop_env:
			return 'ts'
		elif 'Cinnamon' in desktop_env:
			return 'mts'
		elif 'MATE' in desktop_env or 'XFCE' in desktop_env:
			return 'mtc'
		else:
			return 'hg' # Use the GNOME layout if the desktop is unknown,
		# because i don't know how the env variable is on mobile.
		# Since hipsterwm users love "ricing", they'll be happy to edit
		# preferences themselves if they hate CSD.

	def set_ui_bars(self):
		"""Set the UI "bars" (headerbar, menubar, titlebar, toolbar, whatever)
		according to the user's preference, which by default is an empty string.
		In this case, an useful string is set by `get_auto_decorations()`."""
		self.has_good_width_limits = False

		builder = Gtk.Builder.new_from_string(PLACEHOLDER_UI_STRING \
		                                                  % _("No options"), -1)
		# Loading a whole file in a GtkBuilder just for this looked ridiculous,
		# so it's built from a string.
		self.placeholder_model = builder.get_object('tool-placeholder')

		# Remember the setting, so no need to restart this at each dialog.
		self.deco_layout = self._settings.get_string('deco-type')
		if self.deco_layout == '':
			self.deco_layout = self.get_auto_decorations()

		if self.deco_layout == 'hg':
			self._decorations = DrDecoManagerHeaderbar(False, self)
		elif self.deco_layout == 'he':
			self._decorations = DrDecoManagerHeaderbar(True, self)
		elif self.deco_layout == 'm':
			self._decorations = DrDecoManagerMenubar(self, True)
		elif 't' in self.deco_layout:
			symbolic = 's' in self.deco_layout
			menubar = 'm' in self.deco_layout
			self._decorations = DrDecoManagerToolbar(symbolic, menubar, self)
		else:
			self._settings.set_string('deco-type', '')
			self.set_ui_bars() # yes, recursion.

		if self.app.is_beta():
			self.get_style_context().add_class('devel')
		self.set_fullscreen_menu()

	def set_fullscreen_menu(self):
		builder = Gtk.Builder.new_from_resource(UI_PATH + 'win-menus.ui')
		fullscreen_menu = builder.get_object('fullscreen-menu')

		tabs_list = self.get_menubar_item([[True, 2], [False, 1]])
		fullscreen_menu.append_section(_("Opened images"), tabs_list)

		classic_tools_section = self.get_menubar_item([[True, 4], [False, 1]])
		section = fullscreen_menu.get_item_link(3, Gio.MENU_LINK_SECTION)
		section.prepend_section(None, classic_tools_section)

		selection_tools_section = self.get_menubar_item([[True, 4], [False, 0]])
		canvas_tools_section = self.get_menubar_item([[True, 4], [False, 2]])
		submenu = section.get_item_link(1, Gio.MENU_LINK_SUBMENU)
		submenu.append_section(None, selection_tools_section)
		submenu.append_section(None, canvas_tools_section)

		self.fullscreen_btn.set_menu_model(fullscreen_menu)

	def action_main_menu(self, *args):
		if self.fullscreened:
			self.fullscreen_btn.set_active(not self.fullscreen_btn.get_active())
		else:
			self._decorations.toggle_menu()

	def action_options_menu(self, *args):
		"""This displays/hides the tool's options menu, and is implemented as an
		action to ease the accelerator (shift+f10). This action could be
		disable when the current pane doesn't contain the corresponding button,
		but will not be."""
		self.options_manager.toggle_menu()

	def _adapt_to_window_size(self, *args):
		"""Adapts the headerbar (if any) and the default bottom pane to the new
		window size. If the current bottom pane isn't the default one, this
		will call the tool method applying the new size to the tool pane."""
		if not self.has_good_width_limits and self.get_allocated_width() > 700:
			self.options_manager.init_adaptability()
			self._decorations.init_adaptability()
			self.has_good_width_limits = True
		self._decorations.adapt_to_window_size()

		available_width = self.bottom_panes_box.get_allocated_width()
		self.options_manager.adapt_to_window_size(available_width)

		self.get_active_image().fake_scrollbar_update()

	def hide_message(self, *args):
		self.prompt_message(False, '')

	def prompt_message(self, show, label):
		"""Update the content and the visibility of the info bar."""
		self.info_bar.set_visible(show)
		if show:
			self.info_label.set_label(label)
		if self._settings.get_boolean('devel-only'):
			print('Drawing: ' + label)

	def update_tabs_visibility(self):
		should_show = (self.notebook.get_n_pages() > 1) and not self.fullscreened
		self.notebook.set_show_tabs(should_show)

	############################################################################
	# FULLSCREEN ###############################################################

	def action_unfullscreen(self, *args):
		# TODO connect to signals instead
		self.unfullscreen()
		self.set_fullscreen_state(False)

	def action_fullscreen(self, *args):
		# TODO connect to signals instead?
		self.fullscreen()
		self.set_fullscreen_state(True)

	def set_fullscreen_state(self, state):
		self.fullscreened = state
		self.tools_flowbox.set_visible(not state)
		self.toolbar_box.set_visible(not state) # XXX not if empty!!
		self.fullscreen_btn.set_visible(state)
		self.update_tabs_visibility()

	############################################################################
	# SIDE PANE (TOOLS) ########################################################

	def on_icon_size_changed(self, *args):
		for tool_id in self.tools:
			self.tools[tool_id].update_icon_size()

	def set_tools_labels_visibility(self, visible):
		"""Change the way tools are displayed in the side pane. Visible labels
		mean the tools will be arranged in a scrollable list of buttons, else
		they will be in an adaptative flowbox."""
		for tool_id in self.tools:
			self.tools[tool_id].set_show_label(visible)
		nb_tools = len(self.tools)
		parent_box = self.tools_flowbox.get_parent()
		if visible:
			self.tools_flowbox.set_min_children_per_line(nb_tools)
			if parent_box == self.tools_nonscrollable_box:
				self.tools_nonscrollable_box.remove(self.tools_flowbox)
				self.tools_scrollable_box.add(self.tools_flowbox)
		else:
			if parent_box == self.tools_scrollable_box:
				self.tools_scrollable_box.remove(self.tools_flowbox)
				self.tools_nonscrollable_box.add(self.tools_flowbox)
			nb_min = int( (nb_tools+(nb_tools % 3))/3 ) - 1
			self.tools_flowbox.set_min_children_per_line(nb_min)
		self.tools_flowbox.set_max_children_per_line(nb_tools)

	def on_show_labels_setting_changed(self, *args):
		# TODO https://lazka.github.io/pgi-docs/Gio-2.0/classes/Settings.html#Gio.Settings.create_action
		self.set_tools_labels_visibility(self._settings.get_boolean('show-labels'))

	def on_show_labels_action_changed(self, *args):
		show_labels = not args[0].get_state()
		self._settings.set_boolean('show-labels', show_labels)
		args[0].set_state(GLib.Variant.new_boolean(show_labels))

	############################################################################
	# TOOLS ####################################################################

	def on_change_active_tool(self, *args):
		"""Action callback, doing nothing in some situations, thus avoiding
		infinite loops. It sets the correct `tool_id` using adequate methods
		otherwise."""
		state_as_string = args[1].get_string()
		if state_as_string == args[0].get_state().get_string():
			return
		if self.tools[state_as_string].row.get_active():
			self.switch_to(state_as_string, None)
		else:
			self.tools[state_as_string].row.set_active(True)

	def switch_to(self, tool_id, image_pointer):
		"""Switch from the current tool to `tool_id` and to the current image to
		`image_pointer`, which can be `None` if the image is not changing."""
		self.pointer_to_current_page = None
		action = self.lookup_action('active_tool')
		action.set_state(GLib.Variant.new_string(tool_id))
		self._disable_former_tool(tool_id)
		self.pointer_to_current_page = image_pointer
		self.enable_tool(tool_id)
		self.pointer_to_current_page = None

	def enable_tool(self, new_tool_id):
		"""Activate the tool whose id is `new_tool_id`."""
		self.get_active_image().update()
		self.active_tool_id = new_tool_id
		self.active_tool().on_tool_selected()
		self._update_fullscreen_icon()
		self._update_bottom_pane()
		self.get_active_image().update_actions_state()
		self.set_picture_title()

	def _disable_former_tool(self, future_tool_id):
		"""Unactivate the active tool."""
		self.former_tool_id = self.active_tool_id
		should_preserve_selection = self.tools[future_tool_id].accept_selection
		self.former_tool().give_back_control(should_preserve_selection)
		self.former_tool().on_tool_unselected()
		self.get_active_image().selection.hide_popovers()

	def _update_bottom_pane(self):
		"""Show the correct bottom pane, with the correct tool options menu."""
		self.options_manager.try_enable_pane(self.active_tool().pane_id)
		self.options_manager.update_pane(self.active_tool())
		self._build_options_menu()
		self._adapt_to_window_size()

	def _update_fullscreen_icon(self):
		"""Show the icon of the currently active tool on the button managing
		fullscreen's main menu."""
		name = self.active_tool().icon_name
		img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.BUTTON)
		self.fullscreen_btn.set_image(img)

	def active_tool(self):
		return self.tools[self.active_tool_id]

	def former_tool(self):
		return self.tools[self.former_tool_id]

	def back_to_previous(self, *args):
		self.tools[self.former_tool_id].row.set_active(True)

	def _build_options_menu(self):
		"""Build the active tool's option menus.
		The first menu is the popover from the bottom bar. It can contain any
		widget, or it can be build from a Gio.MenuModel
		The second menu is build from a Gio.MenuModel and is in the menubar (not
		available with all layouts)."""
		widget = self.active_tool().get_options_widget()
		model = self.active_tool().get_options_model()
		label = self.active_tool().get_options_label()
		if model is None:
			self.app.get_menubar().remove(5)
			self.app.get_menubar().insert_submenu(5, _("_Options"), self.placeholder_model)
		else:
			self.app.get_menubar().remove(5)
			self.app.get_menubar().insert_submenu(5, _("_Options"), model)
		pane = self.options_manager.get_active_pane()
		if pane is not None: # XXX try/except
			pane.build_options_menu(widget, model, label)
		else:
			self.prompt_message(False, 'Pane is none for label: ' + label)

	def action_use_editor(self, *args):
		use_editor = not args[0].get_state()
		self._settings.set_boolean('direct-color-edit', use_editor)
		args[0].set_state(GLib.Variant.new_boolean(use_editor))
		self.options_manager.set_palette_setting(use_editor)

	def exchange_colors(self, *args):
		self.options_manager.get_classic_tools_pane().middle_click_action()

	def action_color1(self, *args):
		if self.active_tool().use_color:
			self.options_manager.left_color_btn().open()

	def action_color2(self, *args):
		if self.active_tool().use_color:
			self.options_manager.right_color_btn().open()

	def on_antialiasing_action_changed(self, *args):
		pass # TODO

	############################################################################
	# IMAGE FILES MANAGEMENT ###################################################

	def action_properties(self, *args):
		"""Display the properties dialog for the current image. This could be
		done here but it's done in DrImage to have a satisfying UML diagram."""
		self.get_active_image().show_properties()

	def get_active_image(self):
		if self.pointer_to_current_page is None:
			return self.notebook.get_nth_page(self.notebook.get_current_page())
		else:
			return self.pointer_to_current_page

	def get_file_path(self):
		return self.get_active_image().get_file_path()

	def action_reload(self, *args):
		self.get_active_image().reload_from_disk()

	def action_open(self, *args):
		"""Handle the result of an "open" file chooser dialog, and open it in
		the current tab, or in a new one, or in a new window. The decision is
		made depending on what's in the current tab, and (if any doubt)
		according to the user explicit decision."""
		gfile = self.file_chooser_open()
		if gfile is None:
			return
		else:
			file_name = gfile.get_path().split('/')[-1]
			self.prompt_message(True, _("Loading %s") % file_name)
		if self.get_active_image().should_replace():
			# If the current image is just a blank, unmodified canvas.
			self.try_load_file(gfile)
		else:
			dialog = DrMessageDialog(self)
			# Context: answer to "where do you want to open the image?"
			new_tab_id = dialog.set_action(_("New Tab"), None, True)
			# Context: answer to "where do you want to open the image?"
			new_window_id = dialog.set_action(_("New Window"), None, False)
			discard_id = dialog.set_action(_("Discard changes"), \
			                                        'destructive-action', False)
			if not self.get_active_image().is_saved():
				dialog.add_string(_("There are unsaved modifications to %s.") % \
				             self.get_active_image().get_filename_for_display())
			dialog.add_string(_("Where do you want to open %s?") % file_name)
			result = dialog.run()
			dialog.destroy()
			if result == new_tab_id:
				self.build_new_tab(gfile=gfile)
			elif result == discard_id:
				self.try_load_file(gfile)
			elif result == new_window_id:
				self.app.open_window_with_content(gfile, False)
		self.hide_message()

	def file_chooser_open(self, *args):
		"""Opens an "open" file chooser dialog, and return a GioFile or None."""
		gfile = None
		file_chooser = Gtk.FileChooserNative.new(_("Open a picture"), self,
		                     Gtk.FileChooserAction.OPEN, _("Open"), _("Cancel"))
		utilities_add_filechooser_filters(file_chooser)
		response = file_chooser.run()
		if response == Gtk.ResponseType.ACCEPT:
			gfile = file_chooser.get_file()
		file_chooser.destroy()
		return gfile

	def on_data_dropped(self, widget, drag_context, x, y, data, info, time):
		"""Signal callback: when files are dropped on `self.notebook`, a message
		dialog is shown, asking if the user prefers to open them (one new tab
		per image), or to import them (it will only import the first), or to
		cancel (if the user dropped mistakenly)."""
		dialog = DrMessageDialog(self)
		cancel_id = dialog.set_action(_("Cancel"), None, False)
		open_id = dialog.set_action(_("Open"), None, False)
		import_id = dialog.set_action(_("Import"), None, True)
		uris = data.get_uris()
		if len(uris) == 1:
			label = uris[0].split('/')[-1]
		else:
			# Context for translation:
			# "What do you want to do with *these files*?"
			label = _("these files")
		dialog.add_string(_("What do you want to do with %s?") % label)
		result = dialog.run()
		dialog.destroy()
		for uri in uris:
			# print(uri)
			# valider l'URI TODO
			if result == import_id:
				f = Gio.File.new_for_uri(uri)
				self.import_from_path(f.get_path())
				return
			elif result == open_id:
				f = Gio.File.new_for_uri(uri)
				self.build_new_tab(gfile=f)

	def try_load_file(self, gfile):
		if gfile is not None:
			self.get_active_image().try_load_file(gfile)
		self.set_picture_title() # often redundant but not useless
		self.prompt_message(False, 'file successfully loaded')

	def action_save(self, *args):
		"""Try to save the active image, and return True if the image has been
		successfully saved."""
		if self.get_file_path() is None: # Newly created and never saved image
			gfile = self.file_chooser_save()
		else:
			gfile = self.get_active_image().gfile
		return self._save_current_tab_to_gfile(gfile)

	def action_save_as(self, *args):
		gfile = self.file_chooser_save()
		self._save_current_tab_to_gfile(gfile)

	def _save_current_tab_to_gfile(self, gfile):
		"""Do everything needed to save the currently active image's pixbuf to
		the Gio.File object given as argument."""
		if gfile is None:
			# The user pressed "cancel" or closed the file chooser dialog
			return False
		fn = gfile.get_path()
		try:
			pixb = self.get_active_image().main_pixbuf
			utilities_save_pixbuf_to(pixb, fn, self, True)
			self.get_active_image().gfile = gfile
			self.get_active_image().remember_current_state()
		except Exception as e:
			if str(e) == '2': # exception has been raised because the user wants
				# to save the file under an other format (JPEG/BMP → PNG)
				self.action_save_as()
				return True
			# else the exception was raised because an actual error occured, or
			# the user clicked on "cancel"
			self.prompt_message(False, _("Failed to save %s") % fn)
			print(e)
			return False
		self.get_active_image().post_save()
		self.set_picture_title()
		return True

	def confirm_save_modifs(self):
		"""Return True if the image can be closed/overwritten (whether it's
		saved or not), or False otherwise (usually if the user clicked 'cancel',
		or if an error occurred)."""
		if self.get_active_image().is_saved():
			return True
		fn = self.get_file_path()
		if fn is None:
			unsaved_file_name = _("Untitled") + '.png'
			# Context: the sentence "There are unsaved modifications to %s."
			display_name = _("this picture")
		else:
			unsaved_file_name = fn.split('/')[-1]
			display_name = self.get_active_image().get_filename_for_display()
		dialog = DrMessageDialog(self)
		discard_id = dialog.set_action(_("Discard"), 'destructive-action', False)
		cancel_id = dialog.set_action(_("Cancel"), None, False)
		save_id = dialog.set_action(_("Save"), None, True)
		dialog.add_string( _("There are unsaved modifications to %s.") % display_name)
		self.minimap.update_minimap(True)
		image = Gtk.Image().new_from_pixbuf(self.minimap.mini_pixbuf)
		frame = Gtk.Frame(valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
		frame.add(image)
		dialog.add_widget(frame)
		result = dialog.run()
		dialog.destroy()
		if result == save_id:
			return self.action_save()
		elif result == discard_id:
			return True
		else: # cancel_id
			return False

	def file_chooser_save(self):
		"""Opens an "save" file chooser dialog, and return a GioFile or None."""
		gfile = None
		file_chooser = Gtk.FileChooserNative.new(_("Save picture as…"), self,
		                     Gtk.FileChooserAction.SAVE, _("Save"), _("Cancel"))
		utilities_add_filechooser_filters(file_chooser)

		images_dir = GLib.get_user_special_dir(GLib.USER_DIRECTORY_PICTURES)
		if images_dir != None: # no idea why it sometimes fails
			file_chooser.set_current_folder(images_dir)
		default_file_name = str(_("Untitled") + '.png')
		file_chooser.set_current_name(default_file_name)

		response = file_chooser.run()
		if response == Gtk.ResponseType.ACCEPT:
			gfile = file_chooser.get_file()
		file_chooser.destroy()
		return gfile

	def action_print(self, *args):
		self.get_active_image().print_image()

	def action_export_as(self, *args):
		gfile = self.file_chooser_save()
		if gfile is None:
			return
		pixbuf = self.get_active_image().main_pixbuf
		try:
			utilities_save_pixbuf_to(pixbuf, gfile.get_path(), self, False)
		except:
			self.prompt_message(True, _("Failed to save %s") % gfile.get_path())

	############################################################################
	# SELECTION MANAGEMENT #####################################################

	def action_getvalues(self, *args):
		"""Development only: helps debugging the selection."""
		self.get_active_image().selection.print_values()

	def action_select_all(self, *args):
		self.force_selection()
		self.get_selection_tool().select_all()

	def action_unselect(self, *args):
		self.get_selection_tool().give_back_control(False)

	def action_cut(self, *args):
		self.copy_operation()
		self.action_delete()

	def action_copy(self, *args):
		self.copy_operation()

	def copy_operation(self):
		cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		cb.set_image(self.get_active_image().selection.get_pixbuf())

	def action_delete(self, *args):
		self.get_selection_tool().delete_selection()

	def action_paste(self, *args):
		"""By default, this action pastes an image, but if there is no image in
		the clipboard, it will paste text using the text tool. Once the text
		tool is active, this action is disabled to not interfer with the default
		behavior of ctrl+v provided by the GTK text entry."""
		cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		pixbuf = cb.wait_for_image()
		if pixbuf is not None:
			self.force_selection()
			self.get_selection_tool().import_selection(pixbuf)
		else:
			string =  cb.wait_for_text()
			if string is not None:
				self.tools['text'].force_text_tool(string)

	def action_import(self, *args):
		"""Handle the result of an 'open' file chooser dialog. It will then try
		to import it as the selection."""
		file_chooser = Gtk.FileChooserNative.new(_("Import a picture"), self,
		                   Gtk.FileChooserAction.OPEN, _("Import"), _("Cancel"))
		utilities_add_filechooser_filters(file_chooser)
		response = file_chooser.run()
		if response == Gtk.ResponseType.ACCEPT:
			self.import_from_path(file_chooser.get_filename())
		file_chooser.destroy()

	def import_from_path(self, file_path):
		"""Import a file as the selection pixbuf. Called by the 'win.import'
		action or when an image is imported by drag-and-drop."""
		self.force_selection()
		pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
		self.get_selection_tool().import_selection(pixbuf)

	def action_selection_export(self, *args):
		# XXX very similar to action_export_as
		gfile = self.file_chooser_save()
		if gfile is not None:
			pixbuf = self.get_active_image().selection.get_pixbuf()
			try:
				utilities_save_pixbuf_to(pixbuf, gfile.get_path(), self, False)
			except:
				self.prompt_message(True, _("Failed to save %s") % gfile.get_path())

	def get_selection_tool(self):
		if 'rect_select' in self.tools:
			return self.tools['rect_select']
		elif 'free_select' in self.tools:
			return self.tools['free_select']
		elif 'color_select' in self.tools:
			return self.tools['color_select']
		else:
			self.prompt_message(True, _("Required tool is not available"))
			return self.active_tool()

	def force_selection(self, *args):
		self.get_selection_tool().row.set_active(True) # XXX appeler enable tool ?

	def action_apply_canvas_tool(self, *args):
		self.active_tool().on_apply_temp_pixbuf_tool_operation()

	############################################################################
	# HISTORY MANAGEMENT #######################################################

	def action_undo(self, *args):
		# self.prompt_message(True, _("Undoing…"))
		self.get_active_image().try_undo()
		# self.prompt_message(False, 'finished undoing')

	def action_redo(self, *args):
		self.get_active_image().try_redo()

	def action_restore(self, *args):
		"""[Dev only] show the last saved pixbuf on the canvas."""
		self.get_active_image().use_stable_pixbuf()
		self.get_active_image().update()

	def action_rebuild(self, *args):
		"""[Dev only] rebuild the image according to the history content."""
		self.get_active_image()._history._rebuild_from_history()

	def update_history_actions_labels(self, undo_label, redo_label):
		self._decorations.set_undo_label(undo_label)
		self._decorations.set_redo_label(redo_label)
		# TODO maybe update "undo" and "redo" items in the menubar too

	############################################################################
	# PREVIEW, NAVIGATION AND ZOOM ACTIONS #####################################

	def action_toggle_preview(self, *args):
		"""Action callback, showing or hiding the "minimap" preview popover."""
		preview_visible = not args[0].get_state()
		if preview_visible:
			self.minimap.popup()
			self.minimap.update_minimap(True)
		else:
			self.minimap.popdown()
		args[0].set_state(GLib.Variant.new_boolean(preview_visible))

	def action_go_up(self, *args):
		self.get_active_image().add_deltas(0, -1, 100)

	def action_go_down(self, *args):
		self.get_active_image().add_deltas(0, 1, 100)

	def action_go_left(self, *args):
		self.get_active_image().add_deltas(-1, 0, 100)

	def action_go_right(self, *args):
		self.get_active_image().add_deltas(1, 0, 100)

	def action_zoom_in(self, *args):
		self.get_active_image().inc_zoom_level(25)

	def action_zoom_out(self, *args):
		self.get_active_image().inc_zoom_level(-25)

	def action_zoom_100(self, *args):
		self.get_active_image().set_zoom_level(100)

	def action_zoom_opti(self, *args):
		self.get_active_image().set_opti_zoom_level()

	############################################################################
################################################################################

