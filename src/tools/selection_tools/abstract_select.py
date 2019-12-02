# abstract_select.py

from gi.repository import Gtk, Gdk, GdkPixbuf
import cairo

from .abstract_tool import AbstractAbstractTool
from .bottombar import DrawingAdaptativeBottomBar

from .utilities_tools import utilities_show_overlay_on_context

class AbstractSelectionTool(AbstractAbstractTool):
	__gtype_name__ = 'AbstractSelectionTool'
	# x_press = 0
	# y_press = 0
	# future_x = 0
	# future_y = 0
	future_path = None
	# future_pixbuf = None
	# operation_type = None # 'op-define'

	def __init__(self, tool_id, label, icon_name, window, **kwargs):
		super().__init__(tool_id, label, icon_name, window)
		self.menu_id = 2
		self.accept_selection = True

		# XXX ???????????? what should i do here
		self.x_press = 0
		self.y_press = 0
		self.local_dx = 0
		self.local_dy = 0
		self.future_x = 0
		self.future_y = 0
		# self.future_path = None
		self.future_pixbuf = None
		self.operation_type = None # 'op-define'

	############################################################################
	# UI implementations #######################################################

	def get_edition_status(self):
		if self.selection_is_active():
			label = _("Drag the selection or right-click on the canvas")
		else:
			label = _("Select an area or right-click on the canvas")
		return label

	def get_options_model(self):
		fpath = '/com/github/maoschanz/drawing/ui/selection-menus.ui'
		builder = Gtk.Builder.new_from_resource(fpath)
		return builder.get_object('options-menu')

	def try_build_panel(self):
		self.panel_id = 'selection'
		self.window.options_manager.try_add_bottom_panel(self.panel_id, self)

	def build_bottom_panel(self):
		return SelectionToolPanel(self.window)

	############################################################################
	# Lifecycle implementations ################################################

	def give_back_control(self, preserve_selection):
		self.get_selection().hide_popovers()
		# TODO tout le bazar sur has_been_used
		if not preserve_selection:
			self.unselect_and_apply()

	def on_tool_selected(self, *args):
		print("selected", self.get_image())
		# XXX rien, vraiment ?

	def on_tool_unselected(self, *args):
		print("unselected", self.get_image())
		# XXX rien, vraiment ?

	# def cancel_ongoing_operation(self):
	# 	self.get_image().selection.reset()
	# 	return True

	############################################################################
	############################################################################

	def get_press_behavior(self, event):
		if event.button == 3:
			return 'menu'
		elif not self.selection_is_active():
			return 'define'
		elif self.get_selection().point_is_in_selection(self.x_press, self.y_press):
			return 'drag'
		else:
			return 'cancel'

	def press_define(self, event_x, event_y):
		pass # implemented by actual tools

	def motion_define(self, event_x, event_y):
		pass # implemented by actual tools

	def release_define(self, surface, event_x, event_y):
		pass # implemented by actual tools

	def drag_to(self, event_x, event_y):
		x = self.get_selection().selection_x
		y = self.get_selection().selection_y
		self.future_x = x + event_x - self.x_press
		self.future_y = y + event_y - self.y_press
		self.operation_type = 'op-drag'
		operation = self.build_operation()
		self.do_tool_operation(operation)
		self.operation_type = 'op-define'

	def preview_drag_to(self, event_x, event_y):
		self.local_dx = event_x - self.x_press
		self.local_dy = event_y - self.y_press
		self.non_destructive_show_modif()

	############################################################################
	# Signal callbacks implementations #########################################

	def on_press_on_area(self, event, surface, event_x, event_y):
		self.x_press = event_x
		self.y_press = event_y
		self.behavior = self.get_press_behavior(event)
		# print('press', self.behavior)
		if self.behavior == 'drag':
			self.cursor_name = 'grabbing'
			self.window.set_cursor(True)
		elif self.behavior == 'define':
			self.press_define(event_x, event_y)
		elif self.behavior == 'cancel':
			self.unselect_and_apply()
			self.restore_pixbuf()
			self.non_destructive_show_modif()

	def on_motion_on_area(self, event, surface, event_x, event_y):
		if self.behavior == 'define':
			self.motion_define(event_x, event_y)
		elif self.behavior == 'drag':
			self.preview_drag_to(event_x, event_y)

	def on_unclicked_motion_on_area(self, event, surface):
		x = event.x + self.get_image().scroll_x
		y = event.y + self.get_image().scroll_y
		if not self.selection_is_active():
			self.cursor_name = 'cross'
		elif self.get_selection().point_is_in_selection(x, y):
			self.cursor_name = 'grab'
		else:
			self.cursor_name = 'cross'
		self.window.set_cursor(True)

	def on_release_on_area(self, event, surface, event_x, event_y):
		self.get_selection().set_popovers_position(event.x, event.y)
		if event.button == 3:
			self.get_selection().show_popover()
			return
		self.restore_pixbuf()
		if self.behavior == 'define':
			self.release_define(surface, event_x, event_y)
		elif self.behavior == 'drag':
			self.drag_to(event_x, event_y)

	def on_draw(self, area, cairo_context):
		if not self.selection_is_active():
			return
		self.get_selection().show_selection_on_surface(cairo_context, True, \
		                                           self.local_dx, self.local_dy)
		dragged_path = self.get_selection().get_path_with_scroll(self.local_dx, \
		                                                  self.local_dy) # TODO
		# i should give it something corresponding temporary selection_x/y when
		# the selection is moving. Method not really use elsewhere.
		utilities_show_overlay_on_context(cairo_context, dragged_path, True)

	############################################################################
	# Path management ##########################################################

	def tool_select_all(self):
		total_w = self.get_main_pixbuf().get_width()
		total_h = self.get_main_pixbuf().get_height()
		self.build_rectangle_path(0, 0, total_w, total_h)
		self.operation_type = 'op-define'
		operation = self.build_operation()
		self.apply_operation(operation)
		self.get_selection().show_popover()

	def build_rectangle_path(self, press_x, press_y, release_x, release_y):
		cairo_context = cairo.Context(self.get_surface())
		x0 = int( min(press_x, release_x) )
		y0 = int( min(press_y, release_y) )
		x1 = int( max(press_x, release_x) )
		y1 = int( max(press_y, release_y) )
		w = x1 - x0
		h = y1 - y0
		if w <= 0 or h <= 0:
			# AbstractSelectionTool.future_path = None
			return
		self.future_x = x0
		self.future_y = y0
		cairo_context.new_path()
		cairo_context.move_to(x0, y0)
		cairo_context.line_to(x1, y0)
		cairo_context.line_to(x1, y1)
		cairo_context.line_to(x0, y1)
		cairo_context.close_path()
		AbstractSelectionTool.future_path = cairo_context.copy_path()

	def set_future_coords_for_free_path(self):
		main_width = self.get_main_pixbuf().get_width()
		main_height = self.get_main_pixbuf().get_height()
		xmin, ymin = main_width, main_height # TODO cairo_context.path_extents()
		for pts in AbstractSelectionTool.future_path:
			if pts[1] is not ():
				xmin = min(pts[1][0], xmin)
				ymin = min(pts[1][1], ymin)
		self.future_x = max(xmin, 0.0)
		self.future_y = max(ymin, 0.0)

	############################################################################
	# Operations management methods ############################################

	def update_surface(self):
		operation = self.build_operation()
		self.do_tool_operation(operation)
		self.non_destructive_show_modif()

	def delete_selection(self):
		self.operation_type = 'op-delete'
		operation = self.build_operation()
		self.apply_operation(operation)
		self.operation_type = 'op-define'

	def import_selection(self, pixbuf):
		self.unselect_and_apply()
		self.future_pixbuf = pixbuf
		self.operation_type = 'op-import'
		operation = self.build_operation()
		self.apply_operation(operation)
		self.operation_type = 'op-define'

	def unselect_and_apply(self):
		if self.operation_type is None:
			print('none') # FIXME le bug des outils de sélections incompatibles entre eux
			return # TODO raise something goddammit
		self.operation_type = 'op-apply'
		operation = self.build_operation()
		self.apply_operation(operation)
		self.operation_type = 'op-define'
		self.cursor_name = 'cross'
		self.window.set_cursor(True)

	#####

	def op_import(self, operation):
		if operation['pixbuf'] is None:
			return # TODO raise something goddammit
		self.get_selection().set_pixbuf(operation['pixbuf'].copy())

	def op_clean(self, operation):
		if operation['initial_path'] is None:
			return # TODO raise something goddammit
		cairo_context = cairo.Context(self.get_surface())
		cairo_context.new_path()
		cairo_context.append_path(operation['initial_path'])
		cairo_context.set_operator(cairo.Operator.CLEAR)
		cairo_context.fill()
		cairo_context.set_operator(cairo.Operator.OVER)

	def op_drag(self, op):
		# print('drag to : ', op['pixb_x'], op['pixb_y'])
		self.get_selection().set_coords(False, op['pixb_x'], op['pixb_y'])
		self.non_destructive_show_modif()

	def op_define(self, op):
		if op['initial_path'] is None:
			return # TODO raise something goddammit
		self.get_selection().set_coords(True, op['pixb_x'], op['pixb_y'])
		self.get_selection().load_from_path(op['initial_path'])

	def op_apply(self):
		cairo_context = cairo.Context(self.get_surface())
		self.get_selection().show_selection_on_surface(cairo_context, False, \
		                                           self.local_dx, self.local_dy)
		self.get_selection().reset()
		# self.future_path = None
		AbstractSelectionTool.future_path = None

	############################################################################
	# Operations management implementations ####################################

	def build_operation(self):
		if self.future_pixbuf is None: # Cas normal
			pixbuf = None
		else: # Cas des importations uniquement
			pixbuf = self.future_pixbuf.copy()
		operation = {
			'tool_id': self.id,
			'operation_type': self.operation_type,
			'initial_path': AbstractSelectionTool.future_path,
			'pixbuf': pixbuf,
			'pixb_x': int(self.future_x),
			'pixb_y': int(self.future_y)
		}
		return operation

	def do_tool_operation(self, operation):
		if operation['tool_id'] != self.id:
			return
		self.restore_pixbuf()
		# print('operation_type', operation['operation_type'])
		if operation['operation_type'] == 'op-delete':
			# Opération instantanée (sans preview), correspondant à une action
			# de type "clic-droit > couper" ou "clic-droit > supprimer".
			# On réinitialise le selection_manager.
			self.get_selection().reset()
		elif operation['operation_type'] == 'op-import':
			# Opération instantanée (sans preview), correspondant à une action
			# de type "clic-droit > importer" ou "clic-droit > coller".
			# On charge un pixbuf dans le selection_manager.
			self.op_import(operation)
		elif operation['operation_type'] == 'op-define':
			# Opération instantanée (sans preview), correspondant à une sélection
			# (rectangulaire ou non) par définition d'un path.
			# On charge un pixbuf dans le selection_manager.
			self.op_define(operation)
			self.op_clean(operation)
		elif operation['operation_type'] == 'op-drag':
			# Prévisualisation d'opération, correspondant à la définition d'une
			# sélection (rectangulaire ou non) par construction d'un path.
			# On modifie les coordonnées connues du selection_manager.
			self.local_dx = 0
			self.local_dy = 0
			self.op_drag(operation)
		elif operation['operation_type'] == 'op-apply':
			# Opération instantanée correspondant à l'aperçu de l'op-drag, donc
			# la définition d'une sélection (rectangulaire ou non) par
			# construction d'un path qui sera "fusionné" au main_pixbuf.
			# On modifie les coordonnées connues du selection_manager.
			if self.get_selection_pixbuf() is None:
				return
			self.op_drag(operation)
			self.op_apply()

	############################################################################
################################################################################

class SelectionToolPanel(DrawingAdaptativeBottomBar):
	__gtype_name__ = 'SelectionToolPanel'

	def __init__(self, window):
		super().__init__()
		self.window = window
		builder = self.build_ui('ui/selection-panel.ui')
		self.import_box_narrow = builder.get_object('import_box_narrow')
		self.import_box_long = builder.get_object('import_box_long')
		self.cb_box_narrow = builder.get_object('cb_box_narrow')
		self.actions_btn = builder.get_object('actions_btn')
		self.minimap_btn = builder.get_object('minimap_btn')
		self.minimap_label = builder.get_object('minimap_label')
		self.minimap_arrow = builder.get_object('minimap_arrow')

	def get_minimap_btn(self):
		return self.minimap_btn

	def set_minimap_label(self, label):
		self.minimap_label.set_label(label)

	def toggle_options_menu(self):
		self.actions_btn.set_active(not self.actions_btn.get_active())

	def init_adaptability(self):
		super().init_adaptability()
		temp_limit_size = self.import_box_long.get_preferred_width()[0] + \
		                    self.cb_box_narrow.get_preferred_width()[0] + \
		                      self.actions_btn.get_preferred_width()[0] + \
		                      self.minimap_btn.get_preferred_width()[0]
		self.set_limit_size(temp_limit_size)

	def set_compact(self, state):
		super().set_compact(state)
		self.import_box_narrow.set_visible(state)
		self.import_box_long.set_visible(not state)
		self.minimap_arrow.set_visible(not state)

	############################################################################
################################################################################

