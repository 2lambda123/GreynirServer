#!/usr/bin/env python
"""

    Reynir: Natural language processing for Icelandic

    Web server main module

    Copyright (C) 2019 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module is written in Python 3 and is compatible with PyPy3.

    This is the main module of the Greynir web server. It uses Flask
    as its web server and templating engine. In production, this module is
    typically run inside Gunicorn (using servlets) under nginx or a
    compatible WSGi HTTP(S) server. For development, it can be run
    directly from the command line and accessed through port 5000.

    Flask routes are imported from routes/*

"""

import sys
import os
import time
import re
import logging
from datetime import datetime

from flask import Flask, send_from_directory
from flask_caching import Cache

import reynir
from reynir.bindb import BIN_Db
from reynir.fastparser import Fast_Parser

import reynir_correct

from settings import Settings, ConfigError
from article import Article as ArticleProxy


# RUNNING_AS_SERVER is True if we're executing under nginx/Gunicorn,
# but False if the program was invoked directly as a Python main module.
RUNNING_AS_SERVER = __name__ != "__main__"

# Initialize and configure Flask app
app = Flask(__name__)

app.config["JSON_AS_ASCII"] = False  # We're fine with using Unicode/UTF-8
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB, max upload file size
app.config["CACHE_NO_NULL_WARNING"] = True  # Don't warn if caching is disabled

# Only auto-reload templates if we're not running as a production server
app.config["TEMPLATES_AUTO_RELOAD"] = not RUNNING_AS_SERVER

# Push application context to give view functions, error handlers,
# and other functions access to app instance via current_app
app.app_context().push()

# Set up caching
# Caching is disabled if app is invoked via the command line
cache_type = "simple" if RUNNING_AS_SERVER else "null"
cache = Cache(app, config={"CACHE_TYPE": cache_type})
app.config["CACHE"] = cache

# Register blueprint routes
from routes import routes, max_age
app.register_blueprint(routes)


# Utilities for Flask/Jinja2 formatting of numbers using the Icelandic locale
def make_pattern(rep_dict):
    return re.compile("|".join([re.escape(k) for k in rep_dict.keys()]), re.M)


def multiple_replace(string, rep_dict, pattern=None):
    """ Perform multiple simultaneous replacements within string """
    if pattern is None:
        pattern = make_pattern(rep_dict)
    return pattern.sub(lambda x: rep_dict[x.group(0)], string)


_REP_DICT_IS = {",": ".", ".": ","}
_PATTERN_IS = make_pattern(_REP_DICT_IS)


@app.template_filter("format_is")
def format_is(r, decimals=0):
    """ Flask/Jinja2 template filter to format a number for the Icelandic locale """
    fmt = "{0:,." + str(decimals) + "f}"
    return multiple_replace(fmt.format(float(r)), _REP_DICT_IS, _PATTERN_IS)


@app.template_filter("format_ts")
def format_ts(ts):
    """ Flask/Jinja2 template filter to format a timestamp """
    return str(ts)[0:19]


# Flask cache busting for static .css and .js files
@app.url_defaults
def hashed_url_for_static_file(endpoint, values):
    """ Add a ?h=XXX parameter to URLs for static .js and .css files,
        where XXX is calculated from the file timestamp """

    def static_file_hash(filename):
        """ Obtain a timestamp for the given file """
        return int(os.stat(filename).st_mtime)

    if "static" == endpoint or endpoint.endswith(".static"):
        filename = values.get("filename")
        if filename and (filename.endswith(".js") or filename.endswith(".css")):
            # if "." in endpoint:  # has higher priority
            #     blueprint = endpoint.rsplit(".", 1)[0]
            # else:
            #     blueprint = request.blueprint  # can be None too

            # if blueprint:
            #     static_folder = app.blueprints[blueprint].static_folder
            # else:
            static_folder = app.static_folder

            param_name = "h"
            while param_name in values:
                param_name = "_" + param_name
            values[param_name] = static_file_hash(os.path.join(static_folder, filename))


@app.route("/static/fonts/<path:path>")
@max_age(seconds=24 * 60 * 60)  # Cache font for 24 hours
def send_font(path):
    return send_from_directory("static/fonts", path)


# Custom 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    """ Return a custom 404 error """
    return "Þessi vefslóð er ekki rétt", 404


# Custom 500 error handler
@app.errorhandler(500)
def server_error(e):
    """ Return a custom 500 error """
    return "Eftirfarandi villa kom upp: {0}".format(e), 500


# Initialize the main module
t0 = time.time()
try:
    # Read configuration file
    Settings.read(os.path.join("config", "Reynir.conf"))
except ConfigError as e:
    logging.error("Greynir did not start due to a configuration error:\n{0}".format(e))
    sys.exit(1)

if Settings.DEBUG:
    print(
        "\nStarting Greynir web app at {5} with debug={0}, host={1}:{2}, db_hostname={3}\n"
        "Python {4}".format(
            Settings.DEBUG,
            Settings.HOST,
            Settings.PORT,
            Settings.DB_HOSTNAME,
            sys.version,
            datetime.utcnow(),
        )
    )
    # Clobber Settings.DEBUG in ReynirPackage and ReynirCorrect
    reynir.Settings.DEBUG = True
    reynir_correct.Settings.DEBUG = True


if not RUNNING_AS_SERVER:

    if os.environ.get("GREYNIR_ATTACH_PTVSD"):
        # Attach to the VSCode PTVSD debugger, enabling remote debugging via SSH
        import ptvsd
        ptvsd.enable_attach()
        ptvsd.wait_for_attach()  # Blocks execution until debugger is attached
        ptvsd_attached = True
        print("Attached to PTVSD")
    else:
        ptvsd_attached = False

    # Run a default Flask web server for testing if invoked directly as a main program

    # Additional files that should cause a reload of the web server application
    # Note: Reynir.grammar is automatically reloaded if its timestamp changes
    extra_files = [
        "Reynir.conf",
        "ReynirPackage.conf",
        "Index.conf",
        "Verbs.conf",
        "Adjectives.conf",
        "AdjectivePredicates.conf",
        "Morphemes.conf",
        "Prepositions.conf",
        "Prefs.conf",
        "Phrases.conf",
        "Vocab.conf",
        "Names.conf",
        "ReynirCorrect.conf",
    ]

    dirs = list(
        map(os.path.dirname, [__file__, reynir.__file__, reynir_correct.__file__])
    )
    for i, fname in enumerate(extra_files):
        # Look for the extra file in the different package directories
        for directory in dirs:
            path = os.path.join(directory, "config", fname)
            path = os.path.realpath(path)
            if os.path.isfile(path):
                extra_files[i] = path
                break
        else:
            print("Extra file '{0}' not found".format(fname))
    # Add src/reynir/resources/ord.compressed from reynir
    extra_files.append(
        os.path.join(
            os.path.dirname(reynir.__file__),
            "src",
            "reynir",
            "resources",
            "ord.compressed",
        )
    )

    from socket import error as socket_error
    import errno

    try:

        # Suppress information log messages from Werkzeug
        werkzeug_log = logging.getLogger("werkzeug")
        if werkzeug_log:
            werkzeug_log.setLevel(logging.WARNING)
        # Run the Flask web server application
        app.run(
            host=Settings.HOST,
            port=Settings.PORT,
            debug=Settings.DEBUG,
            use_reloader=not ptvsd_attached,
            extra_files=extra_files,
        )

    except socket_error as e:
        if e.errno == errno.EADDRINUSE:  # Address already in use
            logging.error(
                "Reynir is already running at host {0}:{1}".format(
                    Settings.HOST, Settings.PORT
                )
            )
            sys.exit(1)
        else:
            raise

    finally:
        ArticleProxy.cleanup()
        BIN_Db.cleanup()

else:

    # Suppress information log messages from Werkzeug
    werkzeug_log = logging.getLogger("werkzeug")
    if werkzeug_log:
        werkzeug_log.setLevel(logging.WARNING)

    # Log our startup
    log_str = "Reynir instance starting with host={0}:{1}, db_hostname={2} on Python {3}".format(
        Settings.HOST,
        Settings.PORT,
        Settings.DB_HOSTNAME,
        sys.version.replace("\n", " "),
    )
    logging.info(log_str)
    print(log_str)
    sys.stdout.flush()

    # Running as a server module: pre-load the grammar into memory
    with Fast_Parser() as fp:
        pass
