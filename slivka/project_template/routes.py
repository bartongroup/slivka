import flask

blueprint = flask.Blueprint(
    'index', __name__, url_prefix='/',
    template_folder='templates',
    static_folder='static'
)


@blueprint.route('/')
def index():
    return flask.render_template('index.html')
