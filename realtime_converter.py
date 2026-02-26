"""
Real-time frame-by-frame OpenSim converter.

NOT for deployment — local use only.

Usage example:
    converter = RealtimeConverter("model.osim")

    # Option A: feed a dict of {coord_name: value} per frame
    frame_json = converter.convert_frame({"pelvis_tilt": 0.1, "elbow_flex_r": 0.5, ...}, time=0.0)

    # Option B: feed raw lines from a .mot file
    with open("motion.mot") as f:
        headers, data_lines = RealtimeConverter.split_mot_file(f.read())
    for line in data_lines:
        time, coord_values = RealtimeConverter.parse_mot_line(line, headers)
        frame_json = converter.convert_frame(coord_values, time)

    # Static body info (geometries, scale factors) is available separately
    body_info = converter.get_body_info()
"""

import json
import logging

import numpy as np
import opensim

from utils import getOffsetFrameMeshesFromXML, removePatellaFromModelXML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealtimeConverter:
    """
    Converts a single motion frame (coordinate values + time) into a
    visualizer-compatible JSON dict.

    Heavy initialisation (model loading, system init, static geometry
    extraction) happens once in __init__.  convert_frame() is then cheap.
    """

    def __init__(
        self,
        model_path: str,
        states_in_degrees: bool = True,
        vertical_offset: float | None = None,
        remove_patella: bool = True,
    ):
        """
        Args:
            model_path:         Path to the .osim model file.
            states_in_degrees:  If True, rotational coordinate values fed to
                                convert_frame() are assumed to be in degrees
                                and will be converted to radians internally.
            vertical_offset:    Optional vertical offset subtracted from
                                pelvis_ty (same as generateVisualizerJson).
            remove_patella:     Remove patella components from model XML
                                before loading (modifies file in-place,
                                creates a .backup).
        """
        opensim.Logger.setLevelString("error")

        self.states_in_degrees = states_in_degrees
        self.vertical_offset = vertical_offset

        if remove_patella:
            logger.info("Applying XML-based patella removal…")
            model_path = removePatellaFromModelXML(model_path)

        logger.info(f"Loading model: {model_path}")
        self.model = opensim.Model(model_path)

        # --- coordinate metadata ---
        coords = self.model.getCoordinateSet()
        self._n_coords = coords.getSize()
        self._coord_names = [coords.get(i).getName() for i in range(self._n_coords)]
        # motion type per coordinate (1 = rotation)
        self._coord_motion_type = {
            coords.get(i).getName(): coords.get(i).getMotionType()
            for i in range(self._n_coords)
        }

        # --- initialise system state ---
        logger.info("Initialising system…")
        self._state = self.model.initSystem()

        # Map every model coordinate to its position in the system Y vector
        y_names = opensim.createStateVariableNamesInSystemOrder(self.model)
        self._coord_to_sys_idx: dict[str, int] = {}
        for coord_name in self._coord_names:
            matches = [i for i, y in enumerate(y_names) if coord_name + "/value" in y]
            if matches:
                self._coord_to_sys_idx[coord_name] = matches[0]
        logger.info(f"Mapped {len(self._coord_to_sys_idx)} coordinates to system indices")

        # --- static body geometry info ---
        self._bodyset = self.model.getBodySet()
        offset_meshes = getOffsetFrameMeshesFromXML(model_path)
        self._body_info: dict[str, dict] = {}
        for body in self._bodyset:
            body_name = body.getName()
            geoms = []
            first_geom = None

            # direct attached_geometry on the body frame
            n = opensim.Frame.safeDownCast(body).getPropertyByName("attached_geometry").size()
            for i in range(n):
                ag = body.get_attached_geometry(i)
                if ag.getConcreteClassName() == "Mesh":
                    mesh = opensim.Mesh.safeDownCast(ag)
                    geoms.append(mesh.getGeometryFilename())
                    if first_geom is None:
                        first_geom = ag

            # meshes from PhysicalOffsetFrame children (e.g. ribcage on thorax)
            for extra in offset_meshes.get(body_name, []):
                if extra not in geoms:
                    geoms.append(extra)

            scale_factors = [1.0, 1.0, 1.0]
            if first_geom is not None:
                try:
                    scale_factors = first_geom.get_scale_factors().to_numpy().tolist()
                except Exception:
                    pass

            self._body_info[body_name] = {
                "attachedGeometries": geoms,
                "scaleFactors": scale_factors,
            }

        logger.info(
            f"RealtimeConverter ready — {self._bodyset.getSize()} bodies, "
            f"{len(self._coord_to_sys_idx)} coordinates"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_body_info(self) -> dict:
        """
        Return the static per-body metadata (attachedGeometries, scaleFactors).
        This only needs to be sent once to the visualizer.

        Returns:
            {body_name: {"attachedGeometries": [...], "scaleFactors": [...]}}
        """
        return {k: dict(v) for k, v in self._body_info.items()}

    def convert_frame(self, coord_values: dict[str, float], time: float) -> dict:
        """
        Convert one frame of motion data to a visualizer JSON dict.

        Args:
            coord_values:  {coordinate_name: value}.  Missing coordinates
                           default to 0.  Values for rotational coordinates
                           are expected in degrees if states_in_degrees=True.
            time:          Time stamp for this frame (seconds).

        Returns:
            {
                "time": float,
                "bodies": {
                    body_name: {
                        "attachedGeometries": [...],
                        "scaleFactors":       [...],
                        "rotation":           [rx, ry, rz],
                        "translation":        [tx, ty, tz],
                    }
                }
            }
        """
        y_vec = np.zeros(self._state.getNY()).tolist()

        for coord_name, value in coord_values.items():
            sys_idx = self._coord_to_sys_idx.get(coord_name)
            if sys_idx is None:
                continue
            # degrees → radians for rotational DOFs
            if self._coord_motion_type.get(coord_name) == 1 and self.states_in_degrees:
                value = np.deg2rad(value)
            # optional vertical offset on pelvis
            if coord_name == "pelvis_ty" and self.vertical_offset is not None:
                value -= self.vertical_offset - 0.01
            y_vec[sys_idx] = value

        self._state.setY(opensim.Vector(y_vec))
        self.model.realizePosition(self._state)

        bodies_out: dict[str, dict] = {}
        for body in self._bodyset:
            body_name = body.getName()
            try:
                rotation = (
                    body.getTransformInGround(self._state)
                    .R()
                    .convertRotationToBodyFixedXYZ()
                    .to_numpy()
                    .tolist()
                )
                translation = (
                    body.getTransformInGround(self._state)
                    .T()
                    .to_numpy()
                    .tolist()
                )
            except Exception as e:
                logger.error(f"Transform error for body {body_name} at t={time}: {e}")
                rotation = [0.0, 0.0, 0.0]
                translation = [0.0, 0.0, 0.0]

            bodies_out[body_name] = {
                **self._body_info[body_name],
                "rotation": rotation,
                "translation": translation,
            }

        return {"time": time, "bodies": bodies_out}

    # ------------------------------------------------------------------
    # .mot parsing helpers (static — no model needed)
    # ------------------------------------------------------------------

    @staticmethod
    def split_mot_file(mot_text: str) -> tuple[list[str], list[str]]:
        """
        Split raw .mot file text into column headers and data lines.

        Returns:
            (headers, data_lines)
            headers:    list of column names, first entry is 'time'
            data_lines: list of raw data line strings (one per frame)
        """
        lines = mot_text.splitlines()
        # find the 'endheader' marker
        header_end = next(
            (i for i, l in enumerate(lines) if l.strip().lower() == "endheader"), None
        )
        if header_end is None:
            raise ValueError("Could not find 'endheader' in .mot file")

        col_header_line = lines[header_end + 1].strip()
        headers = col_header_line.split()
        data_lines = [l for l in lines[header_end + 2:] if l.strip()]
        return headers, data_lines

    @staticmethod
    def parse_mot_line(line: str, headers: list[str]) -> tuple[float, dict[str, float]]:
        """
        Parse one data line from a .mot file.

        Args:
            line:    Raw whitespace-separated data line.
            headers: Column headers returned by split_mot_file().

        Returns:
            (time, {coord_name: value})
            The 'time' column is separated out; all remaining columns are
            returned in the dict.
        """
        values = list(map(float, line.split()))
        if len(values) != len(headers):
            raise ValueError(
                f"Expected {len(headers)} values, got {len(values)}"
            )
        mapping = dict(zip(headers, values))
        time = mapping.pop("time")
        return time, mapping


# ---------------------------------------------------------------------------
# Quick smoke-test (mirrors the batch test in utils.py __main__)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os

    MODEL_PATH = "sam/model.osim"
    MOT_PATH = "sam/L.mot"
    OUTPUT_PATH = "sam/sam_realtime.json"

    if not os.path.exists(MODEL_PATH) or not os.path.exists(MOT_PATH):
        print("sam/model.osim or sam/motion.mot not found — skipping smoke test")
    else:
        converter = RealtimeConverter(MODEL_PATH)

        with open(MOT_PATH) as f:
            mot_text = f.read()

        headers, data_lines = RealtimeConverter.split_mot_file(mot_text)
        print(f"Motion file: {len(data_lines)} frames, columns: {headers}")

        frames = []
        for line in data_lines:
            t, coords = RealtimeConverter.parse_mot_line(line, headers)
            frame = converter.convert_frame(coords, t)
            frames.append(frame)

        # Assemble into the same format as generateVisualizerJson for easy comparison
        result = {
            "time": [f["time"] for f in frames],
            "bodies": {
                body_name: {
                    **converter.get_body_info()[body_name],
                    "rotation":    [f["bodies"][body_name]["rotation"]    for f in frames],
                    "translation": [f["bodies"][body_name]["translation"] for f in frames],
                }
                for body_name in frames[0]["bodies"]
            },
        }

        with open(OUTPUT_PATH, "w") as f:
            json.dump(result, f)

        print(f"Written {len(frames)} frames to {OUTPUT_PATH}")
        print(f"Bodies: {list(result['bodies'].keys())}")
        for body, info in converter.get_body_info().items():
            if info["attachedGeometries"]:
                print(f"  {body}: {info['attachedGeometries']}")
