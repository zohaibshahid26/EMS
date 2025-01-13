@echo "Installing dependencies..."
"C:\Users\computer point\AppData\Local\Programs\Python\Python37\python.exe" -m pip install -r requirements.txt

@echo "Setting PYTHONPATH..."
set PYTHONPATH=%cd%\src

@echo "Build complete!"


