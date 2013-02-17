#!/usr/bin/env python

from tamaraw import app
import sys
if len(sys.argv) > 1 and sys.argv[1].lower() == 'debug':
    print >> sys.stderr, 'starting in debug mode'
    app.run(debug=True)
else:
    app.run(debug=False)
