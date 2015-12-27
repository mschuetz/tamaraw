combine:
	mkdir -p src/tamaraw/static/jscss
	rm -f src/tamaraw/static/jscss/all.css
	cat src/tamaraw/static/vendor/bootstrap3/css/bootstrap.min.css >> src/tamaraw/static/jscss/all.css
	echo >> src/tamaraw/static/jscss/all.css
	cat src/tamaraw/static/vendor/bootstrap3/css/bootstrap-theme.min.css >> src/tamaraw/static/jscss/all.css
	echo >> src/tamaraw/static/jscss/all.css
	cat src/tamaraw/static/tamaraw.css >> src/tamaraw/static/jscss/all.css
	rm -f src/tamaraw/static/jscss/all.js
	cat src/tamaraw/static/vendor/jquery-1.11.1.min.js >> src/tamaraw/static/jscss/all.js
	echo >> src/tamaraw/static/jscss/all.js
	cat src/tamaraw/static/vendor/underscore-min.js >> src/tamaraw/static/jscss/all.js
	echo >> src/tamaraw/static/jscss/all.js
	cat src/tamaraw/static/vendor/bootstrap3/js/bootstrap.min.js >> src/tamaraw/static/jscss/all.js
	mkdir -p src/tamaraw/static/fonts
	cp src/tamaraw/static/vendor/bootstrap3/fonts/glyphicons-halflings-regular.woff src/tamaraw/static/fonts
