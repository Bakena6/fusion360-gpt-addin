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

from . import shared
from . import document_data



def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")



# send info to html palette
PALETTE_ID = config.palette_id
app = adsk.core.Application.get()
ui = app.userInterface
palette = ui.palettes.itemById(PALETTE_ID)


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

        # method collections
        self.submodules = [
            document_data.GetStateData(),
            document_data.SetStateData(),
            CreateObjects(),
            ModifyObjects(),
            DeleteObjects(),
            ImportExport(),
            Sketches(),
            Joints(),
            Timeline(),
            NonCad(),
        ]

        fusion_methods = {}
        for submod in self.submodules:
            for method_name, method in submod.methods.items():
                # add method from container classes to main interface class
                setattr(self, method_name, method)


    # TODO do this without hard coading modules name
    def _reload_modules(self):
        importlib.reload(shared)
        importlib.reload(document_data)

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
                json_method = json.loads(docstring)
                method_list.append(json_method)


        method_list = json.dumps(method_list)
        self.tools_json = method_list
        return method_list


    # TODO function calls should be wrapped
    def fusion_call(func):
        """
        Wraps fusion interface calls
        """
        # for retrieving wrapped function kwarg names
        @functools.wraps(func)
        def wrapper(self, *args, **kwds):

            self.app = adsk.core.Application.get()
            print("func start")
            result = func(self, *args, **kwds)
            print("func end")
            return result

        return wrapper








class Sketches(ToolCollection):

    ###### ====== cad design ====== ######
    @ToolCollection.tool_call
    def get_sketch_profiles(self, component_name: str = "comp1", sketch_name: str = "Sketch1"):
        """
        {
            "name": "get_sketch_profiles",
            "description": "Retrieves all the profiles from a specified sketch within a specified component. Returns a JSON-like object containing each profile's area, center point, and areaIndex (with 0 being the largest profile).",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the sketch."
                    },
                    "sketch_name": {
                        "type": "string",
                        "description": "The name of the sketch inside the specified component."
                    }
                },
                "required": ["component_name", "sketch_name"],
                "returns": {
                    "type": "object",
                    "description": "A JSON-like dictionary with a 'profiles' key, listing each profile's area, centroid (x, y, z), and areaIndex sorted by descending area. If an error occurs, a string describing the error is returned instead."
                }
            }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # Use a local helper method to find the target component
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            if not targetSketch.profiles or targetSketch.profiles.count == 0:
                return "No profiles found in the sketch."

            # Gather profile information (area and centroid)
            profile_data = []
            for profile in targetSketch.profiles:
                props = profile.areaProperties()
                area = props.area
                centroid = props.centroid
                profile_data.append({
                    "profile": profile,  # Storing the actual profile object (if needed)
                    "area": area,
                    "centroid": [centroid.x, centroid.y, centroid.z]
                })

            # Sort profiles by descending area
            profile_data.sort(key=lambda p: p["area"], reverse=True)

            # Create the final list of profile info for JSON-like output
            results = []
            for idx, data in enumerate(profile_data):
                results.append({
                    "areaIndex": idx,  # 0 = largest
                    "area": data["area"],
                    "centerPoint": data["centroid"]
                })

            # Return the JSON-like structure
            return json.dumps({ "profiles": results })

        except Exception as e:
            return f"Error: {e}"

    @ToolCollection.tool_call
    def get_edges_in_body(self, component_name: str="comp1", body_name: str="Body1") -> str:
        """
        {
            "name": "get_edges_in_body",
            "description": "Generates a list of all edges in a specified BRep body, including position and orientation data that can be used for future operations like fillets or chamfers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the body."
                    },
                    "body_name": {
                        "type": "string",
                        "description": "The name of the target body whose edges will be listed."
                    }
                },
                "required": ["component_name", "body_name"],
                "returns": {
                    "type": "string",
                    "description": "A JSON array of edge information. Each element contains 'index', 'geometryType', 'length', bounding-box data, and geometry-specific data like direction vectors or center points."
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

            # Locate the target component by name (assuming you have a helper method)
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body, errors = self._find_body_by_name(targetComponent, body_name)
            if not body:
                return errors

            edges = body.edges
            edge_data_list = []

            for i, edge in enumerate(edges):
                geom = edge.geometry
                geometryType = type(geom).__name__  # e.g., "Line3D", "Arc3D", "Circle3D", etc.

                # Basic edge info
                edge_info = {
                    "index": i,
                    "geometryType": geometryType,
                    "length": edge.length
                }

                # 1) Collect bounding box data
                bb = edge.boundingBox
                if bb:
                    edge_info["boundingBox"] = {
                        "minPoint": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                        "maxPoint": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]
                    }

                # 2) Collect geometry-specific data
                if isinstance(geom, adsk.core.Line3D):
                    # For finite lines, startPoint and endPoint will be non-null.
                    startPt = geom.startPoint
                    endPt = geom.endPoint

                    # Compute direction: end - start
                    if startPt and endPt:
                        directionVec = adsk.core.Vector3D.create(
                            endPt.x - startPt.x,
                            endPt.y - startPt.y,
                            endPt.z - startPt.z
                        )
                        edge_info["geometryData"] = {
                            "startPoint": [startPt.x, startPt.y, startPt.z],
                            "endPoint": [endPt.x, endPt.y, endPt.z],
                            "direction": [directionVec.x, directionVec.y, directionVec.z]
                        }
                    else:
                        # If the line is infinite (rare in typical Fusion designs),
                        # the start/endPoints might be None.
                        # You could call getData(...) here if needed.
                        edge_info["geometryData"] = {
                            "startPoint": None,
                            "endPoint": None,
                            "direction": None
                        }

                elif isinstance(geom, adsk.core.Arc3D):
                    centerPt = geom.center
                    normalVec = geom.normal
                    edge_info["geometryData"] = {
                        "centerPoint": [centerPt.x, centerPt.y, centerPt.z],
                        "normal": [normalVec.x, normalVec.y, normalVec.z],
                        "radius": geom.radius,
                        "startAngle": geom.startAngle,
                        "endAngle": geom.endAngle
                    }

                elif isinstance(geom, adsk.core.Circle3D):
                    centerPt = geom.center
                    normalVec = geom.normal
                    edge_info["geometryData"] = {
                        "centerPoint": [centerPt.x, centerPt.y, centerPt.z],
                        "normal": [normalVec.x, normalVec.y, normalVec.z],
                        "radius": geom.radius
                    }

                elif isinstance(geom, adsk.core.Ellipse3D):
                    centerPt = geom.center
                    normalVec = geom.normal
                    edge_info["geometryData"] = {
                        "centerPoint": [centerPt.x, centerPt.y, centerPt.z],
                        "normal": [normalVec.x, normalVec.y, normalVec.z],
                        "majorRadius": geom.majorRadius,
                        "minorRadius": geom.minorRadius
                    }

                elif isinstance(geom, adsk.core.NurbsCurve3D):
                    # NURBS curves can be more complex:
                    # store some minimal data; adjust as needed
                    edge_info["geometryData"] = {
                        "isNurbs": True,
                        "degree": geom.degree,
                        "controlPointCount": geom.controlPointCount
                    }

                edge_data_list.append(edge_info)

            # Return the collected info in JSON format
            return json.dumps(edge_data_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def get_faces_in_body(self, component_name: str="comp1", body_name: str = "Body1") -> str:
        """
        {
            "name": "get_faces_in_body",
            "description": "Generates a list of all faces in the specified BRep body. Returns face data in JSON format that can be used for future operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the body."
                    },
                    "body_name": {
                        "type": "string",
                        "description": "The name of the target body whose faces will be listed."
                    }
                },
                "required": ["component_name", "body_name"],
                "returns": {
                    "type": "string",
                    "description": "A JSON array of face information. Each element contains keys such as 'index', 'surfaceType', 'area', and 'boundingBox'."
                }
            }
        }
        """

        try:
            app = adsk.core.Application.get()
            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Find the target component by name (assuming you have a local helper method).
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body, errors = self._find_body_by_name(targetComponent, body_name)
            if not body:
                return errors

            faces = body.faces
            face_data_list = []

            for i, face in enumerate(faces):
                geom = face.geometry
                surface_type = type(geom).__name__  # e.g., "Plane", "Cylinder", "Cone", "Sphere", "Torus", "NurbsSurface"

                # Store basic face info
                face_info = {
                    "index": i,
                    "surfaceType": surface_type,
                    "area": face.area
                }

                # Collect bounding box data for the face (if available)
                bb = face.boundingBox
                if bb:
                    face_info["boundingBox"] = {
                        "minPoint": [bb.minPoint.x, bb.minPoint.y, bb.minPoint.z],
                        "maxPoint": [bb.maxPoint.x, bb.maxPoint.y, bb.maxPoint.z]
                    }

                # Collect geometry-specific data
                geometry_data = {}
                if isinstance(geom, adsk.core.Cylinder):
                    # Cylindrical face
                    axis = geom.axis
                    origin = geom.origin
                    geometry_data = {
                        "axisVector": [axis.x, axis.y, axis.z],
                        "origin": [origin.x, origin.y, origin.z],
                        "radius": geom.radius
                    }

                elif isinstance(geom, adsk.core.Sphere):
                    # Spherical face
                    center = geom.center
                    geometry_data = {
                        "center": [center.x, center.y, center.z],
                        "radius": geom.radius
                    }

                elif isinstance(geom, adsk.core.Torus):
                    # Torus face
                    center = geom.center
                    axis = geom.axis
                    geometry_data = {
                        "center": [center.x, center.y, center.z],
                        "axisVector": [axis.x, axis.y, axis.z],
                        "majorRadius": geom.majorRadius,
                        "minorRadius": geom.minorRadius
                    }

                elif isinstance(geom, adsk.core.Cone):
                    # Conical face
                    axis = geom.axis
                    origin = geom.origin
                    geometry_data = {
                        "axisVector": [axis.x, axis.y, axis.z],
                        "origin": [origin.x, origin.y, origin.z],
                        "halfAngle": geom.halfAngle
                    }

                elif isinstance(geom, adsk.core.NurbsSurface):
                    # Nurbs-based face
                    geometry_data = {
                        "isNurbsSurface": True,
                        "uDegree": geom.degreeU,
                        "vDegree": geom.degreeV,
                        "controlPointCountU": geom.controlPointCountU,
                        "controlPointCountV": geom.controlPointCountV
                    }

                if geometry_data:
                    face_info["geometryData"] = geometry_data

                face_data_list.append(face_info)

            # Convert the collected face data to a JSON string
            return json.dumps(face_data_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_sketch(self, component_name: str="comp1", sketch_name: str ="Sketch1", sketch_plane: str ="xy"):
        """
            {
              "name": "create_sketch",
              "description": "Creates a sketch within a specified component on a specified plane in Fusion 360. The plane can be xy, xz, or yz.",
              "parameters": {
                "type": "object",
                "properties": {
                  "component_name": {
                    "type": "string",
                    "description": "The name of the component where the sketch will be created."
                  },
                  "sketch_name": {
                    "type": "string",
                    "description": "The name for the new sketch to be created."
                  },
                  "sketch_plane": {
                    "type": "string",
                    "enum": ["xy", "xz", "yz"],
                    "description": "The plane on which the sketch will be created. Possible values are 'xy', 'xz', 'yz'. Default is 'xy'."
                  }
                },
                "required": ["component_name", "sketch_name"],
                "returns": {
                  "type": "string",
                  "description": "A message indicating the success or failure of the sketch creation."
                }
              }
            }
        """

        try:
            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent


            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors


            # Determine the sketch plane
            if sketch_plane.lower() == "xz":
                plane = targetComponent.xZConstructionPlane
            elif sketch_plane.lower() == "yz":
                plane = targetComponent.yZConstructionPlane
            else:  # Default to XY plane
                plane = targetComponent.xYConstructionPlane

            # Create the sketch
            newSketch = targetComponent.sketches.add(plane)
            newSketch.name = sketch_name

            return f'Sketch "{sketch_name}" created successfully'

        except Exception as e:
            return f'Error: Failed to create sketch: {e}'


    @ToolCollection.tool_call
    def create_circles_in_sketch(self, component_name:str="comp1", sketch_name:str="Sketch1", point_list:str=[[1,1,0]], circle_diameter_list:list=[10]):
        """
        {
          "name": "create_circles_in_sketch",
          "description": "Creates circles in a specified sketch within a specified component in Fusion 360. Each circle is created at a point provided in the point_list, with its diameter specified by the corresponding element in circle_diameter_list. The units for point_list and circleDiameter is centimeters.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component in the current design."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the sketch inside the specified component."
              },
              "point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 3,
                  "maxItems": 3,
                  "description": "A list representing an XYZ point."
                },
                "description": "A list of lists, each representing an XYZ point (x, y, z) where a circle will be created."
              },
              "circle_diameter_list": {
                "type": "array",
                "items": {
                  "type": "number"
                },
                "description": "A list of diameters for the circles, corresponding to each point in point_list."
              }
            },
            "required": ["component_name", "sketch_name", "point_list", "circle_diameter_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the circle creation."
            }
          }
        }
        """
        try:
            # Validate the lengths of point_list and circle_diameter_list
            if len(point_list) != len(circle_diameter_list):
                return "Error: The lengths of point_list and circle_diameter_list must be equal."

            # Access the active design
            app = adsk.core.Application.get()
            #ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # use base class method
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors


            # Find the target sketch
            targetSketch = None
            for sketch in targetComponent.sketches:
                if sketch.name == sketch_name:
                    targetSketch = sketch
                    break

            if not targetSketch:
                return f'Sketch "{sketch_name}" not found in component "{component_name}"'

            # Create circles in the sketch
            for point, diameter in zip(point_list, circle_diameter_list):

                centerPoint = adsk.core.Point3D.create(point[0], point[1], point[2])

                # circle entity
                entity = targetSketch.sketchCurves.sketchCircles.addByCenterRadius(centerPoint, diameter / 2)
                # offset the text label
                textPoint = adsk.core.Point3D.create(point[0]+1, point[1]+1, point[2])
                dimensions = targetSketch.sketchDimensions
                circleDimension = dimensions.addDiameterDimension(entity, textPoint)

            return f'Circles created in sketch "{sketch_name}"'

        except Exception as e:
            return f'Error: Failed to create circles in sketch: {e}'

    @ToolCollection.tool_call
    def create_polygon_in_sketch(self,
                                 component_name: str = "comp1",
                                 sketch_name: str = "Sketch1",
                                 center_point: list = [0.0, 0.0, 0.0],
                                 radius: float = 1.0,
                                 number_of_sides: int = 6,
                                 orientation_angle_degrees: float = 0.0,
                                 is_inscribed: bool = False) -> str:
        """
        {
            "name": "create_polygon_in_sketch",
            "description": "Creates a regular polygon in the specified sketch using the addScribedPolygon method. The polygon is defined by its center, radius, number of sides, orientation angle, and whether it is inscribed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the sketch."
                    },
                    "sketch_name": {
                        "type": "string",
                        "description": "The name of the sketch within the specified component."
                    },
                    "center_point": {
                        "type": "array",
                        "description": "The [x, y, z] coordinates for the polygon center on the sketch plane.",
                        "items": { "type": "number" }
                    },
                    "radius": {
                        "type": "number",
                        "description": "Radius of the polygon (distance from center to a vertex if inscribed=true, or to a midpoint of a side if inscribed=false)."
                    },
                    "number_of_sides": {
                        "type": "number",
                        "description": "Number of sides of the regular polygon."
                    },
                    "orientation_angle_degrees": {
                        "type": "number",
                        "description": "Rotation of the polygon about its center, in degrees."
                    },
                    "is_inscribed": {
                        "type": "boolean",
                        "description": "If true, polygon is inscribed (radius from center to vertex). If false, circumscribed (radius from center to midpoint of side)."
                    }
                },
                "required": [
                    "component_name",
                    "sketch_name",
                    "center_point",
                    "radius",
                    "number_of_sides",
                    "orientation_angle_degrees",
                    "is_inscribed"
                ],
                "returns": {
                    "type": "string",
                    "description": "A message indicating success or details about any errors encountered."
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

            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors


            # Validate parameters.
            if number_of_sides < 3:
                return "Error: A polygon must have at least 3 sides."
            if radius <= 0:
                return "Error: Radius must be positive."

            # Convert center_point to a 3D point (Z=0 in sketch plane).
            centerPnt = adsk.core.Point3D.create(center_point[0],
                                                 center_point[1],
                                                 center_point[2],
                                                 )

            # Convert the orientation angle to radians.
            orientation_angle_radians = math.radians(orientation_angle_degrees)

            # Access the SketchLines object from the sketch.
            sketchLines_var = targetSketch.sketchCurves.sketchLines

            # Create the polygon using the old 'addScribedPolygon' method.
            #   addScribedPolygon(centerPoint, edgeCount, angle, radius, isInscribed)
            # - centerPoint: adsk.core.Point3D
            # - edgeCount: int (number of sides)
            # - angle: float in RADIANS (orientation of polygon)
            # - radius: float (distance from center to vertex if isInscribed = True, else to side midpoint)
            # - isInscribed: bool

            scribed_polygon = sketchLines_var.addScribedPolygon(
                centerPnt,
                number_of_sides,
                orientation_angle_radians,
                radius,
                is_inscribed
            )


            n_sketch_points = targetSketch.sketchPoints.count
            centerSketchPoint = targetSketch.sketchPoints.item(n_sketch_points-1)

            # fix initial location so it does not move during repositioning
            centerSketchPoint.isFixed = True

            # Find the first edge, point is added and mid point contrained
            firstEdge = scribed_polygon[0]  # First polygon edge

            midpoint = adsk.core.Point3D.create(0, 0, 0)
            midpointSketchPoint = targetSketch.sketchPoints.add(midpoint)

            # Apply a Midpoint Constraint (ensures the point is always attached to the line)
            targetSketch.geometricConstraints.addMidPoint(midpointSketchPoint, firstEdge)

            dimensions = targetSketch.sketchDimensions

             # Get the center sketch point (first point created)
            dim = dimensions.addDistanceDimension(
                centerSketchPoint,  # Center of polygon
                midpointSketchPoint,  # Midpoint of an edge

                adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                #adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                adsk.core.Point3D.create(center_point[0] * 1.5, center_point[1]*1.1, center_point[2]),
                True
            )  # Position for the dimension text


            #dim.parameter.comments = radius  # Set the radius dimension

            # scribed_polygon returns a SketchLineList object that you can inspect if needed.

            poly_type = "inscribed" if is_inscribed else "circumscribed"
            return (
                f"Successfully created a {number_of_sides}-sided polygon "
                f"({poly_type}, radius={radius}) in sketch '{sketch_name}' "
                f"with orientation {orientation_angle_degrees} degrees."
            )

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_spline_in_sketch(self, component_name: str = "comp1", sketch_name: str = "Sketch1", point_list: list = [[0, 0, 0], [1, 1, 0], [2, 0, 0]]):
        """
        {
          "name": "create_spline_in_sketch",
          "description": "Creates a spline in a specified sketch within a specified component in Fusion 360. The spline is defined by an array of points (each an [x, y, z] coordinate in centimeters) that the spline will interpolate through. This function finds the target component and sketch, then constructs a fitted spline based on the provided points.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component in the current design."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the sketch inside the specified component."
              },
              "point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 3,
                  "maxItems": 3,
                  "description": "A list representing an XYZ point (x, y, z) on the sketch plane."
                },
                "description": "An array of points through which the spline will be drawn. The unit for point coordinates is centimeters."
              }
            },
            "required": ["component_name", "sketch_name", "point_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the spline creation."
            }
          }
        }
        """

        try:
            # If point_list is passed as a JSON string, convert it to a list
            if isinstance(point_list, str):
                point_list = json.loads(point_list)

            # Access the active Fusion 360 design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            root_comp = design.rootComponent

            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            # Create an object collection for the spline points
            points_collection = adsk.core.ObjectCollection.create()
            for pt in point_list:
                if len(pt) != 3:
                    return "Error: Each point in point_list must have three coordinates (x, y, z)."
                point3D = adsk.core.Point3D.create(pt[0], pt[1], pt[2])
                points_collection.add(point3D)

            # Create the spline in the sketch using the fitted spline method
            spline = targetSketch.sketchCurves.sketchFittedSplines.add(points_collection)

            return f"Spline created in sketch '{sketch_name}' of component '{component_name}'."
        except Exception as e:
            return f"Error: Failed to create spline in sketch: {e}"


    @ToolCollection.tool_call
    def create_rectangles_in_sketch(self, component_name: str="comp1", sketch_name: str="Sketch1", center_point_list: list=[[1,1,0]], rectangle_size_list:list=[[2,4]]):
        """
        {
          "name": "create_rectangles_in_sketch",
          "description": "Creates rectangles in a specified sketch within a specified component in Fusion 360 using addCenterPointRectangle. Each rectangle is defined by a center point (from center_point_list) and a size (width, height) from rectangle_size_list. A corner point is calculated automatically from the center and half the width and height, and two distance dimensions (horizontal and vertical) are applied. The number of elemenets in center_point_list must be equal to the number of elements in rectangle_size_lis. The unit for center_point_list and rectangle_size_list is centimeters",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component in the current design."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the sketch inside the specified component."
              },
              "center_point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 3,
                  "maxItems": 3,
                  "description": "A list representing an XYZ point (x, y, z)."
                },
                "description": "A list of center points in 3D space for each rectangle to be created."
              },
              "rectangle_size_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 2,
                  "maxItems": 2,
                  "description": "A list representing the width and height of the rectangle."
                },
                "description": "A list of [width, height] pairs, corresponding to each center point in center_point_list."
              }
            },
            "required": ["component_name", "sketch_name", "center_point_list", "rectangle_size_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the rectangle creation."
            }
          }
        }
        """

        try:


            # if dim list passed in as string from user input box
            if isinstance(center_point_list, str):
                center_point_list = json.loads(center_point_list)
            if isinstance(rectangle_size_list, str):
                rectangle_size_list = json.loads(rectangle_size_list)


            # Validate input lengths
            if len(center_point_list) != len(rectangle_size_list):

                center_point_len = len(center_point_list)
                rectangle_size_len = len(rectangle_size_list)

                message = f"The lengths of center_point_list ({center_point_len}) and rectangle_size_list ({rectangle_size_len}) must be equal."

                return message

            # Access the active design
            app = adsk.core.Application.get()
            #ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            root_comp = design.rootComponent

            # Find the target component
            targetComponent = None
            for occ in root_comp.allOccurrences:
                if occ.component.name == component_name:
                    targetComponent = occ.component
                    break

            # use base class method
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors


            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            # Create rectangles in the sketch
            for center_point, size in zip(center_point_list, rectangle_size_list):
                width, height = size[0], size[1]

                # Create the center point 3D object
                center3D = adsk.core.Point3D.create(center_point[0], center_point[1], center_point[2])

                # Calculate the corner point (relative to center)
                # For an axis-aligned rectangle, corner is (center.x + width/2, center.y + height/2, center.z).
                corner3D = adsk.core.Point3D.create(
                    center_point[0] + width / 2.0,
                    center_point[1] + height / 2.0,
                    center_point[2]
                )

                # Create the rectangle using addCenterPointRectangle
                rectangleLines = targetSketch.sketchCurves.sketchLines.addCenterPointRectangle(center3D, corner3D)

                # The addCenterPointRectangle returns a list of four SketchLine objects.
                # Typically:
                #   lines[0]: horizontal line (top or bottom)
                #   lines[1]: vertical line (left or right)
                #   lines[2]: horizontal line (the other top/bottom)
                #   lines[3]: vertical line (the other left/right)

                dimensions = targetSketch.sketchDimensions

                # Dimension the first horizontal line as the 'width'
                horizontalLine = rectangleLines[0]
                dimPointWidth = adsk.core.Point3D.create(center_point[0], center_point[1] - 1, center_point[2])
                dimWidth = dimensions.addDistanceDimension(
                    horizontalLine.startSketchPoint,
                    horizontalLine.endSketchPoint,
                    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                    dimPointWidth
                )

                # Dimension the first vertical line as the 'height'
                verticalLine = rectangleLines[1]
                dimPointHeight = adsk.core.Point3D.create(center_point[0] - 1, center_point[1], center_point[2])
                dimHeight = dimensions.addDistanceDimension(
                    verticalLine.startSketchPoint,
                    verticalLine.endSketchPoint,
                    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                    dimPointHeight
                )

                # Optionally set exact values of the parameters to fix the rectangle size
                # Uncomment if you need these to be parametric at exactly 'width' and 'height':
                #
                # dimWidth.parameter.value = width
                # dimHeight.parameter.value = height

            return f'Rectangles created in sketch "{sketch_name}" using center-point rectangle method.'

        except Exception as e:

            return f'Error: Failed to create rectangles in sketch: {e}'


    def _create_rectangles_in_sketch(self, component_name: str="comp1", sketch_name: str="Sketch1", center_point_list: list=[[1,1,0]], rectangle_size_list:list=[[2,4]]):
        """
            {
              "name": "create_rectangles_in_sketch",
              "description": "Creates rectangles in a specified sketch within a specified component in Fusion 360 using addCenterPointRectangle. Each rectangle is defined by a center point (from center_point_list) and a size (width, height) from rectangle_size_list. A corner point is calculated automatically from the center and half the width and height, and two distance dimensions (horizontal and vertical) are applied. The number of elemenets in center_point_list must be equal to the number of elements in rectangle_size_lis. The unit for center_point_list and rectangle_size_list is centimeters",
              "parameters": {
                "type": "object",
                "properties": {
                  "component_name": {
                    "type": "string",
                    "description": "The name of the component in the current design."
                  },
                  "sketch_name": {
                    "type": "string",
                    "description": "The name of the sketch inside the specified component."
                  },
                  "center_point_list": {
                    "type": "array",
                    "items": {
                      "type": "array",
                      "items": {
                        "type": "number"
                      },
                      "minItems": 3,
                      "maxItems": 3,
                      "description": "A list representing an XYZ point (x, y, z)."
                    },
                    "description": "A list of center points in 3D space for each rectangle to be created."
                  },
                  "rectangle_size_list": {
                    "type": "array",
                    "items": {
                      "type": "array",
                      "items": {
                        "type": "number"
                      },
                      "minItems": 2,
                      "maxItems": 2,
                      "description": "A list representing the width and height of the rectangle."
                    },
                    "description": "A list of [width, height] pairs, corresponding to each center point in center_point_list."
                  }
                },
                "required": ["component_name", "sketch_name", "center_point_list", "rectangle_size_list"],
                "returns": {
                  "type": "string",
                  "description": "A message indicating the success or failure of the rectangle creation."
                }
              }
            }
        """

        try:


            # if dim list passed in as string from user input box
            if isinstance(center_point_list, str):
                center_point_list = json.loads(center_point_list)
            if isinstance(rectangle_size_list, str):
                rectangle_size_list = json.loads(rectangle_size_list)


            # Validate input lengths
            if len(center_point_list) != len(rectangle_size_list):

                center_point_len = len(center_point_list)
                rectangle_size_len = len(rectangle_size_list)

                message = f"The lengths of center_point_list ({center_point_len}) and rectangle_size_list ({rectangle_size_len}) must be equal."

                return message

            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            root_comp = design.rootComponent

            # use base class method
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            # Create rectangles in the sketch
            for center_point, size in zip(center_point_list, rectangle_size_list):
                width, height = size[0], size[1]

                # Create the center point 3D object
                center3D = adsk.core.Point3D.create(center_point[0], center_point[1], center_point[2])

                # Calculate the corner point (relative to center)
                # For an axis-aligned rectangle, corner is (center.x + width/2, center.y + height/2, center.z).
                corner3D = adsk.core.Point3D.create(
                    center_point[0] + width / 2.0,
                    center_point[1] + height / 2.0,
                    center_point[2]
                )

                # Create the rectangle using addCenterPointRectangle
                rectangleLines = targetSketch.sketchCurves.sketchLines.addCenterPointRectangle(center3D, corner3D)

                # The addCenterPointRectangle returns a list of four SketchLine objects.
                # Typically:
                #   lines[0]: horizontal line (top or bottom)
                #   lines[1]: vertical line (left or right)
                #   lines[2]: horizontal line (the other top/bottom)
                #   lines[3]: vertical line (the other left/right)

                dimensions = targetSketch.sketchDimensions

                # Dimension the first horizontal line as the 'width'
                horizontalLine = rectangleLines[0]
                dimPointWidth = adsk.core.Point3D.create(center_point[0], center_point[1] - 1, center_point[2])
                dimWidth = dimensions.addDistanceDimension(
                    horizontalLine.startSketchPoint,
                    horizontalLine.endSketchPoint,
                    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                    dimPointWidth
                )

                # Dimension the first vertical line as the 'height'
                verticalLine = rectangleLines[1]
                dimPointHeight = adsk.core.Point3D.create(center_point[0] - 1, center_point[1], center_point[2])
                dimHeight = dimensions.addDistanceDimension(
                    verticalLine.startSketchPoint,
                    verticalLine.endSketchPoint,
                    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                    dimPointHeight
                )

                # Optionally set exact values of the parameters to fix the rectangle size
                # Uncomment if you need these to be parametric at exactly 'width' and 'height':
                #
                # dimWidth.parameter.value = width
                # dimHeight.parameter.value = height

            return f'Rectangles created in sketch "{sketch_name}" using center-point rectangle method.'

        except Exception as e:

            return f'Error: Failed to create rectangles in sketch: {e}'


    @ToolCollection.tool_call
    def create_irregular_polygon_in_sketch(self, parent_component_name:str="comp1", sketch_name:str="Sketch1", point_list:list=[[0,0,0], [0,1,0], [1,2,0]]):
        """
        {
          "name": "create_irregular_polygon_in_sketch",
          "description": "Creates a polygon in an existing sketch within a specified parent component in Fusion 360. The polygon is formed by connecting a series of points provided in the point_list. the unit for point_list is centimeters",
          "parameters": {
            "type": "object",
            "properties": {
              "parent_component_name": {
                "type": "string",
                "description": "The name of the parent component where the polygon will be created."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the existing sketch where the polygon will be created."
              },
              "point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 2,
                  "maxItems": 2,
                  "description": "A tuple representing an XY point (x, y)."
                },
                "description": "A list of tuples, each representing an XY point (x, y) to be included in the polygon, the unit is centimeters."
              }
            },
            "required": ["parent_component_name", "sketch_name", "point_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the polygon creation."
            }
          }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            parentComponent, errors = self._find_component_by_name(parent_component_name)
            if not parentComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(parentComponent, sketch_name)
            if not targetSketch:
                return errors


            # Add points and lines to the sketch to form the polygon
            for i in range(len(point_list)):
                start_point = adsk.core.Point3D.create(point_list[i][0], point_list[i][1], 0)
                end_point_index = (i + 1) % len(point_list)
                end_point = adsk.core.Point3D.create(point_list[end_point_index][0], point_list[end_point_index][1], 0)
                targetSketch.sketchCurves.sketchLines.addByTwoPoints(start_point, end_point)


            return f'Polygon created in sketch "{sketch_name}"'

        except Exception as e:
            return f'Error: Failed to create polygon in sketch: {e}'


    @ToolCollection.tool_call
    def create_arcs_and_lines_in_sketch(
        self,
        component_name: str = "comp1",
        sketch_name: str = "Sketch1",
        geometry_list: list = [
            { 'object_type': 'arc', 'start': [.5,1,0], 'middle': [.7, .5, 0], 'end': [1,1,0 ] },
            { 'object_type': 'line', 'start': [1,1,0], 'middle': [0,0,0], 'end': [1.2,2,0 ] },
        ]
    ) -> str:
        """
            {
              "name": "create_arcs_and_lines_in_sketch",
              "description": "Creates SketchArcs (by three points) and SketchLines (by two points) in the specified sketch. This allows complex profiles made of arcs and lines. For sketch lines, the middle point will be ignored",
              "parameters": {
                "type": "object",
                "properties": {
                  "component_name": {
                    "type": "string",
                    "description": "The name of the component containing the target sketch."
                  },
                  "sketch_name": {
                    "type": "string",
                    "description": "The name of the sketch in which arcs/lines will be created."
                  },
                  "geometry_list": {
                    "type": "array",
                    "description": "An array of geometry creation instructions. Each item: { 'object_type': 'arc' | 'line', 'start': [x,y,z], 'middle': [x,y,z or null], 'end': [x,y,z] }",
                    "items": {
                      "type": "object",
                      "properties": {
                        "object_type": {
                          "type": "string",
                          "description": "'arc' or 'line'."
                        },
                        "start": {
                          "type": "array",
                          "items": { "type": "number" },
                          "description": "[x,y,z] for the start point of the geometry in the sketch plane coordinate system (Z=0)."
                        },
                        "middle": {
                          "type": "array",
                          "items": { "type": "number" },
                          "description": "For arcs, the 3D point on the arc. For lines, typically null or ignored."
                        },
                        "end": {
                          "type": "array",
                          "items": { "type": "number" },
                          "description": "[x,y,z] for the end point of the geometry in the sketch plane coordinate system."
                        }
                      },
                      "required": ["object_type", "start", "end"]
                    }
                  }
                },
                "required": ["component_name", "sketch_name", "geometry_list"],
                "returns": {
                  "type": "string",
                  "description": "A message summarizing how many arcs/lines were created or any errors encountered."
                }
              }
            }
        """

        try:
            if not geometry_list or not isinstance(geometry_list, list):
                return "Error: 'geometry_list' must be a list of geometry instructions."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Locate the target component
            target_comp = None
            for c in design.allComponents:
                if c.name == component_name:
                    target_comp = c
                    break
            if not target_comp:
                return f"Error: Component '{component_name}' not found."

            # Locate the specified sketch
            target_sketch = None
            for sk in target_comp.sketches:
                if sk.name == sketch_name:
                    target_sketch = sk
                    break
            if not target_sketch:
                return f"Error: Sketch '{sketch_name}' not found in component '{component_name}'."

            # We'll create arcs and lines within this sketch
            lines_collection = target_sketch.sketchCurves.sketchLines
            arcs_collection = target_sketch.sketchCurves.sketchArcs

            created_arcs = 0
            created_lines = 0

            for item in geometry_list:
                obj_type = item.get("object_type", "").lower()
                start_pt = item.get("start", None)
                mid_pt = item.get("middle", None)
                end_pt = item.get("end", None)

                # Basic validation
                if not (isinstance(start_pt, list) and len(start_pt) == 3 and
                        isinstance(end_pt, list) and len(end_pt) == 3):
                    continue  # or record an error

                # Convert to 3D points in the sketch's plane coordinate system (Z=0).
                # The sketch is typically on some plane in 3D space, but
                # we pass [x, y, 0] to create the geometry in sketch coordinates.
                startP = adsk.core.Point3D.create(start_pt[0], start_pt[1], start_pt[2])
                endP = adsk.core.Point3D.create(end_pt[0], end_pt[1], end_pt[2])

                if obj_type == "line":
                    # Lines only need start, end
                    lines_collection.addByTwoPoints(startP, endP)
                    created_lines += 1

                elif obj_type == "arc":
                    # Arcs typically need three points (start, some point on the arc, end)
                    # We'll assume 'middle' is a 3D point on the arc, or we skip if missing
                    if not (isinstance(mid_pt, list) and len(mid_pt) == 3):
                        # If we don't have a valid mid-point, skip
                        continue
                    midP = adsk.core.Point3D.create(mid_pt[0], mid_pt[1], mid_pt[2])
                    arcs_collection.addByThreePoints(startP, midP, endP)
                    created_arcs += 1
                else:
                    # Unknown object_type, skip
                    pass

            return f"Created {created_lines} line(s) and {created_arcs} arc(s) in sketch '{sketch_name}'."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


class CreateObjects(ToolCollection):

    @ToolCollection.tool_call
    def extrude_profiles_in_sketch(
        self,
        component_name: str = "comp1",
        sketch_name: str = "Sketch1",
        profiles_list: list = [[0, 1], [1, 2]],
        operation_type: str = "NewBodyFeatureOperation",
        start_extent: float = 0.0,
        taper_angle: float = 0.0
    ) -> str:

        """
        {
            "name": "extrude_profiles_in_sketch",
            "description": "Extrudes one or more profiles in a specified sketch by different amounts. The profiles are indexed by descending area, where 0 refers to the largest profile. Each item in profiles_list is [profileIndex, extrudeDistance]. The operation_type parameter selects which FeatureOperation to use. The unit for extrudeDistance and start_extent is centimeters, and taper_angle is in degrees (can be positive or negative).",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the sketch."
                    },
                    "sketch_name": {
                        "type": "string",
                        "description": "The name of the sketch inside the specified component containing the profiles."
                    },
                    "profiles_list": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": { "type": "number" },
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "Each element is [profileIndex, extrudeDistance]. profileIndex is an integer referencing the area-sorted profile, extrudeDistance (in cm) is how far to extrude."
                        },
                        "description": "A list of profileIndex / extrudeDistance pairs specifying which profiles to extrude and by how much."
                    },
                    "operation_type": {
                        "type": "string",
                        "enum": [
                            "CutFeatureOperation",
                            "IntersectFeatureOperation",
                            "JoinFeatureOperation",
                            "NewBodyFeatureOperation",
                            "NewComponentFeatureOperation"
                        ],
                        "description": "Specifies the Fusion 360 FeatureOperation to apply."
                    },
                    "start_extent": {
                        "type": "number",
                        "description": "Offset distance in centimeters from the sketch plane to start the extrude. Can be positive or negative. Default 0."
                    },
                    "taper_angle": {
                        "type": "number",
                        "description": "Taper angle (in degrees). Positive or negative. Default 0."
                    }
                },
                "required": ["component_name", "sketch_name", "profiles_list"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating whether the extrude operations completed successfully or not."
                }
            }
        }

        """
        try:
            # A small dictionary to map string inputs to the appropriate enumerations.
            operation_map = {
                "CutFeatureOperation": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "IntersectFeatureOperation": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
                "JoinFeatureOperation": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "NewBodyFeatureOperation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "NewComponentFeatureOperation": adsk.fusion.FeatureOperations.NewComponentFeatureOperation
            }

            # Validate the requested operation_type.
            if operation_type not in operation_map:
                return (f'Error: operation_type "{operation_type}" is not recognized. '
                        f'Valid options are: {", ".join(operation_map.keys())}.')

            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            # Locate the sketch by name (within the target component).
            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            if not targetSketch.profiles or targetSketch.profiles.count == 0:
                return f'Error: Sketch "{sketch_name}" has no profiles to extrude.'

            # Collect and sort profiles by area in descending order (largest first).
            profile_info = []
            for prof in targetSketch.profiles:
                props = prof.areaProperties()
                profile_info.append((prof, props.area))
            profile_info.sort(key=lambda x: x[1], reverse=True)

            # Prepare extrude feature objects
            extrudes = targetComponent.features.extrudeFeatures
            results = []

            # Loop through requested extrusions
            for pair in profiles_list:
                if not isinstance(pair, list) or len(pair) < 2:
                    results.append("Error: Invalid profiles_list entry (expected [profileIndex, distance]).")
                    continue

                profileIndex, extrudeDist = pair[0], pair[1]

                # Check the valid index range.
                if profileIndex < 0 or profileIndex >= len(profile_info):
                    results.append(f"Error: Invalid profile index {profileIndex}.")
                    continue

                selectedProfile = profile_info[profileIndex][0]

                try:
                    # Convert extrudeDist (cm) to internal real value
                    distanceVal = adsk.core.ValueInput.createByReal(float(extrudeDist))

                    # Create the extrude feature input with the requested operation type.
                    extInput = extrudes.createInput(selectedProfile, operation_map[operation_type])

                    # 1) Set an offset start extent if requested
                    if abs(start_extent) > 1e-7:  # effectively non-zero
                        offsetVal = adsk.core.ValueInput.createByReal(float(start_extent))
                        offsetDef = adsk.fusion.OffsetStartDefinition.create(offsetVal)
                        extInput.startExtent = offsetDef

                    # 2) Set the taper angle (in degrees) if non-zero
                    if abs(taper_angle) > 1e-7:
                        # Use createByString for degrees (e.g., "15 deg")
                        angleVal = adsk.core.ValueInput.createByString(f"{taper_angle} deg")
                        extInput.taperAngle = angleVal

                    # 3) Set the extent as a one-side distance.
                    extInput.setDistanceExtent(False, distanceVal)

                    # Add the extrude feature
                    extrudes.add(extInput)
                    results.append(
                        f"Profile index {profileIndex} extruded by {extrudeDist} (startExtent={start_extent}, taper={taper_angle})"
                        f" with {operation_type}."
                    )
                except Exception as e:
                    results.append(f"Error: Could not extrude profile {profileIndex}. Reason: {e}")

            # Combine all messages.
            return "\n".join(results)

        except Exception as e:
            return f"Error: An unexpected exception occurred: {e}"

    @ToolCollection.tool_call
    def revolve_profile_in_sketch(
        self,
        component_name: str = "comp1",
        sketch_name: str = "Sketch1",
        profile_index: int = 0,
        revolve_axis: str = "Z",
        revolve_degrees: float = 180.0,
        operation_type: str = "NewBodyFeatureOperation"
    ) -> str:
        """
        {
          "name": "revolve_profile_in_sketch",
          "description": "Revolves a specified sketch profile around one of the global axes (X, Y, or Z) by a given angle. The revolve is added to the timeline as a new feature.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the component in the current design containing the sketch."
              },
              "sketch_name": {
                "type": "string",
                "description": "Name of the sketch containing the profiles to revolve."
              },
              "profile_index": {
                "type": "number",
                "description": "Index of the profile in the sketch (sorted by descending area). 0 refers to the largest profile."
              },
              "revolve_axis": {
                "type": "string",
                "description": "Which global axis to revolve around: 'X', 'Y', or 'Z'."
              },
              "revolve_degrees": {
                "type": "number",
                "description": "Angle (in degrees) to revolve. Can be positive or negative. Default 180."
              },
              "operation_type": {
                "type": "string",
                "enum": [
                  "CutFeatureOperation",
                  "IntersectFeatureOperation",
                  "JoinFeatureOperation",
                  "NewBodyFeatureOperation",
                  "NewComponentFeatureOperation"
                ],
                "description": "Specifies the Fusion 360 FeatureOperation. Default 'NewBodyFeatureOperation'."
              }
            },
            "required": ["component_name", "sketch_name", "profile_index", "revolve_axis", "revolve_degrees"],
            "returns": {
              "type": "string",
              "description": "A message indicating whether the revolve operation completed successfully or not."
            }
          }
        }
        """

        try:
            # Maps the string operation to the Fusion 360 enum
            operation_map = {
                "CutFeatureOperation": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "IntersectFeatureOperation": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
                "JoinFeatureOperation": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "NewBodyFeatureOperation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "NewComponentFeatureOperation": adsk.fusion.FeatureOperations.NewComponentFeatureOperation
            }

            if operation_type not in operation_map:
                return (f'Error: operation_type "{operation_type}" is not recognized. '
                        f'Valid: {", ".join(operation_map.keys())}.')

            # Access the active design
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            design = adsk.fusion.Design.cast(product)
            if not design:
                return "Error: No active Fusion 360 design found."

            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors


            if not targetSketch.profiles or targetSketch.profiles.count == 0:
                return f"Error: Sketch '{sketch_name}' has no profiles."

            # Sort profiles by area in descending order
            prof_info = []
            for prof in targetSketch.profiles:
                area_props = prof.areaProperties()
                prof_info.append((prof, area_props.area))
            prof_info.sort(key=lambda x: x[1], reverse=True)

            # Validate profile_index
            if profile_index < 0 or profile_index >= len(prof_info):
                return f"Error: profile_index {profile_index} is out of range (0..{len(prof_info)-1})."

            selectedProfile = prof_info[profile_index][0]

            # Create a revolve axis (construction axis) in the component based on revolve_axis
            revolve_axis = revolve_axis.upper()
            if revolve_axis not in ["X", "Y", "Z"]:

                return f"Error: revolve_axis '{revolve_axis}' is invalid. Must be 'X', 'Y', or 'Z'."

            # Define two points in the chosen axis direction (in the component's coordinate system)
            #p0 = adsk.core.Point3D.create(0, 0, 0)
            if revolve_axis == "X":
                #p1 = adsk.core.Point3D.create(1, 0, 0)
                axis = targetComponent.xConstructionAxis
            elif revolve_axis == "Y":
                #p1 = adsk.core.Point3D.create(0, 1, 0)
                axis = targetComponent.yConstructionAxis
            else:  # "Z"
                #p1 = adsk.core.Point3D.create(0, 0, 1)
                axis = targetComponent.zConstructionAxis

            # Create a construction axis
            #axes = targetComponent.constructionAxes
            #axis_input = axes.createInput()
            #axis_input.setByTwoPoints(p0, p1)
            #revolveAxisObj = axes.add(axis_input)
            revolveAxisObj = axis

            # Create revolve input
            revolve_feats = targetComponent.features.revolveFeatures
            rev_input = revolve_feats.createInput(selectedProfile, revolveAxisObj, operation_map[operation_type])
            # One-sided revolve angle
            angleVal = adsk.core.ValueInput.createByString(f"{revolve_degrees} deg")
            rev_input.setAngleExtent(False, angleVal)

            try:
                revolve_feats.add(rev_input)
                return (f"Revolved profile index {profile_index} in sketch '{sketch_name}' around {revolve_axis}-axis by "
                        f"{revolve_degrees} degrees using {operation_type}.")
            except Exception as e:
                return f"Error creating revolve: {e}"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_new_component(self, parent_component_name: str="comp1", component_name: str="comp2") -> str:
        """
            {
                "name": "create_new_component",
                "description": "Creates a new component inside a specified parent component in Fusion 360. The parent component is identified by its name. If the parent component name matches the root component of the design, the new component is created in the root component.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_component_name": {
                            "type": "string",
                            "description": "The name of the parent component where the new component will be created."
                        },
                        "component_name": {
                            "type": "string",
                            "description": "The name to be assigned to the new component."
                        }
                    },
                    "required": ["parent_component_name", "component_name"],
                    "returns": {
                        "type": "string",
                        "description": "Name of successfully created new component"
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

            # Create a new component
            newOccurrence = parentComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            newComponent = newOccurrence.component
            newComponent.name = component_name

            return newComponent.name

        except Exception as e:
            return 'Error: Failed to create new component:\n{}'.format(parent_component_name)

    @ToolCollection.tool_call
    def set_parameter_values(self, parameter_updates: list = [["d1", 1.1], ["d2", 1.9]]) -> str:
        """
        {
          "name": "set_parameter_values",
          "description": "Sets the value of multiple parameters in the active Fusion 360 design. Each item in parameter_updates is [parameterName, newValue].",
          "parameters": {
            "type": "object",
            "properties": {
              "parameter_updates": {
                "type": "array",
                "description": "A list where each element is [parameterName, newValue]. parameterName is a string and newValue is a number.",
                "items": {
                  "type": "array",
                  "minItems": 2,
                  "maxItems": 2,
                  "items": {
                    "type": "string"
                  }
                }
              }
            },
            "required": ["parameter_updates"],
            "returns": {
              "type": "string",
              "description": "Messages indicating the result of each parameter update."
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
            results = []

            # Loop through each [parameterName, newValue] pair
            for update in parameter_updates:
                # Basic validation of each pair
                if not isinstance(update, list) or len(update) != 2:
                    results.append(f"Error: Invalid update format (expected [parameterName, newValue]): {update}")
                    continue

                parameter_name, new_value = update[0], update[1]

                # Attempt to find the parameter by name
                param = design.allParameters.itemByName(parameter_name)
                if not param:
                    results.append(f"Error: Parameter '{parameter_name}' not found.")
                    continue

                # Attempt to set the new value
                try:
                    param.value = float(new_value)
                    results.append(f"Parameter '{parameter_name}' successfully updated to {new_value}.")
                except:
                    # If direct assignment fails (e.g., read-only, locked, or expression-based),
                    # try setting the parameter expression instead
                    try:
                        if param.unit:
                            param.expression = f"{new_value} {param.unit}"
                        else:
                            param.expression = str(new_value)
                        results.append(f"Parameter '{parameter_name}' successfully updated to {new_value}.")
                    except:
                        results.append(f"Error: Failed to update parameter '{parameter_name}' to {new_value}.")

            # Combine and return all messages
            return "\n".join(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def copy_component_as_new(self, source_component_name: str="comp1", target_parent_component_name: str="comp_container", new_component_name: str="new_comp_1") -> str:
        """
            {
                "name": "copy_component_as_new",
                "description": "Creates a completely new component by copying the geometry of an existing component. The copied component is inserted as a new occurrence in the target parent component, but is otherwise independent of the source. The newly created component will be renamed to the provided new_component_name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_component_name": {
                            "type": "string",
                            "description": "The name of the existing Fusion 360 component to be copied."
                        },
                        "target_parent_component_name": {
                            "type": "string",
                            "description": "The name of the component that will serve as the parent for the newly copied component."
                        },
                        "new_component_name": {
                            "type": "string",
                            "description": "The desired name for the newly created component copy."
                        }
                    },
                    "required": ["source_component_name", "target_parent_component_name", "new_component_name"],
                    "returns": {
                        "type": "string",
                        "description": "A message indicating whether the independent copy was successfully created and named."
                    }
                }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            sourceComp, sourceComp = self._find_component_by_name(source_component_name)
            if not targetParentComp:
                return errors

            targetParentComp, errors = self._find_component_by_name(target_parent_component_name)
            if not targetParentComp:
                return errors

            # Create a new, independent copy of the source component
            transform = adsk.core.Matrix3D.create()  # Identity transform
            new_occurrence = targetParentComp.occurrences.addNewComponentCopy(sourceComp, transform)
            new_comp = new_occurrence.component

            # Rename the newly created component
            new_comp.name = new_component_name

            return f'Successfully created a new, independent copy of "{source_component_name}into "{target_parent_component_name}" named "{new_component_name}".'

        except Exception as e:
            return f'Error: Failed to copy "{source_component_name}" as a new component into "{target_parent_component_name}":\n{e}'




class NonCad(ToolCollection):




    def _set_occurrence_grounded(self, occurrence_name: str, grounded: bool = True) -> str:
        """
        {
          "name": "set_occurrence_grounded",
          "description": "Grounds or ungrouds a specified occurrence by toggling its isGrounded property in the root assembly.",
          "parameters": {
            "type": "object",
            "properties": {
              "occurrence_name": {
                "type": "string",
                "description": "Name of the Fusion 360 occurrence to ground or unground."
              },
              "grounded": {
                "type": "boolean",
                "description": "True to ground, False to unground."
              }
            },
            "required": ["occurrence_name"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any errors."
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
            root_comp = design.rootComponent

            targetOccurrence, errors = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return errors

            # Set isGrounded
            #targetOccurrence.isGrounded = grounded
            targetOccurrence.isGroundToParent = grounded


            if grounded:
                return f"Occurrence '{occurrence_name}' is now grounded."
            else:
                return f"Occurrence '{occurrence_name}' is no longer grounded."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def rename_model_parameters(self, old_new_names: list) -> str:
        """
            {
              "name": "rename_model_parameters",
              "description": "Renames multiple model parameters in the active Fusion 360 design. Accepts an array of objects, each containing an old_name and a new_name. Returns a summary indicating which renames succeeded or failed.",
              "parameters": {
                "type": "object",
                "properties": {
                  "old_new_names": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "old_name": {
                          "type": "string",
                          "description": "The current name of the model parameter."
                        },
                        "new_name": {
                          "type": "string",
                          "description": "The new name you wish to assign to the model parameter."
                        }
                      },
                      "required": ["old_name", "new_name"]
                    },
                    "description": "An array of old_name / new_name pairs for the parameters you want to rename."
                  }
                },
                "required": ["old_new_names"],
                "returns": {
                  "type": "string",
                  "description": "A summary message indicating the success or failure of each parameter rename."
                }
              }
            }
        """
        try:
            app = adsk.core.Application.get()

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            results = []  # To store individual success/error messages

            for pair in old_new_names:
                old_name = pair.get("old_name", "")
                new_name = pair.get("new_name", "")

                if not old_name or not new_name:
                    results.append(f"Skipping rename: Missing old_name or new_name in {pair}.")
                    continue

                # Retrieve the parameter by old_name
                param = design.allParameters.itemByName(old_name)
                if not param:
                    results.append(f"Error: Parameter '{old_name}' not found.")
                    continue

                # Attempt to rename
                try:
                    param.name = new_name
                    results.append(f"Renamed '{old_name}' to '{new_name}'.")
                except Exception as rename_error:
                    results.append(
                        f"Error: Failed to rename '{old_name}' to '{new_name}'. Reason: {rename_error}"
                    )

            # Combine all messages into a single result string
            summary = "\n".join(results)
            return summary

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    def _set_appearance_on_occurrences(
        self, appearance_updates: list = [{"occurrence_name": "comp1:1","appearance_name":"Paint - Enamel Glossy (Green)"}]) -> str:

        """
            {
              "name": "set_appearance_on_occurrences",
              "description": "Sets the appearance on a list of occurrence. Each item in appearance_updates is {'occurrence_name': <occurrence_name>, 'appearance_name': <appearance_name>}.",
              "parameters": {
                "type": "object",
                "properties": {
                  "appearance_updates": {
                    "type": "array",
                    "description": "An array of objects with the form {'occurrence_name': <occurrence_name>, 'appearance_name': <appearance_name>}.",
                    "items": {
                      "type": "object",
                      "properties": {
                        "component_name": {
                          "type": "string"
                        },
                        "appearance_name": {
                          "type": "string"
                        }
                      },
                      "required": ["occurrence_name", "appearance_name"]
                    }
                  }
                },
                "required": ["appearance_updates"],
                "returns": {
                  "type": "string",
                  "description": "A summary message about which occurrence were updated or any errors encountered."
                }
              }
            }
        """

    
        try:
            if not appearance_updates or not isinstance(appearance_updates, list):
                return "Error: Must provide an array of updates in the form [{'occurrence_name': '...', 'appearance_name': '...'}, ...]."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # A helper function to find an appearance by name in the design
            # (Optionally search the appearance libraries if not found in design).
            def find_appearance_by_name(appearance_name: str):
                # 1) Check the design's local appearances
                local_appearance = design.appearances.itemByName(appearance_name)
                if local_appearance:
                    return local_appearance

                # 2) Optionally, check libraries if not found in local. Comment this out if not needed.
                appearance_libraries = app.materialLibraries
                for i in range(appearance_libraries.count):

                    a_lib = appearance_libraries.item(i)
                    if a_lib.name not in ["Fusion Appearance Library"]:
                        continue

                    lib_app = a_lib.appearances.itemByName(appearance_name)

                    if lib_app:
                        # You typically need to copy the library appearance into the design before applying
                        return design.appearances.addByCopy(lib_app, appearance_name)

                return None

            results = []
            # Process each update item
            for update in appearance_updates:
                # Validate each item in the array
                if not isinstance(update, dict):
                    results.append("Error: Appearance update must be a dictionary.")
                    continue

                occ_name = update.get("occurrence_name")
                app_name = update.get("appearance_name")

                if not occ_name or not app_name:
                    results.append(f"Error: Missing occurrence_name or appearance_name in {update}.")
                    print("contine")
                    continue

                # Find the appearance by name
                appearance = find_appearance_by_name(app_name)

                if not appearance:
                    results.append(f"Error: Appearance '{app_name}' not found in design or libraries.")
                    continue

                #  in case occurrences was passed in
                targetOcc, errors = self._find_occurrence_by_name(occ_name)
                print(f"targetOcc: {targetOcc}")
                if not targetOcc:
                    results.append(f"Error: Appearance '{app_name}' not found in design or libraries.")
                    continue

                # Setting the appearance property on an occurrence
                targetOcc.appearance = appearance
                # If needed, you can enforce override with:
                #targetOcc.appearance.isOverride = True
                results.append(f"Appearance set on occurrence: {occ_name}")


            return "\n".join(results)

        except:
            print("ERROR")
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()





    def _set_visibility( self, objects_to_set: list = [ {"object_type": "occurrence", "object_name": "comp1", "visible": False} ]) -> str: 
        """
            {
              "name": "set_visibility",
              "description": "Sets the visibility for various Fusion 360 objects (occurrence, bodies, sketches, joints, joint_origins) based on the provided instructions.",
              "parameters": {
                "type": "object",
                "properties": {
                  "objects_to_set": {
                    "type": "array",
                    "description": "Array of items specifying object type, name, and visibility. Example: [{'object_type': 'occurrence', 'object_name': 'comp1:1', 'visible': True}, ...]",
                    "items": {
                      "type": "object",
                      "properties": {
                        "object_type": {
                          "type": "string",
                          "description": "'occurrence', 'body', 'sketch', 'joint', 'joint_origin'."
                        },
                        "object_name": {
                          "type": "string",
                          "description": "The name of the object in Fusion 360."
                        },
                        "visible": {
                          "type": "boolean",
                          "description": "True to show, False to hide."
                        }
                      },
                      "required": ["object_type", "object_name", "visible"]
                    }
                  }
                },
                "required": ["objects_to_set"],
                "returns": {
                  "type": "string",
                  "description": "A summary message about which objects were updated or any errors encountered."
                }
              }
            }
        """

        try:
            # Validate input
            if not objects_to_set or not isinstance(objects_to_set, list):
                return "Error: Must provide a list of objects to set visibility on."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # Helper: gather ALL components in the design in a list for quick searching
            all_comps = []
            def collect_all_components(comp):
                all_comps.append(comp)
                for occ in comp.occurrences:
                    collect_all_components(occ.component)

            collect_all_components(root_comp)



            # Helper: gather ALL bodies and sketches across all components
            all_bodies = []
            all_sketches = []
            all_joints = []
            all_joint_origins = []

            for comp in all_comps:
                for body in comp.bRepBodies:
                    all_bodies.append(body)
                for sk in comp.sketches:
                    all_sketches.append(sk)
                for joint in comp.joints:
                    all_joints.append(joint)
                for joint_origin in comp.jointOrigins:
                    all_joint_origins.append(joint_origin)

            messages = []

            # Process each visibility instruction
            for item in objects_to_set:
                obj_type = item.get('object_type')
                obj_name = item.get('object_name')
                visible = item.get('visible')

                if not obj_type or not obj_name or visible is None:
                    messages.append(f"Error: Missing or invalid fields in {item}.")
                    continue

                if obj_type.lower() == 'component':
                    # Hide/show all occurrences referencing this component name
                    found_occurrences = []
                    for comp in all_comps:
                        if comp.name == obj_name:
                            # Look in root for occurrences referencing comp
                            for i in range(root_comp.occurrences.count):
                                occ = root_comp.occurrences.item(i)
                                if occ.component == comp:
                                    found_occurrences.append(occ)
                            # Also look in sub-assemblies (occurrences of occurrences)
                            # but since we recursively gather "all_comps," the root's
                            # occurrences might suffice if the user consistently named
                            # components. If needed, you could do a more advanced search.

                    if not found_occurrences:
                        messages.append(f"Error: No occurrences found for component '{obj_name}'.")
                        continue

                    for occ in found_occurrences:
                        try:
                            occ.isLightBulbOn = bool(visible)
                        except Exception as e:
                            messages.append(f"Error: Could not set visibility on occurrence '{occ.name}': {e}")
                    messages.append(f"Set visibility for component '{obj_name}' to {visible} (affected {len(found_occurrences)} occurrence(s)).")

                elif obj_type.lower() == 'body':
                    # Hide/show bodies by name
                    found_bodies = [b for b in all_bodies if b.name == obj_name]
                    if not found_bodies:
                        messages.append(f"Error: No body found with name '{obj_name}'.")
                        continue

                    for b in found_bodies:
                        try:
                            b.isLightBulbOn = bool(visible)
                        except Exception as e:
                            messages.append(f"Error: Could not set visibility on body '{b.name}': {e}")
                    messages.append(f"Set visibility for body '{obj_name}' to {visible} (affected {len(found_bodies)} body/ies).")
                elif obj_type.lower() == 'joint':
                    # Hide/show joints by name
                    found_joints = [jt for jt in all_joints if jt.name == obj_name]
                    if not found_joints:
                        messages.append(f"Error: No joint found with name '{obj_name}'.")
                        continue
                    for jt in found_joints:
                        try:
                            jt.isLightBulbOn = bool(visible)
                        except Exception as e:
                            messages.append(f"Error: Could not set visibility on joint '{jt.name}': {e}")
                    messages.append(f"Set visibility for body '{obj_name}' to {visible} (affected {len(found_joints)} joints).")
                elif obj_type.lower() == 'joint_origin':
                    # Hide/show joint origins by name
                    found_joint_origins = [jo for jo in all_joint_origins if jo.name == obj_name]
                    if not found_joint_origins:
                        messages.append(f"Error: No joint origin found with name '{obj_name}'.")
                        continue
                    for jo in found_joint_origins:
                        try:
                            jo.isLightBulbOn = bool(visible)
                        except Exception as e:
                            messages.append(f"Error: Could not set visibility on joint '{jo.name}': {e}")
                    messages.append(f"Set visibility for body '{obj_name}' to {visible} (affected {len(found_joint_origins)} joint origins).")



                elif obj_type.lower() == 'sketch':
                    # Hide/show sketches by name
                    found_sketches = [s for s in all_sketches if s.name == obj_name]
                    if not found_sketches:
                        messages.append(f"Error: No sketch found with name '{obj_name}'.")
                        continue

                    for sk in found_sketches:
                        try:
                            sk.isLightBulbOn = bool(visible)
                        except Exception as e:
                            messages.append(f"Error: Could not set visibility on sketch '{sk.name}': {e}")
                    messages.append(f"Set visibility for sketch '{obj_name}' to {visible} (affected {len(found_sketches)} sketch(es)).")

                else:
                    messages.append(f"Error: Unknown object_type '{obj_type}' in {item}.")

            return "\n".join(messages)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    # TODO
    def capture_component_position(self, component_name: str = "comp1") -> str:
        """
        {
          "name": "capture_component_position",
          "description": "Retrieves the current global position (translation) of each occurrence referencing the specified component.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the Fusion 360 component whose occurrences' positions will be captured."
              }
            },
            "required": ["component_name"],
            "returns": {
              "type": "string",
              "description": "A JSON array where each element has an 'occurrenceName' and 'position' [x, y, z] in centimeters."
            }
          }
        }
        """

        return ""
        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # Find all occurrences of this component
            target_occurrences = []
            for i in range(root_comp.occurrences.count):
                occ = root_comp.occurrences.item(i)
                if occ.component.name == component_name:
                    target_occurrences.append(occ)

            if not target_occurrences:
                return f"Error: No occurrences found for component '{component_name}'."

            # Collect the translation vector (x, y, z) for each occurrence
            positions_info = []
            for occ in target_occurrences:
                transform = occ.transform
                translation = transform.translation
                positions_info.append({
                    "occurrenceName": occ.name,
                    "position": [translation.x, translation.y, translation.z]
                })

            # Return the data as a JSON array string
            return json.dumps(positions_info)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()




class ModifyObjects(ToolCollection):


    @ToolCollection.tool_call
    def copy_component(self, source_component_name: str, target_parent_component_name: str) -> str:
        """
            {
                "name": "copy_component",
                "description": "Creates a new occurrence of an existing component inside another parent component. This effectively 'copies' the geometry by referencing the same underlying component in a new location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_component_name": {
                            "type": "string",
                            "description": "The name of the existing Fusion 360 component to be copied."
                        },
                        "target_parent_component_name": {
                            "type": "string",
                            "description": "The name of the component that will serve as the parent for the new copy."
                        }
                    },
                    "required": ["source_component_name", "target_parent_component_name"],
                    "returns": {
                        "type": "string",
                        "description": "A message indicating whether the copy (new occurrence) was successfully created."
                    }

                }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            # Locate the source component using a helper method (assumed to exist in your environment)

            sourceComp, errors = self._find_component_by_name(source_component_name)
            if not sourceComp:
                return errors

            targetParentComp, errors = self._find_component_by_name(target_parent_component_name)
            if not targetParentComp:
                return errors

            # Create a new occurrence of the source component in the target parent component
            transform = adsk.core.Matrix3D.create()  # Identity transform (no rotation, no translation)
            new_occurrence = targetParentComp.occurrences.addExistingComponent(sourceComp, transform)

            # (Optional) Rename the new occurrence if you want a distinct name
            # new_occurrence.name = source_component_name + "_copy"

            return f'Successfully copied "{source_component_name}" into "{target_parent_component_name}".'

        except Exception as e:
            return f'Error: Failed to copy "{source_component_name}" into "{target_parent_component_name}":\n{e}'

    @ToolCollection.tool_call
    def fillet_or_chamfer_edges(self,
                               component_name: str = "comp1",
                               body_name: str = "Body1",
                               edge_index_list: list = [0],
                               operation_value: float = 0.2,
                               operation_type: str = "fillet") -> str:
        """
        {
          "name": "fillet_or_chamfer_edges",
          "description": "Applies either a fillet or chamfer to the specified edges of a body.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the Fusion 360 component containing the target body."
              },
              "body_name": {
                "type": "string",
                "description": "Name of the BRep body whose edges will be modified."
              },
              "edge_index_list": {
                "type": "array",
                "description": "A list of integer edge indexes from the body whose edges will be filleted or chamfered.",
                "items": {
                  "type": "number"
                }
              },
              "operation_value": {
                "type": "number",
                "description": "The distance (radius or chamfer distance) to apply, in centimeters."
              },
              "operation_type": {
                "type": "string",
                "description": "Either 'fillet' or 'chamfer'."
              }
            },
            "required": ["component_name", "body_name", "edge_index_list", "operation_value", "operation_type"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or details about any errors encountered."
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


            # find the target component by name (assuming you have a local helper method).
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body, errors  = self._find_body_by_name(targetComponent, body_name)
            if not body:
                return errors

            # Validate operation_type
            op_type_lower = operation_type.lower()
            if op_type_lower not in ("fillet", "chamfer"):
                return f"Error: Invalid operation_type '{operation_type}'. Must be 'fillet' or 'chamfer'."

            # Collect edges
            edges = body.edges
            edge_collection = adsk.core.ObjectCollection.create()
            invalid_indexes = []
            for idx in edge_index_list:
                if 0 <= idx < edges.count:
                    edge_collection.add(edges[idx])
                else:
                    invalid_indexes.append(idx)

            # If no valid edges were found, return an error.
            if edge_collection.count == 0:
                return f"Error: No valid edges found. Invalid indexes: {invalid_indexes}" if invalid_indexes else "Error: No valid edges provided."

            # Create either a fillet or a chamfer
            if op_type_lower == "fillet":
                try:
                    fillet_feats = targetComponent.features.filletFeatures
                    fillet_input = fillet_feats.createInput()
                    # Construct the radius ValueInput
                    radius_val = adsk.core.ValueInput.createByReal(float(operation_value))
                    # Add all edges to a single radius set
                    fillet_input.addConstantRadiusEdgeSet(edge_collection, radius_val, True)
                    fillet_feats.add(fillet_input)
                    msg = f"Fillet applied with radius {operation_value} to edges: {edge_index_list}."
                except Exception as e:
                    return f"Error: Error creating fillet: {e}"
            else:  # chamfer
                try:
                    chamfer_feats = targetComponent.features.chamferFeatures
                    # For a simple equal-distance chamfer, we set 'distance'
                    distance_val = adsk.core.ValueInput.createByReal(float(operation_value))
                    # The createInput function signature is chamferFeatures.createInput(ObjectCollection, isTangentChain)
                    chamfer_input = chamfer_feats.createInput(edge_collection, True)
                    chamfer_input.setToEqualDistance(distance_val)
                    chamfer_feats.add(chamfer_input)
                    msg = f"Chamfer applied with distance {operation_value} to edges: {edge_index_list}."
                except Exception as e:
                    return f"Error: Error creating chamfer: {e}"

            # Include any invalid edge indexes in the output message for clarity
            if invalid_indexes:
                msg += f" Some invalid indexes were ignored: {invalid_indexes}"

            return msg

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def move_occurrence(self,
                       occurrence_name: str = "comp1:1",
                       move_position: list = [1.0, 1.0, 0.0]) -> str:
        """
        {
          "name": "move_occurrence",
          "description": "Moves the specified occurrence so that its local origin is placed at the given [x, y, z] point in centimeters.",
          "parameters": {
            "type": "object",
            "properties": {
              "occurrence_name": {
                "type": "string",
                "description": "Name of the Fusion 360 occurrence to move."
              },
              "move_position": {
                "type": "array",
                "description": "The [x, y, z] coordinates (in centimeters) to place the component's local origin in the global coordinate system.",
                "items": { "type": "number" }
              }
            },
            "required": ["occurrence_name", "move_position"],
            "returns": {
              "type": "string",
              "description": "A message indicating the result of the move operation."
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
            root_comp = design.rootComponent
            features = root_comp.features

            # Validate the move_position format: expecting [x, y, z].
            if (not isinstance(move_position, list)) or (len(move_position) < 3):
                return "Error: move_position must be an array of [x, y, z]."

            # Extract the coordinates (in centimeters)
            x_val, y_val, z_val = move_position

            targetOccurrence, errors = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return errors

            # Create a transform with the translation [x_val, y_val, z_val].
            transform = adsk.core.Matrix3D.create()
            translation = adsk.core.Vector3D.create(x_val, y_val, z_val)
            transform.translation = translation

            try:
                targetOccurrence.timelineObject.rollTo(False)
                targetOccurrence.initialTransform = transform
                #occ.transform = transform

            except Exception as e:
                return f"Error: Could not transform occurrence '{occurrence_name}'. Reason: {e}"

            timeline = design.timeline
            timeline.moveToEnd()


            return (f"Moved occurrence '{occurrence_name}' to "
                    # TODO
                    f"[{x_val}, {y_val}, {z_val}] cm")

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def reorient_occurrence(self, occurrence_name: str = "comp1:1", axis: list = [0, 0, 1], target_vector: list = [1, 0, 0]) -> str:
        """
        {
          "name": "reorient_occurrence",
          "description": "Reorients the specified occurrence by rotating its local orientation so that a given axis is aligned with a specified target vector. Both the axis and target vector should be provided as arrays of three numbers representing 3D directions. The function uses Matrix3D.setToRotateTo to compute the necessary rotation transform.",
          "parameters": {
            "type": "object",
            "properties": {
              "occurrence_name": {
                "type": "string",
                "description": "Name of the Fusion 360 occurrence to reorient."
              },
              "axis": {
                "type": "array",
                "description": "A list of three numbers representing the current orientation axis (direction vector) of the occurrence that will be rotated.",
                "items": { "type": "number" },
                "minItems": 3,
                "maxItems": 3
              },
              "target_vector": {
                "type": "array",
                "description": "A list of three numbers representing the target direction for the specified axis.",
                "items": { "type": "number" },
                "minItems": 3,
                "maxItems": 3
              }
            },
            "required": ["occurrence_name", "axis", "target_vector"],
            "returns": {
              "type": "string",
              "description": "A message indicating the result of the reorientation operation."
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
            root_comp = design.rootComponent

            # Validate the axis and target_vector parameters: expecting lists of 3 numbers each.
            if not (isinstance(axis, list) and len(axis) == 3):
                return "Error: 'axis' must be a list of 3 numbers."
            if not (isinstance(target_vector, list) and len(target_vector) == 3):
                return "Error: 'target_vector' must be a list of 3 numbers."

            # Create Vector3D objects from the provided lists.
            fromVector = adsk.core.Vector3D.create(axis[0], axis[1], axis[2])
            toVector = adsk.core.Vector3D.create(target_vector[0], target_vector[1], target_vector[2])

            # Create a transformation matrix and set it to rotate from the 'fromVector' to the 'toVector'
            transform = adsk.core.Matrix3D.create()
            success = transform.setToRotateTo(fromVector, toVector)
            if not success:
                return "Error: Could not compute rotation transform using setToRotateTo."

            # Find the target occurrence using a helper method.
            targetOccurrence, errors = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return f"Error: No occurrence found for '{occurrence_name}'."

            try:
                targetOccurrence.timelineObject.rollTo(False)
                targetOccurrence.initialTransform = transform
            except Exception as e:
                return f"Error: Could not reorient occurrence '{occurrence_name}'. Reason: {e}"

            timeline = design.timeline
            timeline.moveToEnd()

            return (f"Reoriented occurrence '{occurrence_name}' such that the axis {axis} is rotated "
                    f"to align with {target_vector}.")
        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def mirror_body_in_component(
        self,
        component_name: str = "comp1",
        body_name: str = "Body1",
        operation_type: str = "JoinFeatureOperation",
        mirror_plane: str = "XY"
    ) -> str:
        """
        {
          "name": "mirror_body_in_component",
          "description": "Mirrors a specified body in a component along one of the component's planes (XY, XZ, YZ) or a planar face in the body by face index. It creates a MirrorFeature in the timeline.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component containing the target body."
              },
              "body_name": {
                "type": "string",
                "description": "The name of the BRepBody to mirror."
              },
              "operation_type": {
                "type": "string",
                "description": "Either 'JoinFeatureOperation' or 'NewBodyFeatureOperation'.",
                "enum": [
                  "JoinFeatureOperation",
                  "NewBodyFeatureOperation"
                ]
              },
              "mirror_plane": {
                "type": "string",
                "description": "The plane to mirror about. Accepted values: 'XY', 'XZ', 'YZ' (the component's origin planes) OR a face reference in the form 'FaceIndex=3'."
              }
            },
            "required": ["component_name", "body_name", "operation_type", "mirror_plane"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any error encountered."
            }
          }
        }
        """

        try:
            # Validate operation_type
            valid_ops = ["JoinFeatureOperation", "NewBodyFeatureOperation"]
            if operation_type not in valid_ops:
                return (f"Error: operation_type '{operation_type}' must be one of: {valid_ops}.")

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)


            # Find the target component by name (assuming you have a helper method).
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body_to_mirror, errors  = self._find_body_by_name(targetComponent, body_name)
            if not body_to_mirror:
                return errors

            # Decide on the mirror plane
            mirror_plane_obj = None

            # 1) If it's one of 'XY', 'XZ', or 'YZ', use the component's origin planes
            plane_label = mirror_plane.upper().strip()
            if plane_label in ["XY", "XZ", "YZ"]:
                planes = targetComponent.constructionPlanes

                #TODO
                #origin_planes = target_comp.originConstructionPlanes
                # originConstructionPlanes has .item(0)=XY, .item(1)=XZ, .item(2)=YZ in typical order
                # But let's map them carefully:
                plane_map = {
                    "XY": targetComponent.xYConstructionPlane,
                    "XZ": targetComponent.xZConstructionPlane,
                    "YZ": targetComponent.yZConstructionPlane,
                }
                mirror_plane_obj = plane_map.get(plane_label)

            # 2) If it starts with 'FaceIndex=', interpret it as a face index on the body
            elif plane_label.startswith("FACEINDEX="):
                # Parse out the integer
                try:
                    face_index = int(plane_label.split("=")[1])
                except:
                    return f"Error: Could not parse face index from '{mirror_plane}'."
                if face_index < 0 or face_index >= body_to_mirror.faces.count:
                    return f"Error: Face index {face_index} out of range for body '{body_name}'."
                face_obj = body_to_mirror.faces.item(face_index)
                # The face must be planar
                plane_face = adsk.fusion.BRepFace.cast(face_obj)
                if not plane_face or not plane_face.geometry or not isinstance(plane_face.geometry, adsk.core.Plane):
                    return f"Error: Face {face_index} is not planar, cannot mirror about it."
                mirror_plane_obj = plane_face

            else:
                return (f"Error: mirror_plane '{mirror_plane}' is invalid. "
                        "Use 'XY', 'XZ', 'YZ', or 'FaceIndex=N' with a planar face.")

            if not mirror_plane_obj:
                return f"Error: Could not obtain a valid mirror plane from '{mirror_plane}'."

            # Build the input for the MirrorFeature
            mirror_feats = targetComponent.features.mirrorFeatures
            input_entities = adsk.core.ObjectCollection.create()
            input_entities.add(body_to_mirror)

            mirror_input = mirror_feats.createInput(input_entities, mirror_plane_obj)

            # If you want to specify Join vs NewBody, do so via isCombine for MirrorFeatures
            # https://help.autodesk.com/view/fusion360/ENU/?guid=Fusion360_API_Reference_manual_cpp_ref_classadsk_1_1fusion_1_1_mirror_feature_input_html
            if operation_type == "JoinFeatureOperation":
                mirror_input.isCombine = True
            else:
                mirror_input.isCombine = False

            try:
                mirror_feature = mirror_feats.add(mirror_input)
                return (f"Mirrored body '{body_name}' in component '{component_name}' about "
                        f"plane '{mirror_plane}' with operation '{operation_type}'.")
            except Exception as e:
                return f"Error creating mirror feature: {str(e)}"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


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





class DeleteObjects(ToolCollection):

    @ToolCollection.tool_call
    def delete_component_sub_object(self, delete_object_array :list=[
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
    ]) -> str:

        """
        {
            "name": "delete_component_sub_object",
            "description": "Deletes any valid object inside of component",
            "parameters": {
                "type": "object",
                "properties": {

                    "delete_object_array": {
                        "type": "array",
                        "description": "Array of objects to delete",

                        "items": {
                            "type": "object",
                            "properties": {
                                "component_name": {
                                    "type": "string",
                                    "description": "name of the component containing the object to delete"
                                },
                                "object_type": {
                                    "type": "string",
                                    "description": "type of object to delete",
                                    "enum": [ "sketches",
                                            "bRepBodies",
                                            "meshBodies",
                                            "joints",
                                            "jointOrigins",
                                            "occurrences",
                                            "rigidGroups"]
                                },
                                "object_name": {
                                    "type": "string",
                                    "description": "The name of the object to delete"
                                }
                            },
                            "required": ["component_name", "object_type", "object_name"]
                        }

                    }
                },

                "required": ["delete_object_array"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating success or failure of the deletions."
                }
            }
        }
        """
        try:
            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # check arg type
            if not isinstance(delete_object_array, list):
                return "Error: delete_object_array must be an array/ list"

            delete_enums = [
                "sketches",
                "bRepBodies",
                "meshBodies",
                "joints",
                "jointOrigins",
                "occurrences",
                "rigidGroups",
            ]

            # add object to delete to dict, faster this way
            delete_dict = {}

            results = []
            # jonied as string and returned
            # items in array, each representing a delete task
            for delete_object in delete_object_array:
                component_name = delete_object.get("component_name")

                object_type = delete_object.get("object_type")
                object_name = delete_object.get("object_name")

                targetComponent, errors = self._find_component_by_name(component_name)

                if not targetComponent:
                    # if results, add error to return list
                    results.append(errors)
                    continue

                # comp.sketches, comp.bodies, comp.joints etc
                object_class = getattr(targetComponent, object_type, None)

                # check if delete object class list exists
                if object_class == None:
                    results.append(f"Error: Component {component_name} has not attribute '{object_type}'.")
                    continue

                # check that attr has 'itemByName' method before calling it
                if hasattr(object_class, "itemByName") == False:
                    errors = f"Error: Component {component_name}.{object_type} has no method 'itemByName'."
                    results.append(errors)
                    continue

                # select object to delete by name, sketch, body, joint, etc
                target_object = object_class.itemByName(object_name)

                # check if item by name is None
                if target_object == None:
                    errors = f"Error: Component {component_name}: {object_type} has no item {object_name}."
                    available_objects = [o.name for o in object_class]
                    errors += f" Available objects in {component_name}.{object_type}: {available_objects}"
                    results.append(errors)
                    continue

                # check if item can be delete
                if hasattr(target_object,"deleteMe") == False:
                    errors = f"Error: Component {component_name}.{object_type} object {object_name} has no attribute deleteMe."
                    results.append(errors)
                    continue


                delete_dict[f"{component_name}.{object_type}.{target_object.name}"] = target_object
                #results.append(f'Added {component_name}.{object_type} "{target_object.name}" to delete list.')


            if len(list(delete_dict.keys())) == 0:
                results.append(f"No objects to delete.")

            for k, v in delete_dict.items():
                delete_result = v.deleteMe()

                if delete_result == True:
                    results.append(f"Deleted {k}.")
                else:
                    results.append(f"Error deleting {k}.")


            #delete_name_list = []
            #deleteCollection = adsk.core.ObjectCollection.create()
            #for deleteObject in delete_list:
            #    deleteCollection.add(deleteObject)

            #design.deleteEntities(deleteCollection)
            #print(deleteCollection)

            #results.append("All object deleted")

            return "\n".join(results).strip()

        except:
            return f'Error: Failed to delete objects:\n{traceback.format_exc()}'


    @ToolCollection.tool_call
    def delete_occurrence(self, occurrence_name: str="comp1:1") -> str:
        """
        {
            "name": "delete_occurrence",
            "description": "Deletes a occurrence from the current Fusion 360 design based on the given occurrence name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "occurrence_name": {
                        "type": "string",
                        "description": "The name of the Fusion 360 occurrence object to be deleted."
                    }
                },
                "required": ["occurrence_name"]
            }
        }
        """
        try:

            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            targetOccurrence, errors, = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return errors

            targetOccurrence.deleteMe()

            return f'deleted {occurrence_name}'

        except Exception as e:
            return f'Error: Failed to delete occurrence "{occurrence_name}":\n{e}'


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
                        print(edge.geometry)
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
                    #print(edgeObj)


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
                print(request)
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

    @ToolCollection.tool_call
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




class Timeline(ToolCollection):

    @ToolCollection.tool_call
    def list_timeline_info(self) -> str:
        """
            {
              "name": "list_timeline_info",
              "description": "Returns a JSON array describing all items in the Fusion 360 timeline, including entity info, errors/warnings, healthState, etc.",
              "parameters": {
                "type": "object",
                "properties": {
                },
                "required": [],
                "returns": {
                  "type": "string",
                  "description": "A JSON array; each entry includes timeline item data such as index, name, entityType, healthState, errorOrWarningMessage, etc."
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
            timeline = design.timeline

            timeline_info = []

            for i in range(timeline.count):
                t_item = timeline.item(i)
                if not t_item:
                    continue

                # Collect basic info
                item_data = {
                    "index": t_item.index,
                    "name": t_item.name,
                    "isSuppressed": t_item.isSuppressed,
                    "healthState": str(t_item.healthState),          # e.g. 'HealthStateError', 'HealthStateOk'
                    "errorOrWarningMessage": t_item.errorOrWarningMessage,
                }

                # Parent group reference
                if t_item.parentGroup:
                    item_data["parentGroupIndex"] = t_item.parentGroup.index
                    item_data["parentGroupName"] = t_item.parentGroup.name

                # Entity info
                entity = t_item.entity
                if entity:
                    # We'll store a few general properties if available
                    entity_type = entity.objectType  # e.g. 'adsk::fusion::ExtrudeFeature'
                    item_data["entityType"] = entity_type

                    # Many entities have a "name" property, but not all. We'll try/catch.
                    entity_name = getattr(entity, "name", None)
                    if entity_name:
                        item_data["entityName"] = entity_name

                    # Optionally gather more info if you like:
                    # e.g. if entity_type indicates a feature, you could store
                    # entity.isSuppressed or others. Just be sure to check for availability.
                else:
                    item_data["entityType"] = None  # E.g., might be a group or unknown.

                timeline_info.append(item_data)

            return json.dumps(timeline_info)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def delete_timeline_items(self, indexes_to_delete: list = []) -> str:
        """
        {
          "name": "delete_timeline_items",
          "description": "Deletes one or more items in the timeline by their index. Use list_timeline_info() to find item indexes first.",
          "parameters": {
            "type": "object",
            "properties": {
              "indexes_to_delete": {
                "type": "array",
                "description": "A list of integer indexes of the timeline items to delete. Example: [1, 5, 7]",
                "items": { "type": "number" }
              }
            },
            "required": ["indexes_to_delete"],
            "returns": {
              "type": "string",
              "description": "A message about which items were deleted or any errors encountered."
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
            timeline = design.timeline

            if not indexes_to_delete:
                return "Error: No indexes provided to delete."

            # Sort descending to avoid reindexing issues as we delete
            sorted_indexes = sorted(indexes_to_delete, reverse=True)

            results = []
            for idx in sorted_indexes:
                if idx < 0 or idx >= timeline.count:
                    results.append(f"Error: Timeline index {idx} out of range.")
                    continue

                item = timeline.item(idx)
                # Attempt the deletion
                try:

                    item_name = item.name
                    item.entity.deleteMe()
                    results.append(f"Deleted timeline item at index {idx}: {item_name}")
                except Exception as e:
                    results.append(f"Error: deleting timeline item {idx}: {str(e)}")

            return "\n".join(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def roll_back_to_timeline(self, index_to_rollback: int = 0) -> str:
        """
        {
          "name": "roll_back_to_timeline",
          "description": "Rolls the design's timeline marker back (or forward) to the specified index, effectively suppressing all features after that index.",
          "parameters": {
            "type": "object",
            "properties": {
              "index_to_rollback": {
                "type": "number",
                "description": "The timeline index to move the marker to. Items after this index will be suppressed in the UI."
              }
            },
            "required": ["index_to_rollback"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any error encountered."
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
            timeline = design.timeline

            if index_to_rollback < 0 or index_to_rollback >= timeline.count:
                return f"Error: index_to_rollback {index_to_rollback} out of range (0..{timeline.count - 1})."

            # Move the marker position
            timeline.markerPosition = index_to_rollback
            return f"Timeline marker moved to index {index_to_rollback}."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def delete_timeline_groups(self, group_names: list) -> str:
        """
        {
          "name": "delete_timeline_groups",
          "description": "Deletes timeline groups from the active Fusion 360 design whose names match any in the provided list. The function iterates through the timeline, identifies items that are classified as groups (using their entityType or naming convention), and deletes them by collecting their indexes and calling the delete_timeline_items function.",
          "parameters": {
            "type": "object",
            "properties": {
              "group_names": {
                "type": "array",
                "description": "A list of strings representing the names of timeline groups to delete.",
                "items": { "type": "string" }
              }
            },
            "required": ["group_names"],
            "returns": {
              "type": "string",
              "description": "A message indicating which timeline groups were deleted, or an error message if the operation failed."
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
            timeline = design.timeline

            # List to collect indexes of timeline items that are groups and match provided names.
            indexes_to_delete = []

            # Iterate over timeline items.
            for i in range(timeline.count):
                timelineItem = timeline.item(i)
                # Assuming that timeline items representing groups have an entityType "TimelineGroup"
                # or follow a naming convention. Here we check if the name of the item is in group_names.
                # (Adjust the check below if your design uses a different method to mark groups.)
                if timelineItem.name in group_names:
                    indexes_to_delete.append(i)

            if not indexes_to_delete:
                return "No timeline groups matching the provided names were found."

            # It's best to delete timeline items in reverse order to avoid index shifting.
            indexes_to_delete.sort(reverse=True)

            # Call the existing delete_timeline_items function.
            result = self.delete_timeline_items(indexes_to_delete)
            return f"Deleted timeline groups with names {group_names}. Details: {result}"
        except Exception as e:
            return "Error: Failed to delete timeline groups. Exception:\n" + traceback.format_exc()

    def set_all_timeline_groups_state(self, collapse: bool = True) -> str:
        """
        {
          "name": "set_all_timeline_groups_state",
          "description": "Expands or collapses all timeline groups in the active Fusion 360 design. The 'collapse' parameter determines whether to expand (False) or collapse (True) all timeline groups in the timeline. The function iterates through all timeline items and, for those that support the 'isExpanded' property (indicating they are groups), sets their expansion state accordingly.",
          "parameters": {
            "type": "object",
            "properties": {
              "collapse": {
                "type": "boolean",
                "description": "A boolean flag where True collapses all timeline groups and False expands them."
              }
            },
            "required": ["expand"],
            "returns": {
              "type": "string",
              "description": "A message indicating which timeline groups were modified, or an error message if the operation failed."
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
            timelineGroups = design.timeline.timelineGroups

            modified_groups = []
            # Iterate over all timeline items.
            for tlGroup in timelineGroups:

                if hasattr(tlGroup, 'isCollapsed'):
                    tlGroup.isCollapsed = collapse
                    modified_groups.append(tlGroup.name)

            if not modified_groups:
                return "No timeline groups found or none could be modified."

            state = "collapsed" if collapse else "expanded"
            return f"All timeline groups were set to {state}. Modified groups: {modified_groups}"
        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def set_timeline_groups_state(self, group_names: list, expand: bool = True) -> str:
        """
        {
          "name": "set_timeline_groups_state",
          "description": "Expands or collapses timeline groups in the active Fusion 360 design based on the provided group names. The 'expand' parameter determines whether to expand (True) or collapse (False) the matching timeline groups. This function iterates over timeline items, identifies groups by matching their names against the provided list, and then sets their expansion state using a property or method (if available) on the timeline group objects.",
          "parameters": {
            "type": "object",
            "properties": {
              "group_names": {
                "type": "array",
                "description": "A list of strings representing the names of timeline groups to modify.",
                "items": { "type": "string" }
              },
              "expand": {
                "type": "boolean",
                "description": "A boolean flag where True expands the timeline groups and False collapses them."
              }
            },
            "required": ["group_names", "expand"],
            "returns": {
              "type": "string",
              "description": "A message indicating which timeline groups were expanded or collapsed, or an error message if the operation failed."
            }
          }
        }
        """
        try:
            # Get the Fusion 360 application and active design.
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            timeline = design.timeline

            modified_groups = []
            # Iterate through timeline items.
            for i in range(timeline.count):
                timelineItem = timeline.item(i)
                # Check if the timeline item name is one of the target group names.
                if timelineItem.name in group_names:
                    try:
                        # Attempt to set the expansion state.
                        # Note: This assumes that timeline group items expose an 'isExpanded' property.
                        # If the API differs, adjust this section accordingly.
                        timelineItem.isExpanded = expand
                        modified_groups.append(timelineItem.name)
                    except Exception as innerEx:
                        # If an individual group cannot be modified, log and continue.
                        pass

            if not modified_groups:
                return "No matching timeline groups found or none could be modified."

            state = "expanded" if expand else "collapsed"
            return f"Timeline groups {modified_groups} were set to {state}."
        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

