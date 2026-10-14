"""Additive V6.5 preferences and card organization; original documents stay untouched."""
import copy
import os
import socket


def extend(Base, atomic_json):
    class Store(Base):
        def __init__(self, data):
            super().__init__(data)
            if self.state.get('workspace_version', 0) < 65:
                backup = self.data / 'dashboard.before-v6.5.json'
                if not backup.exists():
                    atomic_json(backup, self.state)
                self.state['workspace_version'] = 65
                self.save()

        def scan(self):
            result = super().scan()
            result['preferences'] = copy.deepcopy(self.state.get('preferences', {}))
            result['server_name'] = self.state.get('preferences', {}).get('server_name') or socket.gethostname()
            result['card_pages'] = copy.deepcopy(self.state.get('card_pages'))
            result['order_revision'] = self.state.get('order_revision', 0)
            return result

        def settings(self, body):
            kind = body.get('kind')
            if kind not in {'preferences', 'reorder'}:
                return super().settings(body)
            with self.lock:
                self.scan()
                snapshot = copy.deepcopy(self.state)
                if kind == 'preferences':
                    values = body.get('values')
                    if not isinstance(values, dict) or set(values) - {'theme', 'server_name', 'card_density'}:
                        raise ValueError('Invalid preferences')
                    if 'theme' in values and values['theme'] not in {'dark', 'light'}:
                        raise ValueError('Choose Dark or Light')
                    if 'server_name' in values and (not isinstance(values['server_name'], str) or len(values['server_name']) > 80):
                        raise ValueError('Server display name must be at most 80 characters')
                    if 'card_density' in values and values['card_density'] not in {'auto', 'single', 'compact'}:
                        raise ValueError('Choose a card density')
                    if 'server_name' in values:
                        values = dict(values, server_name=values['server_name'].strip())
                    snapshot.setdefault('preferences', {}).update(values)
                else:
                    if body.get('revision') != snapshot.get('order_revision', 0):
                        raise ValueError('Project order changed on another device. Reopen Reorder and try again.')
                    order = body.get('order')
                    known = set(snapshot['order'])
                    if not isinstance(order, list) or any(not isinstance(x, str) for x in order) or len(order) != len(known) or set(order) != known:
                        raise ValueError('Projects changed. Reopen Reorder before saving; every project must appear once.')
                    pages = body.get('pages')
                    if pages is not None:
                        if not isinstance(pages, list) or not 1 <= len(pages) <= 200 or any(not isinstance(p, list) or len(p) > 24 or any(not isinstance(x, str) for x in p) for p in pages):
                            raise ValueError('Use 1–200 pages with at most 24 projects per page')
                        flat = [x for p in pages for x in p]
                        if flat != order:
                            raise ValueError('Page contents must match the project order exactly once')
                    snapshot['order'] = order
                    snapshot['card_pages'] = pages
                    snapshot['order_revision'] = snapshot.get('order_revision', 0) + 1
                atomic_json(self.path, snapshot)
                self.state = snapshot

        def update(self, body):
            super().update(body)
            if 'move' in body:
                # Older clients can still move cards, returning to automatic pagination.
                with self.lock:
                    self.state['card_pages'] = None
                    self.state['order_revision'] = self.state.get('order_revision', 0) + 1
                    self.save()

        def restore(self, name):
            revision = self.state.get('order_revision', 0)
            result = super().restore(name)
            self.state['order_revision'] = max(revision, self.state.get('order_revision', 0)) + 1
            self.save()
            return result

        def storage_info(self):
            total = count = skipped = 0
            # Do not follow directory links or junctions outside the projects folder.
            for parent, dirs, files in os.walk(self.projects, followlinks=False):
                from pathlib import Path
                base = Path(parent)
                dirs[:] = [d for d in dirs if not (base / d).is_symlink() and not getattr(base / d, 'is_junction', lambda: False)() and (base / d).resolve().is_relative_to(self.projects)]
                for name in files:
                    p = base / name
                    try:
                        if p.is_symlink() or not p.resolve().is_relative_to(self.projects):
                            continue
                        total += p.stat().st_size
                        count += 1
                    except OSError:
                        skipped += 1
            return {'bytes': total, 'files': count, 'unreadable': skipped}
    return Store
