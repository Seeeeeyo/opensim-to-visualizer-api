# OpenSim to Visualizer JSON Converter

This repository provides tools to convert OpenSim motion capture data (model `.osim` and motion `.mot` files) into a JSON format suitable for 3D skeleton visualization in web applications.

## Components

### `utils.py`
- Core conversion logic.
- Reads an OpenSim model and motion file, cleans and maps coordinates, and outputs a JSON file with body segment transforms for each frame.
- Handles edge cases such as coordinate order mismatches and extra columns.

### `app.py`
- FastAPI web server exposing the conversion as a REST API.
- Accepts `.osim` and `.mot` files via POST, returns JSON or downloadable file.
- Handles errors gracefully (e.g., patella/beta mismatch).

## Usage

### Command Line
Edit the bottom of `utils.py` to set your input/output files, then run:

```bash
conda activate opencap-mono  # or your OpenSim Python env
python utils.py
```

### API Server
Start the server:

```bash
conda activate opencap-mono
python app.py
```

Then use the `/docs` endpoint for interactive API usage, or POST to:

```
POST /convert-opensim-to-visualizer-json
```
with form-data fields:
- `osim_file`: OpenSim model file (.osim)
- `mot_file`: Motion file (.mot)
- `download`: (optional) Set to `true` to download the JSON file

Example using `curl`:
```bash
curl -F "osim_file=@model.osim" -F "mot_file=@motion.mot" \
     "http://localhost:8000/convert-opensim-to-visualizer-json?download=true" -o output.json
```

## Requirements
- Python 3.8+
- OpenSim Python API (e.g., via [OpenCap conda env](https://github.com/stanfordnmbl/opencap-environment))
- FastAPI, Uvicorn, NumPy, etc. (see `requirements.txt`)

## Notes
- The output JSON is designed for use with Three.js or similar 3D skeleton visualizers.
- Handles both standard and non-standard `.mot` files robustly.

## License
MIT (or your preferred license) 