import opensim
import numpy as np
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# %% This takes model and IK and generates a json of body transforms that can 
# be passed to the webapp visualizer
def generateVisualizerJson(modelPath,ikPath,jsonOutputPath,statesInDegrees=True,
                           vertical_offset=None):
    
    opensim.Logger.setLevelString('error')
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
        if 'patella' in body.getName() and not beta_present:
            logger.info(f"Processing body: {body.getName()}")
            # raise an error to stop the program
            raise ValueError("The patella is present in the model, but beta is not present in the motion file. Please upload a model with no patella or a motion file with beta.")

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
            if not beta_present and 'patella' in body.getName():
                continue
            visualizeDict['bodies'][body.getName()]['rotation'].append(body.getTransformInGround(state).R().convertRotationToBodyFixedXYZ().to_numpy().tolist())
            visualizeDict['bodies'][body.getName()]['translation'].append(body.getTransformInGround(state).T().to_numpy().tolist())
            
    with open(jsonOutputPath, 'w') as f:
        json.dump(visualizeDict, f)

    return   

if __name__ == "__main__":
    # mocap_model_file = 'working/model.osim'
    # mocap_if_file = 'working/motion.mot'
    # output_mocap_json_path = 'working/output.json'

    mocap_model_file = 'dynamics/LaiUhlrich2022_scaled_no_patella.osim'
    mocap_if_file = 'dynamics/working.mot'
    output_mocap_json_path = 'dynamics/normal.json'
    
    generateVisualizerJson(modelPath=mocap_model_file, ikPath=mocap_if_file, jsonOutputPath=output_mocap_json_path)