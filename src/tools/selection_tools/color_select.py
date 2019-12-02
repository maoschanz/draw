# tool_select.py

from gi.repository import Gtk, Gdk, GdkPixbuf
import cairo

from .abstract_select import AbstractSelectionTool
from .utilities_tools import utilities_get_magic_path

class ToolColorSelect(AbstractSelectionTool):
	__gtype_name__ = 'ToolColorSelect'

	def __init__(self, window, **kwargs):
		super().__init__('color_select', _("Color selection"), 'tool-magic-symbolic', window)

	def press_define(self, event_x, event_y):
		pass

	def motion_define(self, event_x, event_y):
		pass

	def release_define(self, surface, event_x, event_y):
		AbstractSelectionTool.future_path = utilities_get_magic_path(surface, \
		                                       event_x, event_y, self.window, 1)
		if AbstractSelectionTool.future_path is None:
			return
		self.operation_type = 'op-define'
		self.set_future_coords_for_free_path()
		operation = self.build_operation()
		self.apply_operation(operation)

	############################################################################
################################################################################

