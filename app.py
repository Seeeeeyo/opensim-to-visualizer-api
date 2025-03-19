import io
import json
import tempfile
import os
import logging
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import utils
from fastapi.middleware.cors import CORSMiddleware

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenSim to Visualizer JSON Converter")

# Add this after creating the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your website domain for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConversionResponse(BaseModel):
    message: str
    filename: str

@app.post("/convert-opensim-to-visualizer-json",
          responses={
              200: {
                  "content": {
                      "application/json": {},
                      "application/octet-stream": {}
                  },
                  "description": "Returns either JSON data or a downloadable file"
              }
          })
async def convert_opensim_to_visualizer_json(
    osim_file: UploadFile = File(..., description="OpenSim model file (.osim)"),
    mot_file: UploadFile = File(..., description="IK motion file (.mot)"),
    download: bool = Query(False, description="Set to true to download the response as a file")
):
    """
    Convert OpenSim model and motion files to visualizer JSON format.
    
    - **osim_file**: OpenSim model file (.osim)
    - **mot_file**: Motion file (.mot)
    - **download**: If true, returns a downloadable file instead of JSON response
    
    Returns either JSON data directly or a downloadable JSON file based on the download parameter.
    """
    # Validate file extensions
    if not osim_file.filename.endswith('.osim'):
        raise HTTPException(status_code=400, detail="Model file must have .osim extension")
    
    if not mot_file.filename.endswith('.mot'):
        raise HTTPException(status_code=400, detail="Motion file must have .mot extension")
    
    # Create temporary directory that we'll clean up at the end
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create paths for our files
        osim_temp_path = os.path.join(temp_dir, "model.osim")
        mot_temp_path = os.path.join(temp_dir, "motion.mot")
        json_temp_path = os.path.join(temp_dir, "output.json")
        
        # Write uploaded content to temp files
        with open(osim_temp_path, 'wb') as f:
            f.write(await osim_file.read())
        
        with open(mot_temp_path, 'wb') as f:
            f.write(await mot_file.read())
        
        # Generate the visualizer JSON
        utils.generateVisualizerJson(
            modelPath=osim_temp_path,
            ikPath=mot_temp_path,
            jsonOutputPath=json_temp_path
        )
        
        # Handle response based on download parameter
        if download:
            # For download, we need to create a response with the file
            # We need to make sure the file still exists when the response is processed
            filename = f"visualizer_{os.path.basename(osim_file.filename).replace('.osim', '')}.json"
            
            # For download, create a copy in a persistent location and serve that
            # This ensures the file exists when FastAPI reads it
            output_file = os.path.join(tempfile.gettempdir(), filename)
            shutil.copy2(json_temp_path, output_file)
            
            # Now we can safely clean up our temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Return the persistent file for download
            return FileResponse(
                path=output_file,
                filename=filename,
                media_type="application/json",
                background=BackgroundTask(lambda: os.unlink(output_file) if os.path.exists(output_file) else None)
            )
        else:
            # For JSON response, read the file contents
            with open(json_temp_path, 'r') as f:
                result = json.load(f)
            
            # Clean up the temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Return the JSON content
            return JSONResponse(content=result)
    
    except Exception as e:
        # Clean up on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        logger.exception("Error processing files")
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")


@app.get("/", tags=["Info"])
async def root():
    """Returns information about the API"""
    return {
        "message": "OpenSim to Visualizer JSON Converter API",
        "docs": "/docs",
        "endpoints": [
            {
                "path": "/convert-opensim-to-visualizer-json",
                "method": "POST",
                "description": "Convert OpenSim model and motion files to visualizer JSON"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 