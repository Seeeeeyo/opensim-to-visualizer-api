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
              },
              400: {
                  "description": "Invalid file format or patella-related error",
                  "content": {
                      "application/json": {
                          "example": {
                              "detail": "The patella is present in the model, but beta is not present in the motion file. Please upload a model with no patella or a motion file with beta."
                          }
                      }
                  }
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
        logger.info(f"Starting JSON generation for model: {osim_file.filename}, motion: {mot_file.filename}")
        utils.generateVisualizerJson(
            modelPath=osim_temp_path,
            ikPath=mot_temp_path,
            jsonOutputPath=json_temp_path
        )

        # Validate that the JSON file was created and is valid
        if not os.path.exists(json_temp_path):
            logger.error("JSON output file was not created")
            raise HTTPException(status_code=500, detail="Failed to generate visualizer JSON")

        # Read and validate the JSON content
        try:
            with open(json_temp_path, 'r') as f:
                result = json.load(f)

            # Basic validation of the result structure
            if not isinstance(result, dict) or 'time' not in result or 'bodies' not in result:
                logger.error("Generated JSON has invalid structure")
                raise HTTPException(status_code=500, detail="Generated JSON has invalid structure")

            logger.info(f"Successfully generated JSON with {len(result.get('bodies', {}))} bodies and {len(result.get('time', []))} time points")

        except json.JSONDecodeError as e:
            logger.error(f"Generated JSON is not valid JSON: {e}")
            raise HTTPException(status_code=500, detail="Generated JSON is not valid")
        except Exception as e:
            logger.error(f"Error reading generated JSON: {e}")
            raise HTTPException(status_code=500, detail="Error reading generated JSON")

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
            # Clean up the temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

            # Return the JSON content
            return JSONResponse(content=result)
    
    except ValueError as e:
        # Clean up on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Check if this is the patella-related error
        if "patella" in str(e) and "beta" in str(e):
            logger.warning("Patella-related error: %s", str(e))
            raise HTTPException(status_code=400, detail=str(e))
        
        logger.exception("Value error processing files")
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")
        
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