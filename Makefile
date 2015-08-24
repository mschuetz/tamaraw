combine:
	rm -f src/tamaraw/static/all.css
	cat src/tamaraw/static/vendor/bootstrap3/css/bootstrap.min.css >> src/tamaraw/static/all.css
	echo >> src/tamaraw/static/all.css
	cat src/tamaraw/static/vendor/bootstrap3/css/bootstrap-theme.min.css >> src/tamaraw/static/all.css
	echo >> src/tamaraw/static/all.css
	cat src/tamaraw/static/tamaraw.css >> src/tamaraw/static/all.css
	rm -f src/tamaraw/static/all.js
	cat src/tamaraw/static/vendor/jquery-1.11.1.min.js >> src/tamaraw/static/all.js
	echo >> src/tamaraw/static/all.js
	cat src/tamaraw/static/vendor/underscore-min.js >> src/tamaraw/static/all.js
	echo >> src/tamaraw/static/all.js
	cat src/tamaraw/static/vendor/bootstrap3/js/bootstrap.min.js >> src/tamaraw/static/all.js
	echo >> src/tamaraw/static/all.js
	cat src/tamaraw/static/tamaraw.js >> src/tamaraw/static/all.js
