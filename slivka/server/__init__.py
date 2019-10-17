import flask
import slivka


def create_app():
    app = flask.Flask('slivka')
    app.config.update(
        UPLOADS_DIR=slivka.settings.UPLOADS_DIR
    )
    from . import serverapp
    app.register_blueprint(serverapp.bp)
    return app

