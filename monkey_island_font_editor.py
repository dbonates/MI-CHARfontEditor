#!/usr/bin/env python3
"""
Monkey Island Bitmap Font Editor
A specialized pixel editor for editing The Secret of Monkey Island bitmap font files.
Preserves the original color palette (2 tones of pink) without modification.
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QPushButton, QFileDialog, QMessageBox, QGridLayout,
    QFrame, QSizePolicy, QButtonGroup
)
from PyQt6.QtCore import Qt, QSize, QRect, pyqtSignal
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QColor, QPen, QMouseEvent, QPaintEvent
)
from PIL import Image
import struct


class PixelEditorCanvas(QWidget):
    """Canvas widget for pixel-level editing with zoom and grid."""
    
    pixelChanged = pyqtSignal(int, int, int)  # x, y, color_index
    characterJumped = pyqtSignal(int)  # character index
    historyChanged = pyqtSignal()  # Emitted when undo/redo state changes
    selectionChanged = pyqtSignal(bool)  # Emitted when selection state changes (has_selection)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.original_palette = None
        self.zoom_level = 20  # pixels per pixel
        self.grid_enabled = True
        self.current_color_index = 1
        self.drawing = False
        self.char_height = 8  # Standard 8-pixel tall characters
        self.show_char_indices = True
        self.hover_y = -1
        
        # Selection and clipboard
        self.selecting = False
        self.selection_start = None
        self.selection_end = None
        self.clipboard_data = None  # Stores copied pixel data
        self.clipboard_size = None  # (width, height)
        self.paste_mode = False
        self.paste_position = None  # Current paste preview position
        self.paste_dragging = False
        
        # Edit mode: 'draw' or 'select'
        self.edit_mode = 'draw'
        
        # Undo/Redo history
        self.undo_stack = []  # List of (pixel_data, description)
        self.redo_stack = []  # List of (pixel_data, description)
        self.max_history = 50  # Maximum undo levels
        
        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)
        
    def load_image(self, image_path):
        """Load bitmap image and extract palette."""
        # Load with PIL to preserve palette
        pil_image = Image.open(image_path)
        
        # Store original palette
        if pil_image.mode == 'P':
            self.original_palette = pil_image.getpalette()
        
        # Convert to indexed color for Qt
        if pil_image.mode != 'P':
            pil_image = pil_image.convert('P')
        
        # Convert to QImage while preserving palette
        width, height = pil_image.size
        
        # Auto-detect character height based on bitmap height
        if height == 2048:  # 256 chars * 8
            self.char_height = 8
        elif height == 2259:  # 256 chars * 9
            self.char_height = 9
        elif height == 3390:  # 256 chars * 15
            self.char_height = 15
        elif height == 3584:  # 256 chars * 14
            self.char_height = 14
        else:
            # Calculate by dividing by 256 (extended ASCII)
            self.char_height = height // 256
            if self.char_height < 1:
                self.char_height = 8  # fallback
        
        self.image = QImage(width, height, QImage.Format.Format_Indexed8)
        
        # Set palette
        if self.original_palette:
            palette = self.original_palette[:768]  # RGB triplets
            for i in range(256):
                r = palette[i * 3] if i * 3 < len(palette) else 0
                g = palette[i * 3 + 1] if i * 3 + 1 < len(palette) else 0
                b = palette[i * 3 + 2] if i * 3 + 2 < len(palette) else 0
                self.image.setColor(i, QColor(r, g, b).rgb())
        
        # Copy pixel data
        pixel_data = pil_image.tobytes()
        for y in range(height):
            for x in range(width):
                idx = y * width + x
                if idx < len(pixel_data):
                    self.image.setPixel(x, y, pixel_data[idx])
        
        self.update_size()
        self.update()
        
        # Clear undo/redo history for new image
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.historyChanged.emit()
        
    def update_size(self):
        """Update widget size based on image and zoom."""
        if self.image:
            new_size = QSize(
                self.image.width() * self.zoom_level,
                self.image.height() * self.zoom_level
            )
            self.setFixedSize(new_size)
            
    def paintEvent(self, event: QPaintEvent):
        """Draw the zoomed pixel grid."""
        if not self.image:
            return
            
        painter = QPainter(self)
        
        # Draw pixels
        for y in range(self.image.height()):
            for x in range(self.image.width()):
                color_idx = self.image.pixelIndex(x, y)
                color = QColor.fromRgb(self.image.color(color_idx))
                
                rect = QRect(
                    x * self.zoom_level,
                    y * self.zoom_level,
                    self.zoom_level,
                    self.zoom_level
                )
                painter.fillRect(rect, color)
        
        # Draw grid
        if self.grid_enabled:
            painter.setPen(QPen(QColor(100, 100, 100, 100), 1))
            for x in range(self.image.width() + 1):
                painter.drawLine(
                    x * self.zoom_level, 0,
                    x * self.zoom_level, self.image.height() * self.zoom_level
                )
            for y in range(self.image.height() + 1):
                painter.drawLine(
                    0, y * self.zoom_level,
                    self.image.width() * self.zoom_level, y * self.zoom_level
                )
        
        # Draw character index overlays
        if self.show_char_indices and self.char_height > 0:
            num_chars = self.image.height() // self.char_height
            for char_idx in range(num_chars):
                y_start = char_idx * self.char_height * self.zoom_level
                y_end = (char_idx + 1) * self.char_height * self.zoom_level
                
                # Highlight on hover
                is_hovered = (self.hover_y >= char_idx * self.char_height and 
                             self.hover_y < (char_idx + 1) * self.char_height)
                
                # Draw character boundary
                if char_idx > 0:
                    painter.setPen(QPen(QColor(255, 0, 0, 150) if is_hovered else QColor(0, 255, 0, 80), 2))
                    painter.drawLine(0, y_start, self.image.width() * self.zoom_level, y_start)
                
                # Draw character index label
                ascii_val = char_idx
                char_repr = chr(ascii_val) if 32 <= ascii_val < 127 else '·'
                label_text = f"#{char_idx} (ASCII {ascii_val}: '{char_repr}')"
                
                # Background for text
                painter.setPen(Qt.PenStyle.NoPen)
                if is_hovered:
                    painter.setBrush(QColor(255, 255, 0, 200))
                else:
                    painter.setBrush(QColor(0, 0, 0, 180))
                text_rect = QRect(5, y_start + 2, 300, 16)
                painter.drawRect(text_rect)
                
                # Text
                painter.setPen(QColor(255, 255, 255) if not is_hovered else QColor(0, 0, 0))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label_text)
        
        # Draw selection rectangle
        if self.selection_start and self.selection_end:
            x1 = min(self.selection_start[0], self.selection_end[0]) * self.zoom_level
            y1 = min(self.selection_start[1], self.selection_end[1]) * self.zoom_level
            x2 = max(self.selection_start[0], self.selection_end[0]) * self.zoom_level + self.zoom_level
            y2 = max(self.selection_start[1], self.selection_end[1]) * self.zoom_level + self.zoom_level
            
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
        
        # Draw paste preview
        if self.paste_mode and self.paste_position and self.clipboard_data and self.clipboard_size:
            px, py = self.paste_position
            cw, ch = self.clipboard_size
            
            # Draw semi-transparent preview
            painter.setOpacity(0.7)
            for dy in range(ch):
                for dx in range(cw):
                    if dy * cw + dx < len(self.clipboard_data):
                        color_idx = self.clipboard_data[dy * cw + dx]
                        color = QColor.fromRgb(self.image.color(color_idx))
                        
                        rect = QRect(
                            (px + dx) * self.zoom_level,
                            (py + dy) * self.zoom_level,
                            self.zoom_level,
                            self.zoom_level
                        )
                        painter.fillRect(rect, color)
            
            painter.setOpacity(1.0)
            # Draw border around paste preview
            painter.setPen(QPen(QColor(0, 255, 0), 2, Qt.PenStyle.SolidLine))
            painter.drawRect(
                px * self.zoom_level,
                py * self.zoom_level,
                cw * self.zoom_level,
                ch * self.zoom_level
            )
    
    def mousePressEvent(self, event: QMouseEvent):
        """Start drawing, selecting, or paste dragging."""
        if not self.image:
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.paste_mode:
                # Start dragging paste preview or commit paste
                x = event.pos().x() // self.zoom_level
                y = event.pos().y() // self.zoom_level
                self.paste_position = (x, y)
                self.paste_dragging = True
                self.update()
            elif self.edit_mode == 'select' or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Start selection (in select mode or with Shift key)
                x = event.pos().x() // self.zoom_level
                y = event.pos().y() // self.zoom_level
                self.selecting = True
                self.selection_start = (x, y)
                self.selection_end = (x, y)
                self.selectionChanged.emit(True)
                self.update()
            elif self.edit_mode == 'draw':
                # Normal drawing - save state for undo
                self.save_state("Draw")
                self.drawing = True
                self.draw_pixel(event.pos())
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Continue drawing, selecting, or dragging paste preview."""
        if self.image:
            # Update hover position
            old_hover = self.hover_y
            self.hover_y = event.pos().y() // self.zoom_level
            if old_hover != self.hover_y:
                self.update()
            
            x = event.pos().x() // self.zoom_level
            y = event.pos().y() // self.zoom_level
            
            # Update selection
            if self.selecting:
                self.selection_end = (x, y)
                self.update()
            # Drag paste preview
            elif self.paste_dragging:
                self.paste_position = (x, y)
                self.update()
            # Draw if mouse is pressed
            elif self.drawing:
                self.draw_pixel(event.pos())
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Stop drawing, selecting, or paste dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            was_drawing = self.drawing
            self.drawing = False
            self.selecting = False
            self.paste_dragging = False
            # Emit signal to update UI if we were drawing
            if was_drawing:
                self.update()
    
    def draw_pixel(self, pos):
        """Draw a pixel at the given position."""
        if not self.image:
            return
            
        x = pos.x() // self.zoom_level
        y = pos.y() // self.zoom_level
        
        if 0 <= x < self.image.width() and 0 <= y < self.image.height():
            self.image.setPixel(x, y, self.current_color_index)
            self.update()
            self.pixelChanged.emit(x, y, self.current_color_index)
    
    def set_zoom(self, zoom_level):
        """Set zoom level."""
        self.zoom_level = zoom_level
        self.update_size()
        self.update()
    
    def set_color(self, color_index):
        """Set current drawing color by palette index."""
        self.current_color_index = color_index
    
    def set_char_height(self, height):
        """Set the height of each character in pixels."""
        self.char_height = height
        self.update()
    
    def jump_to_character(self, char_index):
        """Emit signal to scroll to a specific character."""
        if self.image and 0 <= char_index < (self.image.height() // self.char_height):
            self.characterJumped.emit(char_index)
    
    def copy_selection(self):
        """Copy selected region to clipboard."""
        if not self.image or not self.selection_start or not self.selection_end:
            return False
        
        x1 = min(self.selection_start[0], self.selection_end[0])
        y1 = min(self.selection_start[1], self.selection_end[1])
        x2 = max(self.selection_start[0], self.selection_end[0])
        y2 = max(self.selection_start[1], self.selection_end[1])
        
        width = x2 - x1 + 1
        height = y2 - y1 + 1
        
        # Copy pixel data
        self.clipboard_data = []
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                if 0 <= x < self.image.width() and 0 <= y < self.image.height():
                    self.clipboard_data.append(self.image.pixelIndex(x, y))
                else:
                    self.clipboard_data.append(0)
        
        self.clipboard_size = (width, height)
        self.selectionChanged.emit(False)  # Selection will be cleared after copy
        return True
    
    def start_paste_mode(self):
        """Enter paste mode with moveable preview."""
        if not self.clipboard_data or not self.clipboard_size:
            return False
        
        self.paste_mode = True
        # Start paste at top-left of visible area (or 0,0)
        self.paste_position = (0, 0)
        self.update()
        return True
    
    def commit_paste(self):
        """Paste clipboard data at current position."""
        if not self.paste_mode or not self.clipboard_data or not self.paste_position:
            return False
        
        # Save state for undo
        self.save_state("Paste")
        
        px, py = self.paste_position
        cw, ch = self.clipboard_size
        
        # Paste pixels
        for dy in range(ch):
            for dx in range(cw):
                target_x = px + dx
                target_y = py + dy
                if (0 <= target_x < self.image.width() and 
                    0 <= target_y < self.image.height() and
                    dy * cw + dx < len(self.clipboard_data)):
                    color_idx = self.clipboard_data[dy * cw + dx]
                    self.image.setPixel(target_x, target_y, color_idx)
        
        self.paste_mode = False
        self.paste_position = None
        self.update()
        return True
    
    def cancel_paste(self):
        """Cancel paste mode."""
        self.paste_mode = False
        self.paste_position = None
        self.update()
    
    def clear_selection(self):
        """Clear current selection."""
        self.selection_start = None
        self.selection_end = None
        self.selectionChanged.emit(False)
        self.update()
    
    def set_edit_mode(self, mode):
        """Set edit mode to 'draw' or 'select'."""
        if mode in ['draw', 'select']:
            self.edit_mode = mode
            # Clear selection when switching to draw mode
            if mode == 'draw':
                self.clear_selection()
    
    def get_edit_mode(self):
        """Get current edit mode."""
        return self.edit_mode
    
    def save_state(self, description="Action"):
        """Save current image state to undo stack."""
        if not self.image:
            return
        
        # Capture current pixel data
        width = self.image.width()
        height = self.image.height()
        pixel_data = []
        for y in range(height):
            for x in range(width):
                pixel_data.append(self.image.pixelIndex(x, y))
        
        # Add to undo stack
        self.undo_stack.append((pixel_data, description, width, height))
        
        # Limit stack size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        
        # Clear redo stack when new action is performed
        self.redo_stack.clear()
        
        # Notify that history changed
        self.historyChanged.emit()
        
        # Notify that history changed
        self.historyChanged.emit()
    
    def undo(self):
        """Undo last action."""
        if not self.image or not self.undo_stack:
            return False
        
        # Save current state to redo stack
        width = self.image.width()
        height = self.image.height()
        pixel_data = []
        for y in range(height):
            for x in range(width):
                pixel_data.append(self.image.pixelIndex(x, y))
        self.redo_stack.append((pixel_data, "Current", width, height))
        
        # Restore previous state
        pixel_data, description, w, h = self.undo_stack.pop()
        if w == width and h == height:
            idx = 0
            for y in range(height):
                for x in range(width):
                    if idx < len(pixel_data):
                        self.image.setPixel(x, y, pixel_data[idx])
                    idx += 1
            self.update()
            self.historyChanged.emit()
            return True
        return False
    
    def redo(self):
        """Redo last undone action."""
        if not self.image or not self.redo_stack:
            return False
        
        # Save current state to undo stack
        width = self.image.width()
        height = self.image.height()
        pixel_data = []
        for y in range(height):
            for x in range(width):
                pixel_data.append(self.image.pixelIndex(x, y))
        self.undo_stack.append((pixel_data, "Current", width, height))
        
        # Restore next state
        pixel_data, description, w, h = self.redo_stack.pop()
        if w == width and h == height:
            idx = 0
            for y in range(height):
                for x in range(width):
                    if idx < len(pixel_data):
                        self.image.setPixel(x, y, pixel_data[idx])
                    idx += 1
            self.update()
            self.historyChanged.emit()
            return True
        return False
    
    def can_undo(self):
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self):
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def save_image(self, output_path):
        """Save image with original palette preserved."""
        if not self.image or not self.original_palette:
            return False
        
        # Convert QImage back to PIL
        width = self.image.width()
        height = self.image.height()
        
        # Create PIL image with palette
        pil_image = Image.new('P', (width, height))
        pil_image.putpalette(self.original_palette)
        
        # Copy pixel data
        pixels = []
        for y in range(height):
            for x in range(width):
                pixels.append(self.image.pixelIndex(x, y))
        
        pil_image.putdata(pixels)
        pil_image.save(output_path, 'BMP')
        return True


class CharacterThumbnail(QFrame):
    """Thumbnail widget displaying a character with its index number."""
    
    clicked = pyqtSignal(str, int)  # filepath, index
    
    def __init__(self, filepath, index, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.index = index
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Index label
        index_label = QLabel(f"#{index}")
        index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        index_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        
        # Image preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.load_preview()
        
        layout.addWidget(index_label)
        layout.addWidget(self.image_label)
        self.setLayout(layout)
        
    def load_preview(self):
        """Load and display thumbnail preview."""
        try:
            image = QImage(self.filepath)
            if not image.isNull():
                # Scale to reasonable size
                scaled = image.scaled(
                    50, 50,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation
                )
                self.image_label.setPixmap(QPixmap.fromImage(scaled))
        except Exception as e:
            self.image_label.setText("Error")
    
    def mousePressEvent(self, event: QMouseEvent):
        """Emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.filepath, self.index)
        super().mousePressEvent(event)


class MonkeyIslandFontEditor(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.current_index = None
        self.workspace_dir = None
        self.color_buttons = []
        self.color_button_group = None
        
        self.setWindowTitle("Monkey Island Bitmap Font Editor")
        self.setGeometry(100, 100, 1200, 800)
        
        self.setup_ui()
        self.setup_shortcuts()
        self.load_workspace()
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        # Undo: Ctrl+Z
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.undo_action)
        
        # Redo: Ctrl+Y or Ctrl+Shift+Z
        redo_shortcut1 = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut1.activated.connect(self.redo_action)
        
        redo_shortcut2 = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_shortcut2.activated.connect(self.redo_action)
        
        # Copy: Ctrl+C
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy_shortcut.activated.connect(self.copy_selection)
        
        # Paste: Ctrl+V
        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self.paste_selection)
        
        # Save: Ctrl+S
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save_current)
        
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Center panel: Editor canvas
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_panel.setLayout(center_layout)
        
        # Info label
        self.info_label = QLabel("Select a character to edit")
        self.info_label.setStyleSheet("font-size: 14px; padding: 10px;")
        center_layout.addWidget(self.info_label)
        
        # Canvas scroll area
        self.canvas_scroll = QScrollArea()
        self.canvas_scroll.setWidgetResizable(False)
        self.canvas = PixelEditorCanvas()
        self.canvas.characterJumped.connect(self.scroll_to_character)
        self.canvas.historyChanged.connect(self.update_undo_redo_buttons)
        self.canvas.selectionChanged.connect(self.update_selection_buttons)
        self.canvas_scroll.setWidget(self.canvas)
        center_layout.addWidget(self.canvas_scroll)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Zoom controls
        zoom_out_btn = QPushButton("Zoom -")
        zoom_out_btn.clicked.connect(lambda: self.adjust_zoom(-5))
        controls_layout.addWidget(zoom_out_btn)
        
        zoom_in_btn = QPushButton("Zoom +")
        zoom_in_btn.clicked.connect(lambda: self.adjust_zoom(5))
        controls_layout.addWidget(zoom_in_btn)
        
        controls_layout.addStretch()
        
        # Mode selection buttons
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("font-weight: bold;")
        controls_layout.addWidget(mode_label)
        
        self.draw_mode_btn = QPushButton("✏️ Draw")
        self.draw_mode_btn.setToolTip("Switch to draw mode (paint pixels)")
        self.draw_mode_btn.clicked.connect(lambda: self.set_mode('draw'))
        self.draw_mode_btn.setCheckable(True)
        self.draw_mode_btn.setChecked(True)
        self.draw_mode_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 15px;
            }
            QPushButton:checked {
                background-color: #90EE90;
                font-weight: bold;
            }
        """)
        controls_layout.addWidget(self.draw_mode_btn)
        
        self.select_mode_btn = QPushButton("⬚ Select")
        self.select_mode_btn.setToolTip("Switch to select mode (drag to select region)")
        self.select_mode_btn.clicked.connect(lambda: self.set_mode('select'))
        self.select_mode_btn.setCheckable(True)
        self.select_mode_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 15px;
            }
            QPushButton:checked {
                background-color: #87CEEB;
                font-weight: bold;
            }
        """)
        controls_layout.addWidget(self.select_mode_btn)
        
        self.clear_sel_btn = QPushButton("✖ Clear")
        self.clear_sel_btn.setToolTip("Clear current selection")
        self.clear_sel_btn.clicked.connect(self.clear_selection_action)
        self.clear_sel_btn.setStyleSheet("padding: 5px 15px;")
        self.clear_sel_btn.setEnabled(False)  # Disabled by default
        controls_layout.addWidget(self.clear_sel_btn)
        
        controls_layout.addStretch()
        
        # Undo/Redo buttons
        self.undo_btn = QPushButton("⟲ Undo")
        self.undo_btn.setToolTip("Undo last action (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo_action)
        self.undo_btn.setStyleSheet("padding: 5px 15px; font-weight: bold;")
        self.undo_btn.setEnabled(False)
        controls_layout.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("⟳ Redo")
        self.redo_btn.setToolTip("Redo last undone action (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.redo_action)
        self.redo_btn.setStyleSheet("padding: 5px 15px; font-weight: bold;")
        self.redo_btn.setEnabled(False)
        controls_layout.addWidget(self.redo_btn)
        
        controls_layout.addStretch()
        
        # Copy/Paste buttons
        copy_btn = QPushButton("Copy")
        copy_btn.setToolTip("Hold Shift and drag to select, then click Copy")
        copy_btn.clicked.connect(self.copy_selection)
        copy_btn.setStyleSheet("padding: 5px 15px;")
        controls_layout.addWidget(copy_btn)
        
        paste_btn = QPushButton("Paste")
        paste_btn.setToolTip("Paste and drag to position, then click Commit")
        paste_btn.clicked.connect(self.paste_selection)
        paste_btn.setStyleSheet("padding: 5px 15px;")
        controls_layout.addWidget(paste_btn)
        
        self.commit_btn = QPushButton("Commit")
        self.commit_btn.setToolTip("Commit paste at current position")
        self.commit_btn.clicked.connect(self.commit_paste)
        self.commit_btn.setStyleSheet("padding: 5px 15px;")
        self.commit_btn.setEnabled(False)
        controls_layout.addWidget(self.commit_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancel paste operation")
        self.cancel_btn.clicked.connect(self.cancel_paste)
        self.cancel_btn.setStyleSheet("padding: 5px 15px;")
        self.cancel_btn.setEnabled(False)
        controls_layout.addWidget(self.cancel_btn)
        
        controls_layout.addStretch()
        
        # Save button
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_current)
        save_btn.setStyleSheet("font-weight: bold; padding: 5px 20px;")
        controls_layout.addWidget(save_btn)
        
        center_layout.addLayout(controls_layout)
        
        # Right panel: Color palette and ASCII jump table
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        right_panel.setMaximumWidth(280)
        
        # Bitmap file selector buttons
        bitmap_selector_frame = QFrame()
        bitmap_selector_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        bitmap_selector_layout = QVBoxLayout()
        bitmap_selector_layout.setContentsMargins(5, 5, 5, 5)
        bitmap_selector_layout.setSpacing(3)
        
        bitmap_label = QLabel("Select Bitmap File")
        bitmap_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        bitmap_selector_layout.addWidget(bitmap_label)
        
        # Row 1
        bitmap_row1 = QHBoxLayout()
        bitmap_row1.setSpacing(2)
        
        btn_0001 = QPushButton("Sentence Line and Dialog")
        btn_0001.clicked.connect(lambda: self.load_bitmap_file("char0001.bmp", 1))
        btn_0001.setStyleSheet("font-size: 8px; padding: 3px; font-weight: bold;")
        bitmap_row1.addWidget(btn_0001)
        
        # Row 2
        bitmap_row2 = QHBoxLayout()
        bitmap_row2.setSpacing(2)
        
        btn_0002 = QPushButton("On Screen Text")
        btn_0002.clicked.connect(lambda: self.load_bitmap_file("char0002.bmp", 2))
        btn_0002.setStyleSheet("font-size: 8px; padding: 3px; font-weight: bold;")
        bitmap_row2.addWidget(btn_0002)
        
        # Row 3
        bitmap_row3 = QHBoxLayout()
        bitmap_row3.setSpacing(2)

        btn_0003 = QPushButton("Upside Down Text")
        btn_0003.clicked.connect(lambda: self.load_bitmap_file("char0003.bmp", 3))
        btn_0003.setStyleSheet("font-size: 8px; padding: 3px; font-weight: bold;")
        bitmap_row3.addWidget(btn_0003)
        
        # Row 4
        bitmap_row4 = QHBoxLayout()
        bitmap_row4.setSpacing(2)

        btn_0004 = QPushButton("Title Screen/Credits Text")
        btn_0004.clicked.connect(lambda: self.load_bitmap_file("char0004.bmp", 4))
        btn_0004.setStyleSheet("font-size: 8px; padding: 3px; font-weight: bold;")
        bitmap_row4.addWidget(btn_0004)


        # Row 5
        bitmap_row5 = QHBoxLayout()
        bitmap_row5.setSpacing(2)

        btn_0006 = QPushButton("VERB UI")
        btn_0006.clicked.connect(lambda: self.load_bitmap_file("char0006.bmp", 6))
        btn_0006.setStyleSheet("font-size: 8px; padding: 3px; font-weight: bold;")
        bitmap_row5.addWidget(btn_0006)

        bitmap_selector_layout.addLayout(bitmap_row1)
        bitmap_selector_layout.addLayout(bitmap_row2)
        bitmap_selector_layout.addLayout(bitmap_row3)
        bitmap_selector_layout.addLayout(bitmap_row4)
        bitmap_selector_layout.addLayout(bitmap_row5)

        bitmap_selector_frame.setLayout(bitmap_selector_layout)
        right_layout.addWidget(bitmap_selector_frame)
        
        # Color picker
        color_picker_frame = QFrame()
        color_picker_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        color_picker_layout = QVBoxLayout()
        color_picker_layout.setContentsMargins(5, 5, 5, 5)
        
        color_label = QLabel("Color Palette")
        color_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        color_picker_layout.addWidget(color_label)
        
        # Color grid container
        color_container = QWidget()
        color_container.setFixedSize(256, 256)
        self.color_layout = QGridLayout()
        self.color_layout.setSpacing(0)
        self.color_layout.setContentsMargins(0, 0, 0, 0)
        color_container.setLayout(self.color_layout)
        color_picker_layout.addWidget(color_container)
        
        color_picker_frame.setLayout(color_picker_layout)
        right_layout.addWidget(color_picker_frame)
        
        # ASCII character jump table
        ascii_frame = QFrame()
        ascii_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        ascii_layout = QVBoxLayout()
        ascii_layout.setContentsMargins(5, 5, 5, 5)
        
        ascii_label = QLabel("Jump to Character")
        ascii_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        ascii_layout.addWidget(ascii_label)
        
        # Scrollable ASCII table
        ascii_scroll = QScrollArea()
        ascii_scroll.setWidgetResizable(True)
        ascii_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        ascii_container = QWidget()
        self.ascii_layout = QGridLayout()
        self.ascii_layout.setSpacing(2)
        self.ascii_layout.setContentsMargins(2, 2, 2, 2)
        ascii_container.setLayout(self.ascii_layout)
        ascii_scroll.setWidget(ascii_container)
        ascii_layout.addWidget(ascii_scroll)
        
        ascii_frame.setLayout(ascii_layout)
        right_layout.addWidget(ascii_frame)
        
        # Add panels to main layout
        main_layout.addWidget(center_panel, stretch=1)
        main_layout.addWidget(right_panel)
        
    def load_workspace(self):
        """Load all character bitmaps from workspace directory."""
        # Get workspace directory
        self.workspace_dir = Path(__file__).parent
        
        # Auto-load first bitmap if available
        first_bitmap = self.workspace_dir / "char0001.bmp"
        if first_bitmap.exists():
            self.load_bitmap_file("char0001.bmp", 1)
    
    def load_bitmap_file(self, filename, index):
        """Load a specific bitmap file by name."""
        filepath = self.workspace_dir / filename
        if not filepath.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"Bitmap file '{filename}' not found in workspace."
            )
            return
        
        self.load_character(str(filepath), index)
    
    def load_character(self, filepath, index):
        """Load a character for editing."""
        self.current_file = filepath
        self.current_index = index
        
        try:
            self.canvas.load_image(filepath)
            # Calculate number of characters in this bitmap strip
            if self.canvas.image:
                num_chars = self.canvas.image.height() // self.canvas.char_height
                self.info_label.setText(
                    f"Editing: {Path(filepath).name} | "
                    f"Char Height: {self.canvas.char_height}px | "
                    f"Contains {num_chars} characters (ASCII 0-{num_chars-1}) | "
                    f"Hover over canvas to see character indices"
                )
            else:
                self.info_label.setText(f"Editing: Character #{index} - {Path(filepath).name}")
            self.update_color_buttons()
            self.populate_ascii_table()
            self.update_undo_redo_buttons()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load character: {str(e)}"
            )
    
    def update_color_buttons(self):
        """Update color button appearances with actual palette colors."""
        if not self.canvas.image:
            return
        
        # Clear existing buttons
        for btn in self.color_buttons:
            self.color_layout.removeWidget(btn)
            btn.deleteLater()
        self.color_buttons.clear()
        
        # Create button group for exclusive selection
        self.color_button_group = QButtonGroup(self)
        self.color_button_group.setExclusive(True)
        
        # Create button for each palette color (16 per row)
        num_colors = self.canvas.image.colorCount()
        colors_per_row = 16
        
        for i in range(num_colors):
            color = QColor.fromRgb(self.canvas.image.color(i))
            
            btn = QPushButton()
            btn.setFixedSize(16, 16)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgb({color.red()}, {color.green()}, {color.blue()});
                    border: none;
                    margin: 0px;
                    padding: 0px;
                }}
                QPushButton:checked {{
                    border: 2px solid #ffffff;
                }}
                QPushButton:hover {{
                    border: 1px solid #ffff00;
                }}
            """)
            btn.setToolTip(f"Index {i}: RGB({color.red()}, {color.green()}, {color.blue()})")
            btn.clicked.connect(lambda checked, idx=i: self.set_color(idx))
            
            row = i // colors_per_row
            col = i % colors_per_row
            
            self.color_button_group.addButton(btn, i)
            self.color_layout.addWidget(btn, row, col)
            self.color_buttons.append(btn)
        
        # Select first color by default
        if self.color_buttons:
            self.color_buttons[1].setChecked(True)
            self.canvas.set_color(1)
    
    def set_color(self, color_index):
        """Set the current drawing color."""
        self.canvas.set_color(color_index)
    
    def adjust_zoom(self, delta):
        """Adjust zoom level."""
        new_zoom = max(5, min(50, self.canvas.zoom_level + delta))
        self.canvas.set_zoom(new_zoom)
    
    def populate_ascii_table(self):
        """Populate the ASCII character jump table."""
        # Clear existing buttons
        for i in reversed(range(self.ascii_layout.count())):
            self.ascii_layout.itemAt(i).widget().setParent(None)
        
        if not self.canvas.image:
            return
        
        num_chars = self.canvas.image.height() // self.canvas.char_height
        chars_per_row = 8
        
        for i in range(num_chars):
            # Determine character representation
            if 32 <= i < 127:
                char_repr = chr(i)
            else:
                char_repr = f"{i}"
            
            btn = QPushButton(char_repr)
            btn.setFixedSize(28, 28)
            btn.setToolTip(f"Jump to ASCII {i}: '{chr(i) if 0 <= i < 256 else '?'}'")
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 10px;
                    font-family: Fira Code;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self.jump_to_character(idx))
            
            row = i // chars_per_row
            col = i % chars_per_row
            self.ascii_layout.addWidget(btn, row, col)
    
    def jump_to_character(self, char_index):
        """Scroll canvas to show specific character."""
        if not self.canvas.image:
            return
        
        y_pos = char_index * self.canvas.char_height * self.canvas.zoom_level
        self.canvas_scroll.verticalScrollBar().setValue(y_pos)
    
    def scroll_to_character(self, char_index):
        """Handle character jump signal from canvas."""
        self.jump_to_character(char_index)
    
    def set_mode(self, mode):
        """Set edit mode (draw or select)."""
        self.canvas.set_edit_mode(mode)
        
        # Update button states
        if mode == 'draw':
            self.draw_mode_btn.setChecked(True)
            self.select_mode_btn.setChecked(False)
        elif mode == 'select':
            self.draw_mode_btn.setChecked(False)
            self.select_mode_btn.setChecked(True)
    
    def clear_selection_action(self):
        """Clear selection and switch to select mode."""
        self.canvas.clear_selection()
        self.set_mode('select')
    
    def copy_selection(self):
        """Copy selected region."""
        if self.canvas.copy_selection():
            QMessageBox.information(
                self,
                "Copied",
                f"Selection copied to clipboard ({self.canvas.clipboard_size[0]}x{self.canvas.clipboard_size[1]} pixels)"
            )
            self.canvas.clear_selection()
        else:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please hold Shift and drag to select a region first."
            )
    
    def paste_selection(self):
        """Enter paste mode."""
        if self.canvas.start_paste_mode():
            self.commit_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.info_label.setText(
                f"{self.info_label.text()} | PASTE MODE: Drag to position, then click Commit or Cancel"
            )
        else:
            QMessageBox.warning(
                self,
                "No Clipboard",
                "Please copy a selection first."
            )
    
    def commit_paste(self):
        """Commit the paste operation."""
        if self.canvas.commit_paste():
            self.commit_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.update_undo_redo_buttons()
            # Restore info label
            if self.canvas.image:
                num_chars = self.canvas.image.height() // self.canvas.char_height
                self.info_label.setText(
                    f"Editing: {Path(self.current_file).name} | "
                    f"Char Height: {self.canvas.char_height}px | "
                    f"Contains {num_chars} characters (ASCII 0-{num_chars-1}) | "
                    f"Hover over canvas to see character indices"
                )
    
    def cancel_paste(self):
        """Cancel the paste operation."""
        self.canvas.cancel_paste()
        self.commit_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        # Restore info label
        if self.canvas.image:
            num_chars = self.canvas.image.height() // self.canvas.char_height
            self.info_label.setText(
                f"Editing: {Path(self.current_file).name} | "
                f"Char Height: {self.canvas.char_height}px | "
                f"Contains {num_chars} characters (ASCII 0-{num_chars-1}) | "
                f"Hover over canvas to see character indices"
            )
    
    def undo_action(self):
        """Undo the last action."""
        if self.canvas.undo():
            self.update_undo_redo_buttons()
        else:
            if self.canvas.can_undo():
                QMessageBox.information(self, "Undo", "Cannot undo: state mismatch")
    
    def redo_action(self):
        """Redo the last undone action."""
        if self.canvas.redo():
            self.update_undo_redo_buttons()
        else:
            if self.canvas.can_redo():
                QMessageBox.information(self, "Redo", "Cannot redo: state mismatch")
    
    def update_undo_redo_buttons(self):
        """Update undo/redo button states."""
        self.undo_btn.setEnabled(self.canvas.can_undo())
        self.redo_btn.setEnabled(self.canvas.can_redo())
    
    def update_selection_buttons(self, has_selection):
        """Update selection-related button states."""
        self.clear_sel_btn.setEnabled(has_selection)
    
    def save_current(self):
        """Save the currently edited character."""
        if not self.current_file:
            QMessageBox.warning(self, "No File", "No character is currently loaded.")
            return
        
        try:
            if self.canvas.save_image(self.current_file):
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Character #{self.current_index} saved successfully!"
                )
                # Refresh thumbnail
                self.load_workspace()
            else:
                raise Exception("Save failed")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save character: {str(e)}"
            )


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern cross-platform style
    
    window = MonkeyIslandFontEditor()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
