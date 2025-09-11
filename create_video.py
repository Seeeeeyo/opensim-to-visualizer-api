import os
from utils import generateVisualizerJson
import opencap_visualizer as ocv

def normalize_path(path):
    """Normalize path to use the correct path separator for the operating system"""
    return os.path.normpath(path)


mot_path = normalize_path(r"/home/selim/opensim_to_viz_api/dynamics/working.mot")
model_path = normalize_path(r"/home/selim/opensim_to_viz_api/dynamics/LaiUhlrich2022_scaled_no_patella.osim")
json_path = normalize_path(r"/home/selim/opensim_to_viz_api/dynamics/output.json")
output_path = normalize_path(r"/home/selim/opensim_to_viz_api/sim.mp4")

# generateVisualizerJson(model_path, mot_path, json_path)
# print("Visualizer JSON generated successfully!")
files = [model_path, mot_path]


success = ocv.create_video(files, output_path, verbose=True)
if success:
    print("Video generated successfully!")