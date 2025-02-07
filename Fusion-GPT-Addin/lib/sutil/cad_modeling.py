# cad design

import adsk.core
import adsk.fusion
import adsk.cam
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
import functools
import hashlib
import base64
import re

from ... import config
from ...lib import fusion360utils as futil

from .shared import ToolCollection

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")




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

            sourceComp, errors = self._find_component_by_name(source_component_name)
            if not sourceComp:
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


    ### OLD

    #@ToolCollection.tool_call
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










