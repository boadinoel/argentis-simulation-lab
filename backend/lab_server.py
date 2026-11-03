"""One-process threaded server: shared runner ownership and same-origin SPA."""
from pathlib import Path
from flask import abort, send_from_directory
from app import create_app

app = create_app()
dist = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'


@app.route('/')
@app.route('/<path:path>')
def frontend(path=''):
    if path.startswith(('api/', 'health/')):
        abort(404)
    candidate = (dist / path).resolve()
    if not candidate.is_relative_to(dist):
        abort(404)
    return send_from_directory(dist, path if candidate.is_file() else 'index.html')
