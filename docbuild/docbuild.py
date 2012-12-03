#!/user/bin/python

from flask import Flask, send_file, request, abort
from werkzeug import secure_filename
import tempfile, os, shutil, subprocess, StringIO
from zipfile import ZipFile
from datetime import datetime, timedelta

app = Flask(__name__)

# User configuration -- edit these to match your setup.
SVC_PORT = 5000
BIND_ADDR = '127.0.0.1'
FORM_URL = '/'
BUILD_URL = '/build/'

# Service configuration -- edit these if you need to.
EMACS_CMD = ['emacs', '--batch',
	'--visit={file}',
	'--funcall',
	'org-export-as-pdf']
CONV_DIR = 'conversion'
LOG_FILE = '{file}.log'
ZIP_NAME = 'org.zip'

# Service code -- Nothing to see here, move along.

TEMP_DIRS = []
ONGOING_BUILDS = []


def mk_dir():
	tmpdir = tempfile.mkdtemp()
	path = os.path.join(tmpdir, CONV_DIR)
	os.mkdir(path)
	return tmpdir


def gen_tree(dir):
	for path, dirs, files in os.walk(dir):
		for f in files:
			yield os.path.join(path, f)
		for d in dirs:
			yield os.path.join(path, d)


def zip_convdir(loc, dir, zipfile):
	"Make a zipfile of the files in <loc>/<dir>/ called zipfile (contains directory <dir>)"
	cwd = os.getcwd()
	os.chdir(loc)
	sio = StringIO.StringIO()
	with ZipFile(sio, 'a') as z:
		for p in gen_tree(dir):
			z.write(p)
	os.chdir(cwd)
	sio.seek(0)
	return sio


def pdf_name(filename):
	return '.'.join([filename.rsplit('.', 1)[0], 'pdf'])


def package_files(tmpdir, filename):
	logfile = LOG_FILE.format(file=filename)
	pdffile = pdf_name(filename)
	shutil.copy(os.path.join(tmpdir, logfile), os.path.join(tmpdir, CONV_DIR))
	shutil.copy(os.path.join(tmpdir, pdffile), os.path.join(tmpdir, CONV_DIR))
	zf = zip_convdir(tmpdir, CONV_DIR, ZIP_NAME)
	ONGOING_BUILDS.remove(tmpdir)


	return send_file(zf, mimetype='application/zip',
		as_attachment=True, attachment_filename=ZIP_NAME)


def build_org_file(tmpdir, filename):
	# Lock the temp directory during build (will be unlocked by package_files())
	ONGOING_BUILDS.append(tmpdir)
	filepath = os.path.join(tmpdir, filename)
	logfile = LOG_FILE.format(file=filepath)
	logpath = os.path.join(tmpdir, logfile)
	cmd = [a.format(file=filepath) for a in EMACS_CMD]
	with open(logpath, 'w') as logf:
		try:
			subprocess.check_call(cmd, stderr=logf)
		except subprocess.CalledProcessError:
			return abort(500)
	return package_files(tmpdir, filename)


def fresh(item):
	if datetime.now()-item[0] < timedelta(minutes=5) or item[1] in ONGOING_BUILDS:
		return True
	return False


def clean_dirs():
	global TEMP_DIRS
	staledirs = [d for d in TEMP_DIRS if not fresh(d)]
	freshdirs = [d for d in TEMP_DIRS if fresh(d)]
	for d in staledirs:
		shutil.rmtree(os.path.realpath(d[1]))
	TEMP_DIRS = freshdirs


@app.route(FORM_URL, methods=['GET'])
def return_image():
	# Clean up any expired temp dirs
	clean_dirs()

	return '''
	<!doctype html>
	<html>
	<head>
	<title>Upload File</title>
	</head>
	<body>
	<h1>Upload new file</h1>
	<form action="{}" method="post" enctype="multipart/form-data">
	<p><input type="file" name="org_file"></p>
	<input type="Submit" value="Upload">
	</form>
	</body>
	</html>
'''.format(BUILD_URL)

@app.route(BUILD_URL, methods=['POST'])
def return_zip():
	orgfile = request.files['org_file']
	if not orgfile:
		return abort(400)

	filename=secure_filename(orgfile.filename)
	builddir = mk_dir()
	TEMP_DIRS.append((datetime.now(), builddir))
	path = os.path.join(builddir, secure_filename(filename))
	orgfile.save(path)
	return build_org_file(builddir, secure_filename(filename))


if __name__ == "__main__":
    app.debug=True
    app.run()