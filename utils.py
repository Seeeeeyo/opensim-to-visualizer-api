import opensim
import numpy as np
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validateVisualizerJson(visualizeDict):
    """
    Validate the structure of the visualizer JSON to ensure it's complete and valid.

    Args:
        visualizeDict: The dictionary containing the visualizer data

    Raises:
        ValueError: If the JSON structure is invalid
    """
    # Check top-level structure
    if not isinstance(visualizeDict, dict):
        raise ValueError("visualizeDict must be a dictionary")

    required_keys = ['time', 'bodies']
    for key in required_keys:
        if key not in visualizeDict:
            raise ValueError(f"Missing required key: {key}")

    # Validate time array
    time_data = visualizeDict['time']
    if not isinstance(time_data, list):
        raise ValueError("time must be a list")
    if len(time_data) == 0:
        raise ValueError("time array cannot be empty")

    # Validate bodies structure
    bodies_data = visualizeDict['bodies']
    if not isinstance(bodies_data, dict):
        raise ValueError("bodies must be a dictionary")

    if len(bodies_data) == 0:
        raise ValueError("bodies dictionary cannot be empty")

    # Validate each body
    for body_name, body_data in bodies_data.items():
        if not isinstance(body_data, dict):
            raise ValueError(f"Body {body_name} data must be a dictionary")

        required_body_keys = ['attachedGeometries', 'scaleFactors', 'rotation', 'translation']
        for key in required_body_keys:
            if key not in body_data:
                raise ValueError(f"Body {body_name} missing required key: {key}")

        # Validate attachedGeometries
        attached_geoms = body_data['attachedGeometries']
        if not isinstance(attached_geoms, list):
            raise ValueError(f"Body {body_name} attachedGeometries must be a list")

        # Validate scaleFactors
        scale_factors = body_data['scaleFactors']
        if not isinstance(scale_factors, list) or len(scale_factors) != 3:
            raise ValueError(f"Body {body_name} scaleFactors must be a list of 3 numbers")

        # Validate rotation
        rotation = body_data['rotation']
        if not isinstance(rotation, list):
            raise ValueError(f"Body {body_name} rotation must be a list")
        if len(rotation) != len(time_data):
            raise ValueError(f"Body {body_name} rotation length ({len(rotation)}) must match time length ({len(time_data)})")

        for i, rot in enumerate(rotation):
            if not isinstance(rot, list) or len(rot) != 3:
                raise ValueError(f"Body {body_name} rotation[{i}] must be a list of 3 numbers")

        # Validate translation
        translation = body_data['translation']
        if not isinstance(translation, list):
            raise ValueError(f"Body {body_name} translation must be a list")
        if len(translation) != len(time_data):
            raise ValueError(f"Body {body_name} translation length ({len(translation)}) must match time length ({len(time_data)})")

        for i, trans in enumerate(translation):
            if not isinstance(trans, list) or len(trans) != 3:
                raise ValueError(f"Body {body_name} translation[{i}] must be a list of 3 numbers")

    logger.info(f"JSON validation passed for {len(bodies_data)} bodies and {len(time_data)} time points")


def removePatellaFromModelXML(modelPath):
    """
    Remove patella-related components from an OpenSim model by modifying the XML file directly.
    This approach is more reliable than trying to modify the loaded model.

    Removes:
    - Patella bodies (patella_r, patella_l)
    - Patellofemoral joints
    - Patellofemoral constraints
    - Muscles that attach to patella: recfem_r/l, vasint_r/l, vaslat_r/l, vasmed_r/l
    - Any PathPoint references to patella bodies

    Args:
        modelPath: Path to OpenSim model file (.osim)

    Returns:
        Modified model path (same as input, file is modified in-place)
    """
    logger.info(f"Starting XML-based patella removal for: {modelPath}")

    # Read the model file
    with open(modelPath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_length = len(content)
    logger.info(f"Original file size: {original_length} characters")

    # Create backup
    backup_path = modelPath + '.backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    logger.info(f"Created backup: {backup_path}")

    # Remove patella bodies
    import re

    # Pattern to match entire Body elements for patella
    patella_body_pattern = r'<Body name="patella_[rl]">.*?</Body>'
    content = re.sub(patella_body_pattern, '', content, flags=re.DOTALL)
    logger.info("Removed patella body elements from XML")

    # Remove patellofemoral joints
    patella_joint_pattern = r'<CustomJoint name="patellofemoral_[rl]">.*?</CustomJoint>'
    content = re.sub(patella_joint_pattern, '', content, flags=re.DOTALL)
    logger.info("Removed patellofemoral joint elements from XML")

    # Remove patellofemoral constraints
    patella_constraint_pattern = r'<CoordinateCouplerConstraint name="patellofemoral_.*?</CoordinateCouplerConstraint>'
    content = re.sub(patella_constraint_pattern, '', content, flags=re.DOTALL)
    logger.info("Removed patellofemoral constraint elements from XML")

    # Remove patella muscles
    patella_muscles = ['recfem_r', 'vasint_r', 'vaslat_r', 'vasmed_r', 'recfem_l', 'vasint_l', 'vaslat_l', 'vasmed_l']
    for muscle in patella_muscles:
        muscle_pattern = f'<Millard2012EquilibriumMuscle name="{muscle}">.*?</Millard2012EquilibriumMuscle>'
        content = re.sub(muscle_pattern, '', content, flags=re.DOTALL)
        logger.info(f"Removed muscle {muscle} from XML")

    # Remove any remaining PathPoint references to patella
    patella_pathpoint_pattern = r'<PathPoint[^>]*>.*?<socket_parent_frame>/bodyset/patella_[rl]</socket_parent_frame>.*?</PathPoint>'
    content = re.sub(patella_pathpoint_pattern, '', content, flags=re.DOTALL)
    logger.info("Removed PathPoint elements referencing patella from XML")

    # Also remove any socket_parent references to patella in PhysicalOffsetFrame
    patella_socket_pattern = r'<socket_parent>/bodyset/patella_[rl]</socket_parent>'
    content = re.sub(patella_socket_pattern, '', content)
    logger.info("Removed socket_parent references to patella from XML")

    # Write back the modified content
    with open(modelPath, 'w', encoding='utf-8') as f:
        f.write(content)

    new_length = len(content)
    reduction = original_length - new_length
    logger.info(f"Modified file size: {new_length} characters (reduced by {reduction} characters)")
    logger.info("XML-based patella removal completed")

    return modelPath


# Note: The old model-based patella removal function has been replaced
# with the more reliable XML-based approach (removePatellaFromModelXML)


# %% This takes model and IK and generates a json of body transforms that can
# be passed to the webapp visualizer
def getOffsetFrameMeshesFromXML(modelPath):
    """
    Parse the model XML to build a mapping of body_name -> [mesh_filenames]
    that includes meshes attached via PhysicalOffsetFrame child components.
    These are missed by the standard OpenSim API body.get_attached_geometry().

    Returns:
        dict: {body_name: [mesh_filename, ...]}
    """
    import xml.etree.ElementTree as ET
    result = {}
    try:
        tree = ET.parse(modelPath)
        root = tree.getroot()
        for body_el in root.iter('Body'):
            body_name = body_el.get('name')
            if not body_name:
                continue
            meshes = []
            components = body_el.find('components')
            if components is not None:
                for offset_frame in components.iter('PhysicalOffsetFrame'):
                    for mesh_el in offset_frame.iter('Mesh'):
                        mesh_file_el = mesh_el.find('mesh_file')
                        if mesh_file_el is not None and mesh_file_el.text:
                            meshes.append(mesh_file_el.text.strip())
            if meshes:
                result[body_name] = meshes
    except Exception as e:
        logger.warning(f"Could not parse offset frame meshes from XML: {e}")
    return result


def generateVisualizerJson(modelPath, ikPath, jsonOutputPath, statesInDegrees=True,
                           vertical_offset=None, removePatella=True):
    """
    Generate JSON visualization data from OpenSim model and motion files.

    Args:
        modelPath: Path to OpenSim model file (.osim)
        ikPath: Path to motion file (.mot)
        jsonOutputPath: Path for output JSON file
        statesInDegrees: Whether motion data is in degrees (default: True)
        vertical_offset: Vertical offset to apply to pelvis (optional)
        removePatella: Whether to remove patella components from model (default: True)

    Returns:
        None (writes JSON file to jsonOutputPath)
    """


    # Patella removal functionality has been implemented above.
    # The model will have patella components removed if removePatella=True


    opensim.Logger.setLevelString('error')

    # Remove patella components from XML if requested
    if removePatella:
        logger.info("Using XML-based patella removal approach")
        modelPath = removePatellaFromModelXML(modelPath)

    # Now load the cleaned model
    model = opensim.Model(modelPath)

    bodyset = model.getBodySet()
    
    coords = model.getCoordinateSet()
    nCoords = coords.getSize()
    coordNames = [coords.get(i).getName() for i in range(nCoords)]
    
    # load IK
    stateTable = opensim.TimeSeriesTable(ikPath)
    stateNames = stateTable.getColumnLabels()
    stateTime = stateTable.getIndependentColumn()
    # Convert to Python list to ensure it's serializable
    if hasattr(stateTime, 'to_numpy'):
        stateTime = stateTime.to_numpy().tolist()
    elif hasattr(stateTime, '__iter__') and not isinstance(stateTime, (str, bytes)):
        stateTime = list(stateTime)
    try:
        inDegrees = stateTable.getTableMetaDataAsString('inDegrees') == 'yes'
    except:
        inDegrees = statesInDegrees
        print('using statesInDegrees variable, which says statesInDegrees is ' + str(statesInDegrees))
    q = np.zeros((len(stateTime),nCoords))
    
    stateNamesOut= []
    columns_to_remove = []
    
    # First identify columns to remove
    logger.info(f"Initial stateNames from MOT file: {stateNames}")
    for col in stateNames:
        if 'activation' in col:
            logger.info(f"Identifying for removal (activation criteria): {col}")
            columns_to_remove.append(col)
        elif col[0] == '/' and any(['jointset' not in col, 'value' not in col]): # full state path
            logger.info(f"Identifying for removal (full path criteria): {col}")
            columns_to_remove.append(col)
        else:
            logger.info(f"Column kept (at identification stage): {col}")
    
    # Remove identified columns
    logger.info(f"Columns identified for removal: {columns_to_remove}")
    for col in columns_to_remove:
        logger.info(f"Attempting to remove column: {col}")
        try:
            stateTable.removeColumn(col)
            logger.info(f"Successfully removed column: {col}")
        except Exception as e:
            logger.error(f"Failed to remove column {col}: {str(e)}") # Log if removal fails
    
    # Get updated column labels after removal
    stateNames = stateTable.getColumnLabels()
    logger.info(f"stateNames after removal process: {stateNames}")
    
    for motColIndex, col in enumerate(stateNames):
        logger.info(f"Processing column: {col} at MOT file index {motColIndex}")
        try:
            # Try to find matching coordinate
            matching_coords = [i for i,c in enumerate(coordNames) if c in col]
            
            if not matching_coords:
                logger.warning(f"No matching coordinate found for {col}")
                continue
                
            modelCoordIndex = matching_coords[0]  # Index in the model's coordinate list
            coordName = col
            logger.info(f"Found matching coordinate: {coordName} at model index {modelCoordIndex}")
            
            if col[0] == '/': # if full state path
                temp = col[:col.rfind('/')]
                coordName = temp[temp.rfind('/')+1:]
                logger.info(f"Extracted coordinate name from path: {coordName}")
                
            logger.info(f"Processing data for coordinate: {coordName}")
            for t in range(len(stateTime)):
                qTemp = np.asarray(stateTable.getDependentColumn(col)[t])
                if coords.get(coordName).getMotionType() == 1 and inDegrees: # rotation
                    qTemp = np.deg2rad(qTemp)
                if 'pelvis_ty' in col and not (vertical_offset is None):
                    qTemp -= (vertical_offset - 0.01)
                q[t,modelCoordIndex] = qTemp  # Use model coordinate index for q array
            stateNamesOut.append(coordName) # This is always just coord - never full path
            logger.info(f"Successfully processed coordinate: {coordName}")
        except Exception as e:
            logger.error(f"Error processing column {col}: {str(e)}")
            continue

    # Only proceed if we have states to process
    if not stateNamesOut:
        logger.error("No valid states found in the motion file that match the model coordinates")
        raise ValueError("No valid states found in the motion file that match the model coordinates")
    
    logger.info(f"Successfully processed {len(stateNamesOut)} coordinates: {stateNamesOut}")
    
    # We may have deleted some columns
    stateNames = stateNamesOut
    
    # Create a mapping from coordinate name to model coordinate index
    coordNameToModelIndex = {}
    for coordName in stateNames:
        matching_coords = [i for i,c in enumerate(coordNames) if c == coordName]
        if matching_coords:
            coordNameToModelIndex[coordName] = matching_coords[0]
    
    logger.info(f"Coordinate name to model index mapping: {coordNameToModelIndex}")

    # check if there is a name containing 'beta' in the stateNames values.
    beta_present = False
    for stateName in stateNames:
        if 'beta' in stateName:
            beta_present = True
            break
    
    if beta_present:
        logger.info("Beta is present in the motion file")
    else:
        logger.info("Beta is NOT present in the motion file")
                          
    logger.info("Initializing system state...")
    state = model.initSystem()
    
    # Create state Y map
    logger.info("Creating state variable names in system order...")
    yNames = opensim.createStateVariableNamesInSystemOrder(model)
    systemStateInds = []
    
    logger.info("Mapping state names to system indices...")
    for stateName in stateNames:
        matching_states = [i for i, y in enumerate(yNames) if stateName + '/value' in y]
        if matching_states:
            systemStateInds.append(matching_states[0])
            logger.info(f"Mapped {stateName} to system index {matching_states[0]}")
        else:
            logger.warning(f"No matching system state found for {stateName}")

    logger.info(f"Found {len(systemStateInds)} system state mappings")
    
    # Build a mapping of offset-frame meshes from the XML (API doesn't expose these directly)
    offsetFrameMeshes = getOffsetFrameMeshesFromXML(modelPath)
    logger.info(f"Offset frame meshes from XML: {offsetFrameMeshes}")

    # Loop over time and bodies
    logger.info("Starting time loop for body transforms...")
    visualizeDict = {}
    visualizeDict['time'] = stateTime
    visualizeDict['bodies'] = {}
    
    logger.info(f"Processing {bodyset.getSize()} bodies...")
    for body in bodyset:
        # Note: Patella bodies should have been removed if removePatella=True

        body_name = body.getName()
        visualizeDict['bodies'][body_name] = {}
        attachedGeometries = []
        
        # Geometries directly attached to the body frame
        thisFrame = opensim.Frame.safeDownCast(body)
        nGeometries = thisFrame.getPropertyByName('attached_geometry').size()

        # Keep track of the first valid geometry for scale factors
        first_valid_geometry = None

        for iGeom in range(nGeometries):
            attached_geometry = body.get_attached_geometry(iGeom)
            if attached_geometry.getConcreteClassName() == 'Mesh':
                thisMesh = opensim.Mesh.safeDownCast(attached_geometry)
                geom_filename = thisMesh.getGeometryFilename()
                attachedGeometries.append(geom_filename)
                if first_valid_geometry is None:
                    first_valid_geometry = attached_geometry

        # Add any meshes from PhysicalOffsetFrame child components (e.g. ribcage on thorax)
        for extra_mesh in offsetFrameMeshes.get(body_name, []):
            if extra_mesh not in attachedGeometries:
                attachedGeometries.append(extra_mesh)
                logger.info(f"Added offset-frame mesh '{extra_mesh}' to body '{body_name}'")

        visualizeDict['bodies'][body_name]['attachedGeometries'] = attachedGeometries

        # Only try to get scale factors if we found at least one valid geometry
        if first_valid_geometry is not None:
            try:
                scale_factors = first_valid_geometry.get_scale_factors().to_numpy()
                visualizeDict['bodies'][body_name]['scaleFactors'] = scale_factors.tolist()
            except Exception as e:
                logger.warning(f"Could not get scale factors for body {body_name}: {e}")
                visualizeDict['bodies'][body_name]['scaleFactors'] = [1.0, 1.0, 1.0]
        else:
            visualizeDict['bodies'][body_name]['scaleFactors'] = [1.0, 1.0, 1.0]
        
        # init body translation and rotations dictionaries
        visualizeDict['bodies'][body_name]['rotation'] = []
        visualizeDict['bodies'][body_name]['translation'] = []
    
    for iTime, time in enumerate(stateTime): 
        yVec = np.zeros((state.getNY())).tolist()
        for i, idx in enumerate(systemStateInds):
            coordName = stateNames[i]  # Get coordinate name by position in stateNames
            modelCoordIdx = coordNameToModelIndex[coordName]  # Get model coordinate index
            if modelCoordIdx < q.shape[1]:  # Check bounds using model coordinate index
                yVec[idx] = q[iTime, modelCoordIdx]  # Use model coordinate index to access q
        state.setY(opensim.Vector(yVec))
        
        model.realizePosition(state)
        
        # get body translations and rotations in ground
        for body in bodyset:
            # This gives us body transform to opensim body frame, which isn't nec.
            # geometry origin. Ayman said getting transform to Geometry::Mesh is safest
            # but we don't have access to it thru API and Ayman said what we're doing
            # is OK for now
            # Note: Patella bodies should have been removed if removePatella=True
            try:
                rotation_matrix = body.getTransformInGround(state).R().convertRotationToBodyFixedXYZ().to_numpy().tolist()
                translation_vector = body.getTransformInGround(state).T().to_numpy().tolist()

                # Validate that we got valid arrays
                if isinstance(rotation_matrix, list) and len(rotation_matrix) == 3:
                    visualizeDict['bodies'][body.getName()]['rotation'].append(rotation_matrix)
                else:
                    logger.warning(f"Invalid rotation matrix for body {body.getName()} at time {time}")
                    visualizeDict['bodies'][body.getName()]['rotation'].append([0.0, 0.0, 0.0])

                if isinstance(translation_vector, list) and len(translation_vector) == 3:
                    visualizeDict['bodies'][body.getName()]['translation'].append(translation_vector)
                else:
                    logger.warning(f"Invalid translation vector for body {body.getName()} at time {time}")
                    visualizeDict['bodies'][body.getName()]['translation'].append([0.0, 0.0, 0.0])

            except Exception as e:
                logger.error(f"Error getting transform for body {body.getName()} at time {time}: {e}")
                visualizeDict['bodies'][body.getName()]['rotation'].append([0.0, 0.0, 0.0])
                visualizeDict['bodies'][body.getName()]['translation'].append([0.0, 0.0, 0.0])

    # Validate the complete structure before writing
    try:
        validateVisualizerJson(visualizeDict)
        with open(jsonOutputPath, 'w') as f:
            json.dump(visualizeDict, f)
        logger.info(f"Successfully wrote visualizer JSON to {jsonOutputPath}")
    except Exception as e:
        logger.error(f"Error validating or writing JSON: {e}")
        raise

    return   

def testValidateVisualizerJson():
    """Test the JSON validation function with various inputs."""
    # Test valid structure
    valid_data = {
        'time': [0.0, 0.1, 0.2],
        'bodies': {
            'pelvis': {
                'attachedGeometries': ['pelvis.vtp'],
                'scaleFactors': [1.0, 1.0, 1.0],
                'rotation': [[0.0, 0.0, 0.0], [0.1, 0.1, 0.1], [0.2, 0.2, 0.2]],
                'translation': [[0.0, 0.0, 0.0], [0.1, 0.1, 0.1], [0.2, 0.2, 0.2]]
            }
        }
    }

    try:
        validateVisualizerJson(valid_data)
        print("✓ Valid JSON structure passed validation")
    except Exception as e:
        print(f"✗ Valid JSON structure failed validation: {e}")

    # Test invalid structures
    invalid_cases = [
        ("Missing time key", {'bodies': {}}),
        ("Time not a list", {'time': 'not_a_list', 'bodies': {}}),
        ("Empty time array", {'time': [], 'bodies': {'body': {'attachedGeometries': [], 'scaleFactors': [1,1,1], 'rotation': [], 'translation': []}}}),
        ("Body missing required key", {'time': [0.0], 'bodies': {'body': {'attachedGeometries': [], 'scaleFactors': [1,1,1]}}}),
        ("Invalid rotation length", {'time': [0.0, 0.1], 'bodies': {'body': {'attachedGeometries': [], 'scaleFactors': [1,1,1], 'rotation': [[0,0,0]], 'translation': [[0,0,0], [0,0,0]]}}}),
    ]

    for test_name, invalid_data in invalid_cases:
        try:
            validateVisualizerJson(invalid_data)
            print(f"✗ {test_name} should have failed but passed")
        except ValueError:
            print(f"✓ {test_name} correctly failed validation")
        except Exception as e:
            print(f"? {test_name} failed with unexpected error: {e}")


if __name__ == "__main__":
    # Run validation tests
    print("Running JSON validation tests...")
    testValidateVisualizerJson()
    print()

    # Original test code
    mocap_model_file = 'sam/model.osim'
    mocap_if_file = 'sam/L.mot'
    output_mocap_json_path = 'sam/sam.json'

    generateVisualizerJson(modelPath=mocap_model_file, ikPath=mocap_if_file, jsonOutputPath=output_mocap_json_path, removePatella=True)