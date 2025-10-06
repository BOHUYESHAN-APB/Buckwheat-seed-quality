from pathlib import Path
import sys
sys.path.insert(0, str(Path('.').resolve()))
from app.main import App
app = App()
print('created, cam_entry exists=', hasattr(app, 'cam_entry'))
app.destroy()
