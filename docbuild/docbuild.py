from flask import Flask, send_from_directory, request, redirect, url_for, g
from werkzeug import secure_filename
from jinja2 import Template
import tempfile, os, shutil, subprocess
from zipfile import ZipFile

app = Flask(__name__)

# configuration
EMACS_CMD=['emacs', '--batch', '--visit={{file}}', '--funcall', 'org-export-as-pdf']
CONV_DIR='conversion'
LOG_FILE='{{file}}.log'
ZIP_NAME='org.zip'

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
	with ZipFile(os.path.join(loc, zipfile), 'a') as zip:
		for p in gen_tree(dir):
			zip.write(p)
	os.chdir(cwd)

def pdf_name(filename):
	return '.'.join([filename.rsplit('.', 1)[0], 'pdf'])

def package_files(tmpdir, filename):
	logfile = Template(LOG_FILE).render(file=filename)
	pdffile = pdf_name(filename)
	shutil.copy(os.path.join(tmpdir, logfile), os.path.join(tmpdir, CONV_DIR))
	shutil.copy(os.path.join(tmpdir, pdffile), os.path.join(tmpdir, CONV_DIR))
	zip_convdir(tmpdir, CONV_DIR, ZIP_NAME)
	return send_from_directory(tmpdir, ZIP_NAME, as_attachment=True, attachment_filename=ZIP_NAME)

def build_org_file(tmpdir, filename):
	filepath = os.path.join(tmpdir, filename)
	logfile = Template(LOG_FILE).render(file=filepath)
	logpath = os.path.join(tmpdir, logfile)
	cmd = [Template(a).render(file=filepath) for a in EMACS_CMD]
	with open(logpath, 'w') as logf:
		try:
			subprocess.check_call(cmd, stderr=logf)
		except CalledProcessError:
			return abort(400)
		return package_files(tmpdir, filename)	

@app.route('/build/', methods=['GET', 'POST'])
def return_image():
	if request.method == 'POST':
		file = request.files['file1']
		if file:
			filename=secure_filename(file.filename)
			dir = mk_dir()
			path = os.path.join(dir, secure_filename(filename))
			file.save(path)
			return build_org_file(dir, secure_filename(filename))

	return '''
	<!doctype html>
	<html>
	<head>
	<title>Upload File</title>
	</head>
	<body>
	<h1>Upload new file</h1>
	<form action="" method="post" enctype="multipart/form-data">
	<p><input type="file" name="file1"></p>
	<input type="Submit" value="Upload">
	</form>
	</body>
	</html>
'''

@app.route('/display/')
def display_filename():
	return request.args['filename']

if __name__ == "__main__":
    app.debug=True
    app.run()