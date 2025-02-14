import adsk.core
import adsk.fusion
#import adsk.cam
import traceback
import sys
import math
import os
import json
import inspect
import re
#from multiprocessing.connection import Client
from array import array
import time

import importlib
import functools


from ... import config
from ...lib import fusion360utils as futil
from .shared import ToolCollection

from . import shared, transient_objects, document_data, cad_modeling


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))


print(f"RELOADED: {__name__.split("%2F")[-1]}")

# send info to html palette
PALETTE_ID = config.palette_id
app = adsk.core.Application.get()
ui = app.userInterface
palette = ui.palettes.itemById(PALETTE_ID)

ent_dict = {}

class FusionInterface:
    """
    interface between Fusion360 api and OpenAI Assistant
    methonds in this class are made avilable to the OpenAI Assistants API
    via the GptClient class
    """

    def __init__(self, app, ui):
        self.app = app
        self.ui = ui
        self.design = adsk.fusion.Design.cast(self.app.activeProduct)

        ent_dict["design"] = self.design
        ent_dict["root"] = self.design.rootComponent

        # method collections
        self.submodules = [
            document_data.GetStateData(ent_dict),
            document_data.SetStateData(ent_dict),
            cad_modeling.CreateObjects(ent_dict),
            transient_objects.TransientObjects(ent_dict),
            cad_modeling.ModifyObjects(ent_dict),
            ImportExport(ent_dict),
            Joints(ent_dict),
        ]

        fusion_methods = {}
        for submod in self.submodules:
            for method_name, method in submod.methods.items():
                # add method from container classes to main interface class
                setattr(self, method_name, method)


    # TODO do this without hard coading modules name
    def _reload_modules(self):
        importlib.reload(shared)
        importlib.reload(transient_objects)
        importlib.reload(document_data)
        importlib.reload(cad_modeling)

    def update_settings(self, settings_dict ):
        ToolCollection.update(settings_dict)

    def get_tools(self):
        """
        creates list fusion interface functions
        """
        methods = {}

        # add modules and create methods
        for mod in self.submodules:
            class_name = mod.__class__.__name__

            # class name used for display
            methods[class_name] = {}

            for attr_name in dir(mod):

                attr = getattr(mod, attr_name)
                wrapper = getattr(attr, "__wrapper__", None )
                if wrapper != "tool_call":
                    continue

                if str(attr.__class__) == "<class 'method'>":
                    # method signature
                    sig = inspect.signature(attr)

                    attr = inspect.unwrap(attr)

                    default_vals = inspect.getfullargspec(attr).defaults

                    if default_vals != None:
                        n_default_vals = len(default_vals)
                    else:
                        n_default_vals = 0

                    param_dict = {}
                    for index, param_name in enumerate(sig.parameters):
                        annotation = sig.parameters.get(param_name).annotation

                        if index < n_default_vals:
                            default_val = default_vals[index]
                        else:
                            default_val = None

                        param_info_dict = {
                            "type": str(annotation),
                            "default_val": default_val
                        }

                        #param_info_dict
                        param_dict[param_name] = param_info_dict

                    methods[class_name][attr_name] = param_dict

        return methods



    def get_docstr(self):
        """
        creates list fusion interface functions
        """
        method_list = []
        for attr_name in dir(self):

            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":
                sig = inspect.signature(attr)

                wrapper = getattr(attr, "__wrapper__", None )

                if wrapper != "tool_call":
                    continue

                docstring = attr.__doc__

                print(attr_name)
                json_method = json.loads(docstring)

                method_list.append(json_method)


        method_list = json.dumps(method_list)
        self.tools_json = method_list
        return method_list



class ImportExport(ToolCollection):

    @ToolCollection.tool_call
    def list_step_files_in_directory(self) -> str:
        """
        {
          "name": "list_step_files_in_directory",
          "description": "Recursively navigates a given directory and returns an organized JSON-like object containing the names and full file paths of all STEP files. STEP files are identified by the '.step' or '.stp' extension. The returned structure organizes the files by directory, listing files and nested subdirectories. The root directory path is hard coded by the user",
          "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "returns": {
              "type": "object",
              "description": "An organized JSON-like object with keys 'files' and 'subdirectories'. 'files' is a list of objects each containing 'name' and 'path' for STEP files in the current directory, while 'subdirectories' is a dictionary mapping each subdirectory name to its own similar object."
            }
          }
        }
        """

        try:

            def recursive_scan(current_path):
                # Initialize the result for the current directory
                result = {"files": [], "subdirectories": {}}
                with os.scandir(current_path) as it:
                    for entry in it:
                        if entry.is_file():
                            # Check if file extension is .step or .stp (case-insensitive)
                            if entry.name.lower().endswith(('.step', '.stp')):
                                result["files"].append({
                                    "name": entry.name,
                                    "path": os.path.abspath(entry.path)
                                })
                        elif entry.is_dir():
                            # Recursively scan subdirectories
                            result["subdirectories"][entry.name] = recursive_scan(entry.path)
                return result

            directory_path = config.LOCAL_CAD_PATH

            organized_result = recursive_scan(directory_path)

            return json.dumps(organized_result)

        except Exception as e:
            return f"Error: Failed to scan local directory: {e}"

    @ToolCollection.tool_call
    def import_step_file_to_component(self, target_component: str="comp1", file_path: str="paath"):
        """
        {
          "name": "import_step_file_to_component",
          "description": "Imports a STEP file into a specified target component in Fusion 360. The STEP file is read from the local file path and its geometry is inserted into the target component. This function uses the Fusion 360 import manager to create an import operation.",
          "parameters": {
            "type": "object",
            "properties": {
              "target_component": {
                "type": "string",
                "description": "The name of the target component in the current design where the STEP file will be imported."
              },
              "file_path": {
                "type": "string",
                "description": "The local file path of the STEP file to be imported."
              }
            },
            "required": ["target_component", "file_path"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the STEP file import."
            }
          }
        }
        """
        try:
            # Access the active Fusion 360 design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            # find the target component by name (assuming you have a local helper method).
            targetComp, errors = self._find_component_by_name(target_component)
            if not targetComp:
                return errors

            # Get the import manager from the application
            importMgr = app.importManager

            # Create the STEP import options with the provided file path and target component.
            # Note: The API method createSTEPImportOptions expects a file path and the target component.
            stepOptions = importMgr.createSTEPImportOptions(file_path)
            #prevent auto resize
            stepOptions.isViewFit = False

            # Execute the import operation into the target component
            importOperation = importMgr.importToTarget(stepOptions, targetComp)

            #camera_ = app.activeViewport.camera
            #camera_.isFitView = True
            #app.activeViewport.camera = camera_

            return f"STEP file imported successfully into component '{target_component}'."
        except Exception as e:
            return f"Error: Failed to import STEP file: {e}"

    @ToolCollection.tool_call
    def import_dxf_to_component(self, target_component : str, dxf_file_path: str):
        """
            {
              "name": "import_dxf_to_component",
              "description": "Imports a DXF file into a specified target component on its XY plane in Fusion 360. The function renames the new sketch to match the name of the DXF file, excluding the file extension.",

              "parameters": {
                "type": "object",
                "properties": {
                  "target_component": {
                    "type": "string",
                    "description": "The target component in Fusion 360 where the DXF file will be imported."
                  },
                  "dxf_file_path": {
                    "type": "string",
                    "description": "The file path of the DXF file to be imported."
                  }
                },
                "required": ["target_component", "dxf_file_path"]
              }
            }
        """

        newSketch = None
        try:
            # Check if target_component is a valid Fusion 360 Component object
            if not isinstance(self, target_component, adsk.fusion.Component):
                raise ValueError("target_component must be a fusion 360 Component object")

            app = adsk.core.Application.get()

            # Access the import manager
            importManager = app.importManager

            # Get the XY plane of the target component
            xyPlane = target_component.xYConstructionPlane

            # Create DXF import options
            dxfOptions = importManager.createDXF2DImportOptions(dxf_file_path, xyPlane)

            # Import the DXF file into the target component
            importManager.importToTarget(dxfOptions, target_component)

            # Extract the file name without extension
            file_name = os.path.splitext(os.path.basename(dxf_file_path))[0]

            # Find the newly created sketch by default name "0" and rename it
            for sketch in target_component.sketches:
                if sketch.name == "0":
                    sketch.name = file_name
                    newSketch = sketch
                    break

        except:
            if ui:
                ui.messageBox('Error: Failed to import DXF file:\n{}'.format(traceback.format_exc()))


        return newSketch

    @ToolCollection.tool_call
    def import_fusion_component(self, parent_component_name: str, file_path: str) -> str:
        """
            {
              "name": "import_fusion_component",
              "description": "Imports a FusionArchive file into a specified parent component within the current Fusion 360 design.",
              "parameters": {
                "type": "object",
                "properties": {
                  "parent_component_name": {
                    "type": "string",
                    "description": "The name of the parent component in the current design where the FusionArchive file will be imported."
                  },
                  "file_path": {
                    "type": "string",
                    "description": "The local file path to the FusionArchive file to be imported."
                  }
                },
                "required": ["parent_component_name", "file_path"],
                "returns": {
                  "type": "string",
                  "description": "A message indicating the success or failure of the import operation."
                }
              }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            parentComponent, errors = self._find_component_by_name(parent_component_name)
            if not parentComponent:
                return errors

            # Access the import manager and create import options
            importManager = app.importManager
            fusionArchiveOptions = importManager.createFusionArchiveImportOptions(file_path)

            # Import the FusionArchive file into the parent component
            importManager.importToTarget(fusionArchiveOptions, parentComponent)

            return f'FusionArchive file imported into component "{parent_component_name}"'

        except Exception as e:
            return f'Failed to import FusionArchive file: {e}'


class Joints(ToolCollection):

    @ToolCollection.tool_call
    def list_joint_origin_references(self, component_name: str = "comp1") -> str:
        """
        {
          "name": "list_joint_origin_references",
          "description": "Finds potential reference geometry (faces, edges, vertices, sketch points) in the specified component that can host a Joint Origin. Returns a JSON array, each item includes geometry type, name or index, a referenceId, and approximate X/Y/Z coordinates.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the Fusion 360 component whose geometry references will be listed."
              }
            },
            "required": ["component_name"],
            "returns": {
              "type": "string",
              "description": "A JSON array of references. Each entry might look like { 'referenceId': 'face|body0|face3', 'geometryType': 'face', 'location': [x, y, z], ... }"
            }
          }
        }
        """

        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Find the target component by name
            targetComponent = None
            for comp in design.allComponents:
                if comp.name == component_name:
                    targetComponent = comp
                    break
            if not targetComponent:
                return f"Error: Component '{component_name}' not found."

            references_list = {
                "faces": [],
                "edges": [],
                "vertices": [],
                "sketch_points": [],

            }

            # A helper to get the bounding box center in [x, y, z].
            def bounding_box_center(bbox: adsk.core.BoundingBox3D):
                x = 0.5 * (bbox.minPoint.x + bbox.maxPoint.x)
                y = 0.5 * (bbox.minPoint.y + bbox.maxPoint.y)
                z = 0.5 * (bbox.minPoint.z + bbox.maxPoint.z)
                return [x, y, z]


            # 1) Collect faces (using bounding box center)
            for bodyIndex, body in enumerate(targetComponent.bRepBodies):
                for faceIndex, face in enumerate(body.faces):
                    refId = f"face|body{bodyIndex}|face{faceIndex}"
                    bbox = face.boundingBox
                    loc = bounding_box_center(bbox) if bbox else [0, 0, 0]

                    face_type = face.geometry.objectType
                    #face_type = face.geometry.surfaceType
                    #print(dir(face.geometry))
                    print(f"{faceIndex}: {face_type}")

                    references_list["faces"].append({
                        "referenceId": refId,
                        "geometryType": "face",
                        "faceType": face_type,
                        "number_of_edges": face.edges.count,
                        "area": face.area,
                        "bodyName": body.name,
                        "faceIndex": faceIndex,
                        "location": loc
                    })

            # 2) Collect edges (using bounding box center)
            for bodyIndex, body in enumerate(targetComponent.bRepBodies):
                for edgeIndex, edge in enumerate(body.edges):
                    refId = f"edge|body{bodyIndex}|edge{edgeIndex}"

                    geoType = ""
                    edgeGeo = edge.geometry
                    if isinstance(edgeGeo, adsk.core.Circle3D):
                        geoType = "Circle3D"
                        loc = edge.geometry.center.asArray()
                    elif isinstance(edgeGeo, adsk.core.Line3D):
                        geoType = "Line3D"
                        loc = edge.geometry.startPoint.asArray()
                    elif isinstance(edgeGeo, adsk.core.Arc3D):
                        geoType = "Arc3D"
                        loc = edge.geometry.center.asArray()
                    else:
                        #print(edge.geometry)
                        loc = None

                    if geoType != "Circle3D":
                        continue

                    edgeDict = {
                        "referenceId": refId,
                        "geometryType": f"Edge",
                        "edgeType": geoType,
                        "bodyName": body.name,
                        "edgeIndex": edgeIndex,
                        "location": loc
                    }

                    if geoType == "Circle3D":
                        edgeDict["radius"] = edge.geometry.radius 

                    references_list["edges"].append(edgeDict)


            # 3) Collect vertices (bounding box center = actual vertex coords)
            for bodyIndex, body in enumerate(targetComponent.bRepBodies):
                for vertIndex, vertex in enumerate(body.vertices):
                    refId = f"vertex|body{bodyIndex}|vertex{vertIndex}"

                    if isinstance(vertex, adsk.fusion.BRepVertex):
                        loc = vertex.geometry.asArray()
                    else:
                        loc = None

                    #loc = bounding_box_center(bbox) if bbox else [0, 0, 0]
                    references_list["vertices"].append({
                        "referenceId": refId,
                        "geometryType": "vertex",
                        "bodyName": body.name,
                        "vertexIndex": vertIndex,
                        "location": loc
                    })

            # 4) Collect sketch points (use the 3D geometry of the point)
            for sketchIndex, sketch in enumerate(targetComponent.sketches):
                for pointIndex, skPoint in enumerate(sketch.sketchPoints):
                    refId = f"sketchPoint|sketch{sketchIndex}|point{pointIndex}"
                    geo = skPoint.worldGeometry  # a Point3D in global coords

                    loc = [geo.x, geo.y, geo.z]

                    references_list["sketch_points"].append({
                        "referenceId": refId,
                        "geometryType": "sketchPoint",
                        "sketchName": sketch.name,
                        "sketchPointIndex": pointIndex,
                        "location": loc
                    })


            references_list.pop("vertices")
            #references_list.pop("edges")
            references_list.pop("sketch_points")
            references_list.pop("faces")
            return json.dumps(references_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_joint_origin(self,
                            component_name: str = "comp1",
                            reference_id: str = "face|body0|face1",
                            origin_name: str = "topFaceCenter") -> str:

        """
        {
          "name": "create_joint_origin",
          "description": "Creates a Joint Origin in the specified component, attached to a reference (face/edge/vertex/sketchPoint) identified by reference_id. Names the Joint Origin as specified.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the Fusion 360 component in which to create the Joint Origin."
              },
              "reference_id": {
                "type": "string",
                "description": "ID string for the geometry reference. This typically comes from list_joint_origin_references()."
              },
              "origin_name": {
                "type": "string",
                "description": "A descriptive name for the newly created Joint Origin."
              }
            },
            "required": ["component_name", "reference_id", "origin_name"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any errors that occurred."
            }
          }
        }
        """

        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Find the target component by name
            targetComponent = None
            for comp in design.allComponents:
                if comp.name == component_name:
                    targetComponent = comp
                    break
            if not targetComponent:
                return f"Error: Component '{component_name}' not found."

            tokens = reference_id.split('|')
            if len(tokens) < 2:
                return f"Error: reference_id '{reference_id}' is not in the expected format."

            geometry_type = tokens[0]  # e.g. "face", "edge", "vertex", "sketchPoint"
            refGeom = None

            # We'll define a helper function to parse "bodyN" => integer N
            def parse_body_index(bodyTag):
                m = re.search(r"body(\d+)", bodyTag)
                return int(m.group(1)) if m else None

            if geometry_type in ["face", "edge", "vertex"]:
                if len(tokens) < 3:
                    return f"Error: reference_id '{reference_id}' missing 'bodyX|faceY/edgeY/vertexY'."

                bodyTag = tokens[1]           # e.g. "body0"
                fevTag = tokens[2]           # e.g. "face3", "edge1", or "vertex5"
                bodyIndex = parse_body_index(bodyTag)
                if bodyIndex is None:
                    return f"Error: Could not parse body index from '{bodyTag}'."

                fevMatch = re.search(r"(face|edge|vertex)(\d+)", fevTag)
                if not fevMatch:
                    return f"Error: Could not parse geometry index from '{fevTag}'."
                subType = fevMatch.group(1)  # "face", "edge", or "vertex"
                geomIndex = int(fevMatch.group(2))

                # Get the actual geometry
                bodies = targetComponent.bRepBodies
                if bodyIndex >= bodies.count:
                    return f"Error: Body index {bodyIndex} out of range."
                theBody = bodies.item(bodyIndex)

                if subType == "face":
                    if geomIndex >= theBody.faces.count:
                        return f"Error: Face index {geomIndex} out of range on body {bodyIndex}."

                    faceObj = theBody.faces.item(geomIndex)
                    faceGeo = faceObj.geometry

                    if isinstance(faceGeo, adsk.core.Plane ):
                        # This example assumes the face is planar
                        # For non-planar, use createByNonPlanarFace, etc.
                        planarFace = adsk.fusion.BRepFace.cast(faceObj)

                        if not planarFace or not planarFace.geometry or not isinstance(planarFace.geometry, adsk.core.Plane):
                            return "Error: The specified face is not planar. For non-planar, use createByNonPlanarFace, etc."

                        refGeom = adsk.fusion.JointGeometry.createByPlanarFace(
                            planarFace, #face
                            None, # edge
                            adsk.fusion.JointKeyPointTypes.CenterKeyPoint  # or MidPointKeyPoint, etc.
                        )

                    # center of cylinder
                    elif isinstance(faceGeo, adsk.core.Cylinder ):
                        # This example assumes the face is planar
                        # For non-planar, use createByNonPlanarFace, etc.
                        nonPlanarFace = adsk.fusion.BRepFace.cast(faceObj)
                        print(nonPlanarFace)

                        refGeom = adsk.fusion.JointGeometry.createByNonPlanarFace(
                            nonPlanarFace, #face
                            adsk.fusion.JointKeyPointTypes.MiddleKeyPoint  # or MidPointKeyPoint, etc.
                        )

                elif subType == "edge":

                    if geomIndex >= theBody.edges.count:
                        return f"Error: Edge index {geomIndex} out of range on body {bodyIndex}."
                    edgeObj = theBody.edges.item(geomIndex)


                    # TODO get edge type
                    try:
                        # Use createByCurve with a keypoint type; e.g. MiddleKeyPoint
                        refGeom = adsk.fusion.JointGeometry.createByCurve(
                            edgeObj,
                            adsk.fusion.JointKeyPointTypes.CenterKeyPoint
                        )
                    except Exception as e:
                        # Use createByCurve with a keypoint type; e.g. MiddleKeyPoint
                        refGeom = adsk.fusion.JointGeometry.createByCurve(
                            edgeObj,
                            adsk.fusion.JointKeyPointTypes.MiddleKeyPoint
                        )


                elif subType == "vertex":
                    if geomIndex >= theBody.vertices.count:
                        return f"Error: Vertex index {geomIndex} out of range on body {bodyIndex}."
                    vertexObj = theBody.vertices.item(geomIndex)
                    # For a vertex, use createByPoint
                    refGeom = adsk.fusion.JointGeometry.createByPoint(vertexObj)

            elif geometry_type == "sketchPoint":
                # Expect something like "sketchPoint|sketch0|point2"
                if len(tokens) < 3:
                    return f"Error: reference_id '{reference_id}' is missing 'sketchX|pointY'."

                sketchTag = tokens[1]  # e.g. "sketch0"
                pointTag = tokens[2]   # e.g. "point2"

                s_match = re.search(r"sketch(\d+)", sketchTag)
                p_match = re.search(r"point(\d+)", pointTag)
                if not s_match or not p_match:
                    return f"Error: Could not parse sketch/point indexes from '{sketchTag}', '{pointTag}'."
                sketchIndex = int(s_match.group(1))
                pointIndex = int(p_match.group(1))

                if sketchIndex >= targetComponent.sketches.count:
                    return f"Error: Sketch index {sketchIndex} out of range."
                theSketch = targetComponent.sketches.item(sketchIndex)
                if pointIndex >= theSketch.sketchPoints.count:
                    return f"Error: Sketch point index {pointIndex} out of range."

                skPointObj = theSketch.sketchPoints.item(pointIndex)
                refGeom = adsk.fusion.JointGeometry.createByPoint(skPointObj)

            else:
                return f"Error: Unrecognized geometry type '{geometry_type}' in reference_id '{reference_id}'."

            if not refGeom:
                return f"Error: Could not build JointGeometry for '{reference_id}'. Possibly non-planar or invalid geometry."

            # Now we create the Joint Origin
            joint_origins = targetComponent.jointOrigins
            jo_input = joint_origins.createInput(refGeom)
            # Optionally set orientation or offsets here, e.g.:
            # transform = adsk.core.Matrix3D.create()
            # transform.translation = adsk.core.Vector3D.create(0, 0, 1)  # offset 1 cm
            # jo_input.setByOffset(transform)

            # Add the new Joint Origin
            newJo = joint_origins.add(jo_input)
            newJo.name = origin_name

            return f"Joint Origin '{origin_name}' created for {reference_id} in component '{component_name}'."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_joints_between_origins(self, joint_requests: list = [
            { "occurrence_1_name": "comp1:1",
             "joint_origin_1":"jointOrigin1",
             "occurrence_2_name":"comp2:1",
             "joint_origin_2":"jointOrigin2",
            "jointType":"RigidJointType",
                                      }]
                                      ) -> str:
        """
        {
          "name": "create_joints_between_origins",
          "description": "Creates new joints between pairs of existing jointOrigins. Each request specifies the path (or reference) to two JointOrigins and a joint type.",
          "parameters": {
            "type": "object",
            "properties": {
              "joint_requests": {
                "type": "array",
                "description": "An array of occurrence and joint names items",
                "items": {
                  "type": "object",
                  "properties": {
                    "occurrence_1_name": { "type": "string", "description": "Name of the first occurrence" },
                    "joint_origin_1": { "type": "string", "description": "Name of the first joint origin." },
                    "occurrence_2_name": { "type": "string", "description": "Name of the second occurrence" },
                    "joint_origin_2": { "type": "string", "description": "Name of the second joint origin." },
                    "jointType": {
                      "type": "string",
                      "description": "The type of joint: 'RigidJointType', 'RevoluteJointType', etc."
                    }
                  },
                  "required": ["occurrence_1_name", "joint_origin_1", "occurrence_2_name", "joint_origin_2", "jointType"]
                }
              }
            },
            "required": ["joint_requests"],
            "returns": {
              "type": "string",
              "description": "A summary of created joints or errors encountered."
            }
          }
        }
        """

        try:
            if not joint_requests or not isinstance(joint_requests, list):
                return "Error: Must provide an array of joint requests."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # A mapping from string to the Fusion 360 JointTypes enumerations
            joint_type_map = {
                "RigidJointType": adsk.fusion.JointTypes.RigidJointType,
                "RevoluteJointType": adsk.fusion.JointTypes.RevoluteJointType,
                "SliderJointType": adsk.fusion.JointTypes.SliderJointType,
                "CylindricalJointType": adsk.fusion.JointTypes.CylindricalJointType,
                "PinSlotJointType": adsk.fusion.JointTypes.PinSlotJointType,
                "PlanarJointType": adsk.fusion.JointTypes.PlanarJointType,
                "BallJointType": adsk.fusion.JointTypes.BallJointType
            }

            results = []

            # A helper to find a joint origin by name or path (assuming unique naming)
            def find_joint_origin_by_name(occ, name_str):
                # Search in all components
                for j_origin in occ.component.jointOrigins:
                    print(j_origin.name)
                    if j_origin.name == name_str:
                        return j_origin

                return None


            for request in joint_requests:
                #print(request)
                occ_1_name = request.get("occurrence_1_name")
                j1_name = request.get("joint_origin_1")
                occ_2_name = request.get("occurrence_2_name")
                j2_name = request.get("joint_origin_2")

                j_type_str = request.get("jointType")

                occ1, errors, = self._find_occurrence_by_name(occ_1_name)
                if not occ1:
                    results.append(errors)
                    continue
                occ2, errors, = self._find_occurrence_by_name(occ_2_name)
                if not occ2:
                    results.append(errors)
                    continue


                if not (j1_name and j2_name and j_type_str):
                    results.append(f"Error: Missing fields in {request}")
                    continue

                # Map the jointType string
                if j_type_str not in joint_type_map:
                    results.append(f"Error: Unknown jointType '{j_type_str}' in {request}")
                    continue
                the_joint_type = joint_type_map[j_type_str]

                # Find the joint origins by their name or path
                joint_origin_1 = find_joint_origin_by_name(occ1, j1_name)
                joint_origin_2 = find_joint_origin_by_name(occ2, j2_name)

                if not joint_origin_1 or not joint_origin_2:
                    results.append(f"Error: Could not find one or both JointOrigins '{j1_name}', '{j2_name}'.")
                    continue

                # Create a JointInput
                #joint_origin_1 = joint_origin_1.occurrenceForGeometry(occ1)
                #joint_origin_2 = joint_origin_2.occurrenceForGeometry(occ2)

                joints_collection = root_comp.joints
                j_input = joints_collection.createInput(
                    joint_origin_1, joint_origin_2
                )

                # TODO need to handle all joint types here
                #j_input.setAsStandardJoint(the_joint_type)
                j_input.setAsRigidJointMotion()

                # Add the joint
                try:
                    new_joint = joints_collection.add(j_input)
                    results.append(
                        f"Joint of type '{j_type_str}' created between '{j1_name}' and '{j2_name}'."
                    )
                except Exception as e:
                    results.append(f"Error creating joint between '{j1_name}' and '{j2_name}': {str(e)}")

            return "\n".join(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    #@ToolCollection.tool_call
    def modify_joint_origin(self,
                            joint_origin_name: str = None,
                            new_geometry: dict = None,
                            new_orientation: dict = None) -> str:
        """
        {
          "name": "modify_joint_origin",
          "description": "Modifies an existing joint origin, including its attachment point (geometry) and orientation (offset or angle).",
          "parameters": {
            "type": "object",
            "properties": {
              "joint_origin_name": {
                "type": "string",
                "description": "Name of the joint origin to modify."
              },
              "new_geometry": {
                "type": "object",
                "description": "An optional specification of new geometry for the joint origin. For example: { 'type': 'face', 'component_name': 'comp1', 'body_index': 0, 'face_index': 2 } or { 'type': 'sketchPoint', ... }"
              },
              "new_orientation": {
                "type": "object",
                "description": "An optional specification of transform or offset. E.g. { 'offsetX': 1.0, 'offsetY': 0.5, 'offsetZ': 0 } in cm or an angle in degrees."
              }
            },
            "required": ["joint_origin_name"],
            "returns": {
              "type": "string",
              "description": "A success or error message."
            }
          }
        }
        """

        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            if not joint_origin_name:
                return "Error: joint_origin_name is required."

            # Locate the joint origin by name
            target_jo = None
            for comp in design.allComponents:
                for jo in comp.jointOrigins:
                    if jo.name == joint_origin_name:
                        target_jo = jo
                        break
                if target_jo:
                    break

            if not target_jo:
                return f"Error: JointOrigin '{joint_origin_name}' not found."

            # We retrieve the existing definition
            jo_def = target_jo.definition
            # For example, jo_def is typically a "JointOriginDefinition" object, which might be
            # an OffsetPlaneJointOriginDefinition, etc.

            # 1) If new_geometry is specified, reattach to new geometry
            if new_geometry and isinstance(new_geometry, dict):
                # We'll do a simplistic approach; you can adapt to your geometry approach
                # e.g. re-creating a JointGeometry by face/edge/sketchPoint, etc.
                new_geom_ref = None
                geom_type = new_geometry.get("type")  # e.g. "face", "edge", "sketchPoint"
                comp_name = new_geometry.get("component_name")
                body_index = new_geometry.get("body_index")
                face_index = new_geometry.get("face_index")
                # etc. This part is flexible, depending on how you define your references.

                # Example: if we detect "face" and the user provided body_index, face_index
                if geom_type == "face" and comp_name is not None and body_index is not None and face_index is not None:
                    # Find the component
                    new_comp = None
                    for c in design.allComponents:
                        if c.name == comp_name:
                            new_comp = c
                            break
                    if not new_comp:
                        return f"Error: Could not find component '{comp_name}' for new geometry."

                    if body_index < 0 or body_index >= new_comp.bRepBodies.count:
                        return f"Error: body_index {body_index} out of range in comp '{comp_name}'."

                    the_body = new_comp.bRepBodies.item(body_index)
                    if face_index < 0 or face_index >= the_body.faces.count:
                        return f"Error: face_index {face_index} out of range in body {body_index}."

                    the_face = the_body.faces.item(face_index)
                    # Create a new JointGeometry
                    plane_face = adsk.fusion.BRepFace.cast(the_face)
                    if plane_face and isinstance(plane_face.geometry, adsk.core.Plane):
                        new_geom_ref = adsk.fusion.JointGeometry.createByPlanarFace(
                            plane_face,
                            adsk.fusion.JointKeyPointTypes.CenterKeyPoint
                        )
                    else:
                        return "Error: Only planar faces handled in this sample."

                # If new_geom_ref is found, update definition
                if new_geom_ref:
                    # Reattach
                    jo_def.reattach(new_geom_ref)

            # 2) If new_orientation is specified, apply offset or angles
            #    For example, if user provides an offsetX, offsetY, offsetZ in cm
            #    or a rotation angle in degrees about some axis, etc.
            if new_orientation and isinstance(new_orientation, dict):
                # We'll do a basic offset approach.
                ox = new_orientation.get("offsetX", 0.0)
                oy = new_orientation.get("offsetY", 0.0)
                oz = new_orientation.get("offsetZ", 0.0)

                if abs(ox) > 1e-7 or abs(oy) > 1e-7 or abs(oz) > 1e-7:
                    offset_transform = adsk.core.Matrix3D.create()
                    offset_transform.translation = adsk.core.Vector3D.create(ox, oy, oz)
                    # The setByOffset method replaces the existing orientation
                    jo_def.setByOffset(offset_transform)

                # If you also want angles, you'd do a rotation in the transform or use
                # jo_def.setByXXX(...). The specifics can be expanded if needed.

            return f"Joint Origin '{joint_origin_name}' modified successfully."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

