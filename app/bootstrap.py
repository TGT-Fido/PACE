"""First-run content installation, without replacing user projects or preferences."""
import shutil
from pathlib import Path

def prepare_data(data):
    data=Path(data)
    defaults=Path(__file__).resolve().parent.parent/'defaults'
    if not defaults.exists():return
    fresh=not data.exists() or not any(data.iterdir())
    data.mkdir(parents=True,exist_ok=True)
    if fresh:
        shutil.copytree(defaults/'data',data,dirs_exist_ok=True)
    marker=data/'.v7-wallpapers-installed'
    if not marker.exists():
        dest=data/'backgrounds';dest.mkdir(exist_ok=True)
        for source in (defaults/'backgrounds').iterdir():
            target=dest/source.name
            if source.is_file() and not target.exists():shutil.copy2(source,target)
        marker.write_text('7.0.0\n',encoding='utf-8')
