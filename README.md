# Monkey Island Bitmap Font Editor

![Monkey Island Font Editor](screenshot.png)

A specialized pixel editor for editing The Secret of Monkey Island bitmap font files. Built with PyQt6 to preserve the original color palette without modification.

I coded it in one afternoon in my spare time to make ease my life on translating The Secrect of Monkey Island to brasilian portuguese. The original game does not have some special lating characters.

Yes, with AI help, never did anything with PyQt6 and wanted to try something else other than XCode/Swift this time.

## Features

### Core Editing
- **Pixel-Level Editing**: Zoom in (5-50x) and edit individual pixels with a grid overlay
- **Palette Preservation**: Maintains the original 256-color indexed palette from the game files
- **Character Index Ruler**: Left-side ruler displaying ASCII codes and Windows-1252 character representations
- **Auto-Height Detection**: Automatically detects character heights (8, 9, 14, or 15 pixels)

### Edit Modes
- **Draw Mode (✏️)**: Click and drag to paint pixels
- **Select Mode (⬚)**: Drag to select regions, or hold Shift in draw mode

### Advanced Features
- **Copy/Paste**: Copy selected regions and paste with moveable preview positioning
- **Undo/Redo**: 50-level history stack with keyboard shortcuts (Ctrl+Z / Ctrl+Y)
- **ASCII Jump Table**: Quick navigation to any character (0-255)
- **Hover Highlighting**: Ruler highlights the character under cursor
- **Multiple Bitmap Files**: Switch between different font sets (Dialog, Screen Text, Title Screen, etc.)

### Color Palette
- **Full 256-Color Grid**: 16×16 color palette display
- **Color Selection**: Click any color to set as drawing color
- **RGB Tooltips**: Hover over colors to see RGB values

## Installation

### Requirements
- Python 3.8 or higher
- PyQt6
- Pillow (PIL)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/monkey-island-font-editor.git
cd monkey-island-font-editor
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install PyQt6 Pillow
```

## Usage

### Running the Editor

With virtual environment activated:
```bash
python monkey_island_font_editor.py
```

Or directly:
```bash
.venv/bin/python monkey_island_font_editor.py  # macOS/Linux
.venv\Scripts\python monkey_island_font_editor.py  # Windows
```

### Editing Workflow

1. **Select Bitmap File**: Choose from the preset buttons (Sentence Line, On Screen Text, etc.)
2. **Navigate Characters**: 
   - Click buttons in the ASCII jump table
   - Hover over the canvas to see character boundaries
   - Characters are labeled with ASCII codes and symbols
3. **Choose Edit Mode**:
   - **Draw Mode**: Paint pixels directly
   - **Select Mode**: Select regions for copying
4. **Select Color**: Click a color in the palette (shows RGB values on hover)
5. **Edit Pixels**: Click and drag to draw
6. **Advanced Operations**:
   - **Copy**: Select region (Shift+drag or use Select mode), click Copy
   - **Paste**: Click Paste, drag preview to position, click Commit
   - **Undo/Redo**: Use buttons or Ctrl+Z / Ctrl+Y
7. **Save**: Click Save or press Ctrl+S

### Keyboard Shortcuts

- `Ctrl+Z` - Undo
- `Ctrl+Y` or `Ctrl+Shift+Z` - Redo
- `Ctrl+C` - Copy selection
- `Ctrl+V` - Paste
- `Ctrl+S` - Save
- `Shift+Drag` - Select region (in Draw mode)

## Technical Details

### File Format
- Reads 8-bit indexed BMP files with 256-color palettes
- Preserves original palette data byte-for-byte
- Supports variable character heights (8, 9, 14, 15 pixels)
- Each bitmap contains 256 characters (extended ASCII)

### Character Encoding
- Windows-1252 encoding for extended ASCII characters (128-255)
- Standard ASCII for printable characters (32-126)
- Character indices displayed on left ruler with hover highlighting

### Bitmap Files
The editor recognizes these preset bitmap files:
- `char0001.bmp` - Sentence Line and Dialog (8px height)
- `char0002.bmp` - On Screen Text (8px height)
- `char0003.bmp` - Upside Down Text (9px height)
- `char0004.bmp` - Title Screen/Credits Text (14px height)
- `char0006.bmp` - VERB UI (8px height)

### Architecture
- **PixelEditorCanvas**: Main canvas widget with zoom, grid, selection, and undo/redo
- **MonkeyIslandFontEditor**: Main window with UI controls and file management
- **Signal/Slot Pattern**: Reactive UI updates via Qt signals (historyChanged, selectionChanged, characterJumped)

## Notes

- **Backups**: Original files are overwritten when saving - keep backups!
- **Undo History**: Limited to 50 levels to manage memory usage
- **Palette**: Color palette is read from the bitmap file and preserved exactly
- **Character Width**: All characters are 10 pixels wide
- **Platform**: Cross-platform (macOS, Linux, Windows)


## How I got the bitmaps for editign?

I used these tools to get the editable bitmap:

[scummrp and scummfont](https://github.com/dwatteau/scummtr)

## The flow (you don't need to do it as these bitmap are already on this repo, but to repack modified versions into the game you will need them. Also, I put them on system PATH to make things easier.

** Be sure to run these tools on same directory of `MONKEY.OOO` AND `MONKEY.001` files.

1. unpack the game files

```bash
scummrp -g monkeycd  -p . -d dump_MI -o
```

2. extract the font bitmaps

```bash
scummfont o ./dump_MI/DISK_0001/LECF/LFLF_0010/CHAR_0001 char0001.bmp 
scummfont o ./dump_MI/DISK_0001/LECF/LFLF_0010/CHAR_0002 char0002.bmp 
scummfont o ./dump_MI/DISK_0001/LECF/LFLF_0010/CHAR_0003 char0003.bmp 
scummfont o ./dump_MI/DISK_0001/LECF/LFLF_0010/CHAR_0004 char0004.bmp 
scummfont o ./dump_MI/DISK_0001/LECF/LFLF_0010/CHAR_0006 char0006.bmp
```


## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is open source. Please check the [LICENSE](LICENSE) file for details.

## Credits

Created for editing bitmap fonts from The Secret of Monkey Island by LucasArts.
