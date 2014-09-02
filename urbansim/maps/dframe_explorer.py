from bottle import route, response, run, hook, static_file
from urbansim.utils import yamlio
import simplejson
import numpy as np
import pandas as pd
import os
import json
import webbrowser
from jinja2 import Environment


@hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = \
        'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

DFRAMES = {}
CONFIG = None


def get_schema():
    global DFRAMES
    return {name: list(DFRAMES[name].columns) for name in DFRAMES}


@route('/map_query/<table>/<filter>/<groupby>/<field:path>/<agg>', method="GET")
def map_query(table, filter, groupby, field, agg):
    global DFRAMES

    filter = ".query('%s')" % filter if filter != "empty" else ""

    df = DFRAMES[table]

    if field not in df.columns:
        print "Col not found, trying eval:", field
        df["eval"] = df.eval(field)
        field = "eval"

    cmd = "df%s.groupby('%s')['%s'].%s" % \
          (filter, groupby, field, agg)
    print cmd
    results = eval(cmd)
    results[results == np.inf] = np.nan
    results = yamlio.series_to_yaml_safe(results.dropna())
    results = {int(k): results[k] for k in results}
    return results


@route('/map_query/<table>/<filter>/<groupby>/<field>/<agg>', method="OPTIONS")
def ans_options(table=None, filter=None, groupby=None, field=None, agg=None):
    return {}


@route('/')
def index():
    global CONFIG
    dir = os.path.dirname(__file__)
    index = open(os.path.join(dir, 'dframe_explorer.html')).read()
    return Environment().from_string(index).render(CONFIG)


@route('/data/<filename>')
def data_static(filename):
    if filename == "internal":
        return SHAPES
    return static_file(filename, root='./data')


def start(views,
          center=[37.7792, -122.2191],
          zoom=11,
          shape_json='data/zones.json',
          geom_name='ZONE_ID',  # from JSON file
          join_name='zone_id',  # from data frames
          precision=8,
          port=8765,
          host='localhost',
          testing=False):
    """
    Start the web service which serves the Pandas queries and generates the
    HTML for the map.  You will need to open a web browser and navigate to
    http://localhost:8765 (or the specified port)

    Parameters
    ----------
    views : Python dictionary
        This is the data that will be displayed in the maps.  Keys are strings
        (table names) and values are dataframes.  Each data frame should have a
        column with the name specified as join_name below
    center : a Python list with two floats
        The initial latitude and longitude of the center of the map
    zoom : int
        The initial zoom level of the map
    shape_json : str
        Can either be the geojson itself or the path to a file which contains
        the geojson that describes the shapes to display (uses os.path.exists
        to check for a file on the filesystem)
    geom_name : str
        The field name from the JSON file which contains the id of the
        geometry - if it's None, use the id of the geojson feature
    join_name : str
        The column name from the dataframes passed as views (must be in each
        view) which joins to geom_name in the shapes
    precision : int
        The precision of values to show in the legend on the map
    port : int
        The port for the web service to respond on
    host : str
        The hostname to run the web service from
    testing : bool
        Whether to print extra debug information

    Returns
    -------
    Does not return - takes over control of the thread and responds to
    queries from a web browser
    """

    global DFRAMES, CONFIG, SHAPES
    DFRAMES = {str(k): views[k] for k in views}

    print shape_json
    if not testing and not os.path.exists(shape_json):
        # if the file doesn't exist, we try to use it as json
        try:
            json.loads(shape_json)
        except:
            assert 0, "The json passed in appears to be neither a parsable " \
                      "json format nor a file that exists on the file system"
        SHAPES = shape_json
        shape_json = "data/internal"

    config = {
        'center': str(center),
        'zoom': zoom,
        'shape_json': shape_json,
        'geom_name': geom_name,
        'join_name': join_name,
        'precision': precision
    }

    for k in views:
        if join_name not in views[k].columns:
            raise Exception("Join name must be present on all dataframes - "
                            "'%s' not present on '%s'" % (join_name, k))

    config['schema'] = simplejson.dumps(get_schema())

    CONFIG = config

    if testing:
        return

    # open in a new tab, if possible
    webbrowser.open("http://%s:%s" % (host, port), new=2)

    run(host=host, port=port, debug=True)