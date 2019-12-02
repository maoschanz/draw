# tool_scale.py
#
# Copyright 2019 Romain F. T.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import cairo
from gi.repository import Gtk, Gdk, GdkPixbuf

from .abstract_canvas_tool import AbstractCanvasTool
from .bottombar import DrawingAdaptativeBottomBar

from .utilities import utilities_add_unit_to_spinbtn
from .utilities_tools import utilities_show_handles_on_context

class ToolScale(AbstractCanvasTool):
	__gtype_name__ = 'ToolScale'

	def __init__(self, window):
		super().__init__('scale', _("Scale"), 'tool-scale-symbolic', window)
		self.cursor_name = 'not-allowed'
		self.keep_proportions = True
		self._x = 0
		self._y = 0
		self.x_press = 0
		self.y_press = 0
		self.add_tool_action_boolean('scale-proportions', False)
		# self.add_tool_action_boolean('scale-deformation', False) # TODO ?

	def try_build_panel(self):
		self.panel_id = 'scale'
		self.window.options_manager.try_add_bottom_panel(self.panel_id, self)

	def build_bottom_panel(self):
		bar = ScaleToolPanel(self.window, self)
		self.width_btn = bar.width_btn
		self.height_btn = bar.height_btn
		self.width_btn.connect('value-changed', self.on_width_changed)
		self.height_btn.connect('value-changed', self.on_height_changed)
		return bar

	def get_edition_status(self):
		if self.apply_to_selection:
			return _("Scaling the selection")
		else:
			return _("Scaling the canvas")

	############################################################################

	def should_set_value(self, *args):
		current_prop = self.get_width() / self.get_height()
		return self.keep_proportions and self.proportion != current_prop

	def try_set_keep_proportions(self, *args):
		if self.keep_proportions == self.get_option_value('scale-proportions'):
			return
		self.keep_proportions = self.get_option_value('scale-proportions')
		if self.keep_proportions:
			self.proportion = self.get_width() / self.get_height()

	def on_tool_selected(self, *args):
		super().on_tool_selected()
		self._x = 0
		self._y = 0
		if self.apply_to_selection:
			width = self.get_selection_pixbuf().get_width()
			height = self.get_selection_pixbuf().get_height()
		else:
			width = self.get_image().get_pixbuf_width()
			height = self.get_image().get_pixbuf_height()
		self.keep_proportions = self.get_option_value('scale-proportions')
		self.proportion = width/height
		self.width_btn.set_value(width)
		self.height_btn.set_value(height)

	def on_width_changed(self, *args):
		self.try_set_keep_proportions()
		if self.should_set_value():
			self.height_btn.set_value(self.get_width() / self.proportion)
		self.build_and_do_op()

	def on_height_changed(self, *args):
		self.try_set_keep_proportions()
		if self.should_set_value():
			self.width_btn.set_value(self.get_height() * self.proportion)
		else:
			self.build_and_do_op()

	def get_width(self):
		return self.width_btn.get_value_as_int()

	def get_height(self):
		return self.height_btn.get_value_as_int()

	############################################################################

	def on_unclicked_motion_on_area(self, event, surface):
		self.cursor_name = self.get_handle_cursor_name(event.x, event.y)
		self.window.set_cursor(True)

	def on_press_on_area(self, event, surface, event_x, event_y):
		self.x_press = event.x
		self.y_press = event.y

	def on_motion_on_area(self, event, surface, event_x, event_y):
		if self.cursor_name == 'not-allowed':
			return
		else:
			directions = self.cursor_name.replace('-resize', '')
		delta_x = event.x - self.x_press
		delta_y = event.y - self.y_press
		self.x_press = event.x
		self.y_press = event.y

		height = self.get_height()
		width = self.get_width()
		if 'n' in directions:
			height -= delta_y
			self._y = self._y + delta_y
		if 's' in directions:
			height += delta_y
		if 'w' in directions:
			width -= delta_x
			self._x = self._x + delta_x
		if 'e' in directions:
			width += delta_x

		if self.apply_to_selection:
			# XXX pas ce que je veux, mais ça limite la casse
			self._x = min(self._x + self.get_width(), self._x)
			self._y = min(self._y + self.get_height(), self._y)

		if self.keep_proportions:
			# XXX Les erreurs liées aux arrondis s'ajoutent et ça fait pas mal
			# bouger la sélection alors que ça ne devrait pas
			if abs(delta_y) > abs(delta_x):
				self.height_btn.set_value(height)
			else:
				self.width_btn.set_value(width)
		else:
			self.height_btn.set_value(height)
			self.width_btn.set_value(width)

	def on_release_on_area(self, event, surface, event_x, event_y):
		self.on_motion_on_area(event, surface, event_x, event_y)
		self.build_and_do_op() # techniquement déjà fait

	############################################################################

	def on_draw(self, area, cairo_context):
		if self.apply_to_selection:
			x1 = int(self._x)
			y1 = int(self._y)
		else:
			x1 = 0
			y1 = 0
		x2 = x1 + self.get_width()
		y2 = y1 + self.get_height()
		x1, x2, y1, y2 = self.get_image().get_corrected_coords(x1, x2, y1, y2, \
		                                         self.apply_to_selection, False)
		utilities_show_handles_on_context(cairo_context, x1, x2, y1, y2)
		# FIXME bien excepté les delta locaux : quand on rogne depuis le haut ou
		# la gauche, les coordonées de référence des poignées ne sont plus
		# correctes.

	############################################################################

	def build_operation(self):
		operation = {
			'tool_id': self.id,
			'is_selection': self.apply_to_selection,
			'is_preview': True,
			'local_dx': int(self._x),
			'local_dy': int(self._y),
			'width': self.get_width(),
			'height': self.get_height()
		}
		return operation

	def do_tool_operation(self, operation):
		if operation['tool_id'] != self.id:
			return
		self.restore_pixbuf()

		if operation['is_selection']:
			source_pixbuf = self.get_selection_pixbuf()
		else:
			source_pixbuf = self.get_main_pixbuf()
		self.get_image().set_temp_pixbuf(source_pixbuf.scale_simple( \
		   operation['width'], operation['height'], GdkPixbuf.InterpType.TILES))
		self.common_end_operation(operation)

	############################################################################
################################################################################

class ScaleToolPanel(DrawingAdaptativeBottomBar):
	__gtype_name__ = 'ScaleToolPanel'

	def __init__(self, window, scale_tool):
		super().__init__()
		self.window = window
		# knowing the tool is needed because the panel doesn't compact the same
		# way if it's applied to the selection
		self.scale_tool = scale_tool
		builder = self.build_ui('tools/ui/tool_scale.ui')

		self.width_btn = builder.get_object('width_btn')
		self.height_btn = builder.get_object('height_btn')
		utilities_add_unit_to_spinbtn(self.height_btn, 4, 'px')
		utilities_add_unit_to_spinbtn(self.width_btn, 4, 'px')

		self.options_btn = builder.get_object('options_btn')

		self.width_label = builder.get_object('width_label')
		self.height_label = builder.get_object('height_label')
		self.separator = builder.get_object('separator')

	def toggle_options_menu(self):
		self.options_btn.set_active(not self.options_btn.get_active())

	def init_adaptability(self):
		super().init_adaptability()
		temp_limit_size = self.centered_box.get_preferred_width()[0] + \
		                    self.cancel_btn.get_preferred_width()[0] + \
		                   self.options_btn.get_preferred_width()[0] + \
		                     self.apply_btn.get_preferred_width()[0]
		self.set_limit_size(temp_limit_size)

	def set_compact(self, state):
		super().set_compact(state)
		if state:
			self.centered_box.set_orientation(Gtk.Orientation.VERTICAL)
		else:
			self.centered_box.set_orientation(Gtk.Orientation.HORIZONTAL)
		self.width_label.set_visible(not state)
		self.height_label.set_visible(not state)
		self.separator.set_visible(not state)

		# if self.scale_tool.apply_to_selection:
		# 	self.???.set_visible(state)
		# else:
		# 	self.???.set_visible(state)

	############################################################################
################################################################################

