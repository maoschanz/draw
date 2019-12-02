# abstract_canvas_tool.py
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

from .abstract_tool import AbstractAbstractTool

class AbstractCanvasTool(AbstractAbstractTool):
	__gtype_name__ = 'AbstractCanvasTool'

	def __init__(self, tool_id, label, icon_name, window, **kwargs):
		super().__init__(tool_id, label, icon_name, window)
		self.menu_id = 1
		self.centered_box = None
		self.needed_width_for_long = 0
		self.accept_selection = True

	def on_tool_selected(self, *args):
		super().on_tool_selected()
		self.apply_to_selection = self.selection_is_active()

	def give_back_control(self, preserve_selection):
		if not preserve_selection and self.selection_is_active():
			self.on_apply_temp_pixbuf_tool_operation()
			self.window.get_selection_tool().unselect_and_apply()
		super().give_back_control(preserve_selection)

	############################################################################

	def build_and_do_op(self):
		operation = self.build_operation()
		self.do_tool_operation(operation)

	def temp_preview(self, is_selection, local_dx, local_dy):
		"""Part of the previewing methods shared by all canvas tools."""
		cairo_context = cairo.Context(self.get_surface())
		pixbuf = self.get_image().get_temp_pixbuf()
		if is_selection:
			cairo_context.set_source_surface(self.get_surface(), 0, 0)
			cairo_context.paint()
			x = self.get_selection().selection_x + local_dx
			y = self.get_selection().selection_y + local_dy
			Gdk.cairo_set_source_pixbuf(cairo_context, pixbuf, x, y)
			cairo_context.paint()
		else:
			cairo_context.set_operator(cairo.Operator.CLEAR)
			cairo_context.paint()
			cairo_context.set_operator(cairo.Operator.OVER)
			Gdk.cairo_set_source_pixbuf(cairo_context, pixbuf, 0, 0)
			cairo_context.paint()
		self.get_image().update()

	############################################################################

	def on_apply_temp_pixbuf_tool_operation(self, *args):
		self.restore_pixbuf()
		operation = self.build_operation()
		self.apply_operation(operation)
		if self.apply_to_selection:
			self.window.force_selection()
		else:
			self.window.back_to_previous()

	def apply_operation(self, operation):
		operation['is_preview'] = False
		super().apply_operation(operation)
		self.get_image().reset_temp()

	def common_end_operation(self, op):
		if op['is_preview']:
			self.temp_preview(op['is_selection'], op['local_dx'], op['local_dy'])
		else:
			self.apply_temp(op['is_selection'], op['local_dx'], op['local_dy'])

	def apply_temp(self, operation_is_selection, local_dx, local_dy):
		if operation_is_selection:
			pixbuf = self.get_image().get_temp_pixbuf().copy() # copy ??
			self.get_selection().set_pixbuf(pixbuf)
			x = self.get_selection().selection_x + local_dx
			y = self.get_selection().selection_y + local_dy
			self.get_selection().set_coords(True, x, y) # XXX si on reste sur
			# True, l'overlay s'en trouve décalée, mais avec False ça nique tout
			# au moment de la désélection
		else:
			self.get_image().main_pixbuf = self.get_image().get_temp_pixbuf().copy()
			self.get_image().use_stable_pixbuf()

	############################################################################

	def get_handle_cursor_name(self, event_x, event_y):
		"""Return the name of the accurate cursor for tools such as `scale` or
		`crop`, with or without an active selection, depending on the size and
		position of the resized/cropped area."""
		height = self.get_image().temp_pixbuf.get_height()
		width = self.get_image().temp_pixbuf.get_width()
		w_left, w_right, h_top, h_bottom = self.get_image().get_corrected_coords(\
		                     0, width, 0, height, self.apply_to_selection, True)
		# Comment to help the debug:
		h_top += 0.4 * height
		h_bottom -= 0.4 * height
		w_left += 0.4 * width
		w_right -= 0.4 * width
		# print("get_handle_cursor_name", w_left, w_right, h_top, h_bottom)

		cursor_name = ''
		if event_y < h_top:
			cursor_name = cursor_name + 'n'
		elif event_y > h_bottom:
			cursor_name = cursor_name + 's'
		if event_x < w_left:
			cursor_name = cursor_name + 'w'
		elif event_x > w_right:
			cursor_name = cursor_name + 'e'

		if cursor_name == '':
			cursor_name = 'not-allowed'
		else:
			cursor_name = cursor_name + '-resize'
		return cursor_name

	def on_draw(self, area, cairo_context):
		pass

	def get_deformed_surface(self, source_surface, coefs):
		"""Use cairo.Matrix to apply a transformation to `source_surface` using
		the coefficients in `coefs` and return a new surface with the result."""
		p_xx, p_yx, p_xy, p_yy, p_x0, p_y0 = coefs

		source_w = source_surface.get_width()
		source_h = source_surface.get_height()
		# w = p_xx * source_w + p_xy * 0 + p_x0
		# h = p_yx * 0 + p_yy * source_h + p_y0
		normal_w = p_xx * source_w + p_xy * source_h + p_x0
		normal_h = p_yx * source_w + p_yy * source_h + p_y0
		# w = abs( p_xx * source_w ) + abs( p_xy * source_h ) + p_x0
		# h = abs( p_yx * source_w ) + abs( p_yy * source_h ) + p_y0

		# print('source_w, source_h', source_w, source_h)
		# print('normal_w, normal_h', normal_w, normal_h)
		# print('p_x0, p_y0', p_x0, p_y0 )

		# w = max(w, source_w) + p_x0
		# h = max(h, source_h) + p_y0

		w = max(normal_w, source_w + p_x0)
		h = max(normal_h, source_h + p_y0) # FIXME non toujours pas ?

		new_surface = cairo.ImageSurface(cairo.Format.ARGB32, int(w), int(h))
		cairo_context = cairo.Context(new_surface)
		# m = cairo.Matrix(xx=1.0, yx=0.0, xy=0.0, yy=1.0, x0=0.0, y0=0.0)
		m = cairo.Matrix(xx=p_xx, yx=p_yx, xy=p_xy, yy=p_yy, x0=p_x0, y0=p_y0)
		cairo_context.transform(m)
		cairo_context.set_source_surface(source_surface, 0, 0)
		# FIXME scroll and zoom ?
		cairo_context.paint()
		return new_surface

	############################################################################
################################################################################

