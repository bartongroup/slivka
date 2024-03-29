import flask

import slivka
from slivka.conf import SlivkaSettings
from slivka.server.forms import FormLoader

try:
    import simplejson as json
except ImportError:
    import json


class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix=''):
        self.app = wsgi_app
        if prefix and not prefix.startswith('/'):
            prefix = '/' + prefix
        self._prefix_parts = prefix.split('/')
        self._prefix_parts[1:] = [p for p in self._prefix_parts[1:] if p]

    def __call__(self, environ, start_response):
        PrefixMiddleware.shift_path_prefix(environ, self._prefix_parts)
        return self.app(environ, start_response)

    @staticmethod
    def shift_path_prefix(environ, prefix_parts):
        path_info: str = environ.get('PATH_INFO', "")
        path_parts = path_info.split('/')
        # remove empty segments preserving leading and trailing slash
        path_parts[1:-1] = [p for p in path_parts[1:-1] if p]
        if (len(path_parts) < len(prefix_parts) or
                any(p1 != p2 for p1, p2 in zip(path_parts, prefix_parts))):
            return
        del path_parts[1:len(prefix_parts)]  # discard prefix leaving leading slash
        script_name = environ.get('SCRIPT_NAME', '')
        environ['SCRIPT_NAME'] = script_name + '/'.join(prefix_parts)
        environ['PATH_INFO'] = '/'.join(path_parts)


def create_app(config: SlivkaSettings = None):
    config = config or slivka.conf.settings
    form_loader = FormLoader()
    for service in config.services:
        form_loader.read_config(service)
    app = flask.Flask('slivka', static_url_path='')
    app.config.update(
        home=config.directory.home,
        jobs_dir=config.directory.jobs,
        uploads_dir=config.directory.uploads,
        services={srv.id: srv for srv in config.services},
        forms=form_loader
    )
    from . import api_views
    app.register_blueprint(api_views.bp, name='api', url_prefix='/api')
    app.register_blueprint(api_views.bp)

    uploads_route = config.server.uploads_path.rstrip('/') + "/<path:file_path>"
    results_route = config.server.jobs_path.rstrip('/') + "/<job_id>/<path:file_path>"
    if app.debug:
        from . import media_views
        uploads_view = media_views.serve_uploads_view
        results_view = media_views.serve_results_view
    else:
        uploads_view = results_view = lambda **kw: flask.abort(404)
    app.add_url_rule(uploads_route, 'media.uploads', uploads_view)
    app.add_url_rule(results_route, 'media.jobs', results_view)

    if config.server.prefix is not None:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, config.server.prefix)
    return app
