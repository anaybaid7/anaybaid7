# Local preview: make, then open README.md in VS Code's markdown preview
all:
	python3 tools/build.py
	python3 tools/live.py
	python3 tools/readme.py
