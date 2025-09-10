import opensim
import numpy as np
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    # Loop over time and bodies
    logger.info("Starting time loop for body transforms...")
    visualizeDict = {}
    visualizeDict['time'] = stateTime
    visualizeDict['bodies'] = {}
    
    logger.info(f"Processing {bodyset.getSize()} bodies...")
    for body in bodyset:
        # Note: Patella bodies should have been removed if removePatella=True

        visualizeDict['bodies'][body.getName()] = {}
        attachedGeometries = []
        
        # Ayman said that meshes could get attached to model in different ways than
        # this, so this isn't most general sol'n, but should work for now
        thisFrame = opensim.Frame.safeDownCast(body)
        nGeometries = thisFrame.getPropertyByName('attached_geometry').size()
        
        for iGeom in range(nGeometries):
            attached_geometry = body.get_attached_geometry(iGeom)
            if attached_geometry.getConcreteClassName() == 'Mesh':
                thisMesh = opensim.Mesh.safeDownCast(attached_geometry)
                attachedGeometries.append(thisMesh.getGeometryFilename())
        visualizeDict['bodies'][body.getName()]['attachedGeometries'] = attachedGeometries

        # Only try to get scale factors if there are geometries
        if nGeometries > 0:
            scale_factors = attached_geometry.get_scale_factors().to_numpy() 
            visualizeDict['bodies'][body.getName()]['scaleFactors'] = scale_factors.tolist()
        else:
            visualizeDict['bodies'][body.getName()]['scaleFactors'] = [1.0, 1.0, 1.0]
        
        # init body translation and rotations dictionaries
        visualizeDict['bodies'][body.getName()]['rotation'] = []
        visualizeDict['bodies'][body.getName()]['translation'] = []
    
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
            visualizeDict['bodies'][body.getName()]['rotation'].append(body.getTransformInGround(state).R().convertRotationToBodyFixedXYZ().to_numpy().tolist())
            visualizeDict['bodies'][body.getName()]['translation'].append(body.getTransformInGround(state).T().to_numpy().tolist())
            
    with open(jsonOutputPath, 'w') as f:
        json.dump(visualizeDict, f)

    return   

if __name__ == "__main__":
    # mocap_model_file = 'working/model.osim'
    # mocap_if_file = 'working/motion.mot'
    # output_mocap_json_path = 'working/output.json'

    mocap_model_file = 'bug/model.osim'
    mocap_if_file = 'bug/motion.mot'
    output_mocap_json_path = 'bug/normal_removed_patella.json'
    
    generateVisualizerJson(modelPath=mocap_model_file, ikPath=mocap_if_file, jsonOutputPath=output_mocap_json_path, removePatella=True)